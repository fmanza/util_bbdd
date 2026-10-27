"""Planificador de la ejecución paralela de las cargas masivas (v3.0.0).

``ParallelPlanner`` decide cuántos hilos usar en una carga por particiones: es la **política**; el mecanismo (un hilo y
una ``BulkCrud`` por partición) lo pone ``ParallelBulkLoader``. Lo usan ``BulkCrud`` (``ParallelOptions``),
``ParallelBulkLoader`` y ``dump`` (``parallel_pk_ranges="auto"``), así que las reglas por motor viven en un solo sitio.

Es una función pura: no abre conexiones ni ejecuta SQL. Los hechos del entorno (capacidad del pool, privilegio ``TEMP``
de PostgreSQL) los obtiene quien llama y llegan en :class:`PlanInput`.

Dos tipos de reglas:

- **Seguridad** (modos ``"manual"`` y ``"auto"``): capacidad del pool (más hilos que conexiones lo agotan), un solo
  escritor en SQLite (PD-06: ``database is locked``) y UPDATE de PostgreSQL fila a fila, que empeora con cada hilo.
- **Rendimiento** (solo ``"auto"``): :attr:`ParallelPlanner.RULES`, con las mediciones del banco
  (``docs/guides/benchmarks.md``). Criterio: se paraleliza si la mejor aceleración medida es de al menos 1,5×, con los
  hilos del mejor tiempo (en empate, los menos), y solo desde el menor volumen medido. Una combinación sin medir va en
  serie.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import ClassVar, Literal

from ..options import ParallelOptions
from .staging_update import STAGING_UPDATE_DIALECTS

#: Origen de los datos de cada partición. ``"memory"``: ya leídos (``BulkCrud``, lectores de ``ParallelBulkLoader``);
#: ``"source"``: cada hilo lee además su rango del origen (``dump``), lo que cambia qué motores ganan.
Workload = Literal["memory", "source"]

#: Operación de la carga.
Operation = Literal["insert", "update", "delete"]

#: Motores que admiten un solo escritor a la vez: en paralelo, ``database is locked`` (PD-06).
SINGLE_WRITER_DIALECTS: frozenset[str] = frozenset({"sqlite"})


@dataclass(frozen=True, slots=True)
class ParallelRule:
    """Resultado medido de una combinación de origen de datos, motor y operación.

    Attributes:
        workers: Hilos con los que se midió el mejor tiempo; 1 si la ganancia no llega a 1,5× (en serie).
        min_rows: Menor volumen medido: por debajo no hay medición y ``"auto"`` va en serie.
        evidence: Medición que justifica la regla (aparece en ``ParallelPlan.reasons``).
    """

    workers: int
    min_rows: int
    evidence: str


def _rules() -> Mapping[tuple[Workload, str, Operation], ParallelRule]:
    """Tabla de reglas. Fuente: ``docs/guides/benchmarks.md`` («Carga paralela por particiones», «UPDATE y DELETE en
    paralelo») y ``DumpConfig.parallel_pk_ranges`` (Q4, PD-06). Al repetir los benchmarks, se actualiza aquí."""
    serial = 1
    rules: dict[tuple[Workload, str, Operation], ParallelRule] = {
        # Datos ya leídos: 1M filas con 1, 2 y 4 hilos (2026-10-01) y, en INSERT, también 200K con 1 y 4 (v0.26.0) y
        # 50K/200K con 1 y 4 (v3.0.0, sesión 2026-10-16f: BulkCrud con ParallelOptions, SQL Server con pyodbc). Oracle:
        # scripts/bench_parallel.py, 200K y 1M con 1/2/4 hilos, calentamiento y 5 tandas alternas (sesión 2026-10-16g).
        ("memory", "postgresql", "insert"): ParallelRule(
            serial, 50_000, "INSERT con psycopg 3: ≤ 1,2× con 2-4 hilos (50K-1M)"
        ),
        ("memory", "postgresql", "update"): ParallelRule(4, 1_000_000, "UPDATE 1M: 10,8 s → 6,9 s con 4 hilos (1,6×)"),
        ("memory", "postgresql", "delete"): ParallelRule(4, 1_000_000, "DELETE 1M: 1,8 s → 0,9 s con 4 hilos (2,0×)"),
        ("memory", "mysql", "insert"): ParallelRule(4, 50_000, "INSERT 50K-1M: 1,7-1,8× con 4 hilos"),
        ("memory", "mysql", "update"): ParallelRule(4, 1_000_000, "UPDATE 1M: 24,1 s → 12,9 s con 4 hilos (1,9×)"),
        ("memory", "mysql", "delete"): ParallelRule(2, 1_000_000, "DELETE 1M: 7,2 s → 4,3 s con 2 hilos (1,7×)"),
        ("memory", "mariadb", "insert"): ParallelRule(4, 50_000, "INSERT 50K-1M: 1,6-2,0× con 4 hilos"),
        ("memory", "mariadb", "update"): ParallelRule(4, 1_000_000, "UPDATE 1M: 22,2 s → 12,6 s con 4 hilos (1,8×)"),
        ("memory", "mariadb", "delete"): ParallelRule(2, 1_000_000, "DELETE 1M: 6,9 s → 4,5 s con 2 hilos (1,5×)"),
        ("memory", "mssql", "insert"): ParallelRule(4, 50_000, "INSERT 50K-1M: 2,4-2,8× con 4 hilos"),
        ("memory", "mssql", "update"): ParallelRule(4, 1_000_000, "UPDATE 1M: 22,8 s → 8,2 s con 4 hilos (2,8×)"),
        ("memory", "mssql", "delete"): ParallelRule(4, 1_000_000, "DELETE 1M: 3,0 s → 1,2 s con 4 hilos (2,5×)"),
        ("memory", "oracle", "insert"): ParallelRule(
            serial, 50_000, "INSERT 200K-1M: 0,94-1,04× con 2-4 hilos (5 tandas alternas, Oracle 23 Free)"
        ),
        ("memory", "oracle", "update"): ParallelRule(
            serial, 1_000_000, "UPDATE 200K-1M: 0,95-1,04× con 2-4 hilos (5 tandas alternas, Oracle 23 Free)"
        ),
        ("memory", "oracle", "delete"): ParallelRule(
            serial, 1_000_000, "DELETE 200K-1M: 1,13-1,15× con 2 hilos, ≤ 1× con 4 (5 tandas alternas, Oracle 23 Free)"
        ),
        # Cada hilo lee su rango del origen (dump, 4 rangos a 3,5M filas frente a la carga que ya solapa lectura y
        # escritura).
        ("source", "mssql", "insert"): ParallelRule(4, 3_500_000, "volcado 3,5M con 4 rangos: −37 % (1,6×)"),
        ("source", "postgresql", "insert"): ParallelRule(serial, 3_500_000, "volcado 3,5M con 4 rangos: −9 % (1,1×)"),
        ("source", "oracle", "insert"): ParallelRule(serial, 3_500_000, "volcado 3,5M con 4 rangos: −2 %"),
        ("source", "mysql", "insert"): ParallelRule(serial, 3_500_000, "volcado 3,5M con 4 rangos: +84 % a +94 %"),
        ("source", "mariadb", "insert"): ParallelRule(serial, 3_500_000, "volcado 3,5M con 4 rangos: +84 % a +94 %"),
    }
    return MappingProxyType(rules)


@dataclass(frozen=True, slots=True, kw_only=True)
class PlanInput:
    """Hechos de una carga que el planificador necesita.

    Attributes:
        dialect: ``engine.dialect.name`` del destino.
        operation: ``"insert"``, ``"update"`` o ``"delete"``.
        options: :class:`ParallelOptions` pedidas.
        rows: Filas de la carga (o una cota, p. ej. el rango de la PK en ``dump``). ``None``: desconocidas.
        partitions: Particiones ya hechas por quien llama (lectores de ``ParallelBulkLoader``): tope de los hilos.
        pool_capacity: Conexiones que el pool puede dar a la vez (``pool_size + max_overflow``). ``None``: sin límite
            conocido.
        staging_update: En MySQL/MariaDB y PostgreSQL, el UPDATE irá por tabla temporal (``update_via_staging`` y, en
            PostgreSQL, privilegio ``TEMP``). Se ignora en el resto de motores, que no la usan.
        workload: Origen de los datos de cada partición (:data:`Workload`).
        periodic_commits: La carga confirma cada N lotes (``BatchOptions.commit_every_n_chunks``): no es atómica ni en
            un hilo (v4.5.0, :attr:`ParallelPlan.atomic`).
    """

    dialect: str
    operation: Operation
    options: ParallelOptions
    rows: int | None = None
    partitions: int | None = None
    pool_capacity: int | None = None
    staging_update: bool = True
    workload: Workload = "memory"
    periodic_commits: bool = False


@dataclass(frozen=True, slots=True)
class ParallelPlan:
    """Decisión del planificador.

    Attributes:
        workers: Hilos (y particiones, en ``BulkCrud`` y ``dump``) que usar; 1 = en serie.
        reasons: Por qué se recortaron los hilos pedidos o en qué medición se basa la decisión, en orden.
        atomic: ``True`` si la carga va en una sola transacción: un hilo, una partición y sin ``commit_every_n_chunks``
            (v4.5.0, G36 de util_bbdd_web). Con más de un hilo cada partición es una transacción y, si una falla, las
            demás quedan confirmadas. Con ``ParallelBulkLoader`` y varias particiones tampoco lo es en un hilo. Lo
            calcula :meth:`ParallelPlanner.plan`; un plan construido a mano es ``False`` salvo que se indique.
    """

    workers: int
    reasons: tuple[str, ...] = ()
    atomic: bool = False

    @property
    def parallel(self) -> bool:
        """``True`` si se usa más de un hilo."""
        return self.workers > 1


class ParallelPlanner:
    """Decide los hilos de una carga paralela a partir de las opciones pedidas, el motor, la operación y el volumen.

    Examples:
        >>> from util_bbdd.bulk.options import ParallelOptions
        >>> plan = ParallelPlanner.plan(
        ...     PlanInput(dialect="mssql", operation="insert", rows=2_000_000, options=ParallelOptions(mode="auto"))
        ... )
        >>> plan.workers
        4
        >>> ParallelPlanner.plan(
        ...     PlanInput(dialect="postgresql", operation="insert", rows=2_000_000, options=ParallelOptions(mode="auto"))
        ... ).workers
        1
    """

    #: Reglas de rendimiento por (origen de los datos, motor, operación); ver el docstring del módulo.
    RULES: ClassVar[Mapping[tuple[Workload, str, Operation], ParallelRule]] = _rules()

    @classmethod
    def rule(cls, workload: Workload, dialect: str, operation: Operation) -> ParallelRule | None:
        """Regla medida de la combinación, o ``None`` si no se ha medido.

        Args:
            workload: Origen de los datos de la carga.
            dialect: Motor de destino (nombre de dialecto de SQLAlchemy).
            operation: Operación de la carga.
        """
        return cls.RULES.get((workload, dialect, operation))

    @classmethod
    def plan(cls, facts: PlanInput) -> ParallelPlan:
        """Hilos de la carga descrita por ``facts``: las reglas de seguridad y, en ``"auto"``, las de rendimiento.

        Args:
            facts: Datos de la carga (opciones, motor, operación, filas, particiones y capacidad del pool).

        Returns:
            Número de hilos, motivos de cada recorte y si la carga es atómica (:attr:`ParallelPlan.atomic`).
        """
        plan = cls._plan_workers(facts)
        atomic: bool = plan.workers == 1 and (facts.partitions or 1) <= 1 and not facts.periodic_commits
        return replace(plan, atomic=atomic)

    @classmethod
    def _plan_workers(cls, facts: PlanInput) -> ParallelPlan:
        """Hilos y motivos de :meth:`plan`, sin :attr:`ParallelPlan.atomic`."""
        options = facts.options
        if options.require_atomic:
            return ParallelPlan(1, ("require_atomic=True: en serie, en una transacción",))
        if options.mode == "off":
            return ParallelPlan(1, ("mode='off': en serie",))
        workers: int = options.max_workers
        if facts.partitions is not None:
            workers = min(workers, max(1, facts.partitions))
        if facts.rows is not None:
            workers = min(workers, max(1, facts.rows))
        blocked = cls._unsafe(facts)
        if blocked is not None:
            return ParallelPlan(1, (blocked,))
        reasons: list[str] = []
        if facts.pool_capacity is not None and facts.pool_capacity < workers:
            workers = max(1, facts.pool_capacity)
            reasons.append(f"{workers} hilos: capacidad del pool (pool_size + max_overflow)")
        if options.mode == "auto" and workers > 1:
            return cls._measured(facts, workers, reasons)
        return ParallelPlan(workers, tuple(reasons))

    @staticmethod
    def _unsafe(facts: PlanInput) -> str | None:
        """Motivo por el que la carga debe ir en serie en cualquier modo, o ``None``."""
        if facts.dialect in SINGLE_WRITER_DIALECTS:
            return f"{facts.dialect} admite un solo escritor a la vez: en serie"
        if facts.operation == "update" and facts.dialect == "postgresql" and not facts.staging_update:
            return (
                "PostgreSQL sin UPDATE por tabla temporal (sin privilegio TEMP o update_via_staging=False): fila a fila "
                "en paralelo es más lento que en serie (1M: 25,7 s con 1 hilo, 56,8 s con 4); concede TEMP sobre la "
                "base de datos para usar varios hilos"
            )
        return None

    @classmethod
    def _measured(cls, facts: PlanInput, workers: int, reasons: list[str]) -> ParallelPlan:
        """Aplica la regla medida de la combinación (modo ``"auto"``) a ``workers`` hilos."""
        where = f"{facts.operation.upper()} en {facts.dialect}"
        rule = cls.rule(facts.workload, facts.dialect, facts.operation)
        if rule is None:
            return ParallelPlan(1, (*reasons, f"{where}: sin medición, en serie"))
        if rule.workers <= 1:
            return ParallelPlan(1, (*reasons, f"{where}: no gana en paralelo ({rule.evidence})"))
        if facts.operation == "update" and facts.dialect in STAGING_UPDATE_DIALECTS and not facts.staging_update:
            return ParallelPlan(1, (*reasons, f"{where}: medido con UPDATE por tabla temporal; sin ella, en serie"))
        threshold: int = facts.options.min_rows or rule.min_rows
        if facts.rows is None:
            reasons.append("volumen desconocido: no se aplica el umbral de filas")
        elif facts.rows < threshold:
            return ParallelPlan(1, (*reasons, f"{where}: {facts.rows} filas < {threshold} (menor volumen medido)"))
        if rule.workers < workers:
            workers = rule.workers
            reasons.append(f"{where}: {workers} hilos, el mejor tiempo medido ({rule.evidence})")
        else:
            reasons.append(f"{where}: {rule.evidence}")
        return ParallelPlan(workers, tuple(reasons))


__all__: list[str] = [
    "SINGLE_WRITER_DIALECTS",
    "Operation",
    "ParallelPlan",
    "ParallelPlanner",
    "ParallelRule",
    "PlanInput",
    "Workload",
]
