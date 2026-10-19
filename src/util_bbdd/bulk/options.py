"""Paquetes de opciones de ``BulkCrud`` y ``ParallelBulkLoader`` (v3.0.0).

Hasta v2.x ``BulkCrud`` recibía 16 parámetros sueltos y ``ParallelBulkLoader`` 17, y quien creaba ``BulkCrud`` por su
cuenta (los workers del loader, ``dump``) copiaba la lista a mano: los workers no recibían ``insert_resolver`` ni
``update_via_staging``. Desde 3.0.0 los dos reciben los mismos paquetes inmutables, validados al construirse, y los
workers se crean con :meth:`BulkOptions.for_worker`. Equivalencias 2.x → 3.0: ``docs/guides/api_3_0_migration.md``.

Examples:
    >>> from util_bbdd.bulk.options import AuditOptions, BatchOptions, ParallelOptions
    >>> crud = BulkCrud(  # doctest: +SKIP
    ...     engine,
    ...     batch=BatchOptions(commit_every_n_chunks=20),
    ...     audit=AuditOptions(csv_path="audit.csv"),
    ...     parallel=ParallelOptions(mode="auto"),
    ... )
"""

from __future__ import annotations

import math

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from .._core.validation import OptionalPathField
from ..audit.contracts import AuditSink
from ._execution.batch import InsertStrategyResolver, validate_chunk_size
from ._support.rejects import optional_non_negative_int, validate_isolation
from ._support.retry import is_retriable
from ._support.secondary_indexes import IndexMode, resolve_index_mode

#: Modo de ejecución paralela: ``"off"`` en serie, ``"manual"`` los hilos pedidos (solo con los límites de seguridad),
#: ``"auto"`` los que decide :class:`~util_bbdd.bulk.ParallelPlanner` con las mediciones del banco.
ParallelMode = Literal["off", "manual", "auto"]

_PARALLEL_MODES: tuple[str, ...] = ("off", "manual", "auto")


def _positive_int(value: Any, name: str) -> int:
    """``value`` si es un entero ≥ 1 (no ``bool``); si no, ``ValueError``."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} debe ser un entero ≥ 1, recibido: {value!r}")
    return int(value)


@dataclass(frozen=True, kw_only=True)
class BatchOptions:
    """Tamaño de lote, cadencia de commits y preparación anticipada de lotes.

    Attributes:
        chunk_size: Filas por lote. ``None`` (default) elige el lote por motor y operación: 20 000 en el INSERT y el
            DELETE de PostgreSQL y en el DELETE de SQL Server, 5000 en el resto (B-04). Con ``commit_every_n_chunks`` el
            default es 5000 en todas las operaciones. Un entero se usa en todas las operaciones.
        commit_every_n_chunks: Commit cada N lotes en lugar de una sola transacción (**crítico en MySQL/MariaDB** con
            millones de filas: acota el undo log). ``None`` (default): una transacción, atómica. Con la cadencia, un fallo
            a mitad deja confirmados los lotes anteriores.
        prefetch_blocks: Prepara el lote siguiente de INSERT y UPDATE en un hilo mientras se envía el actual (SQL Server
            INSERT −10,6 %, UPDATE −6,2 %; MySQL/MariaDB −2 % a −6 %). En una carga paralela añade un hilo por worker.

    Raises:
        ValueError: Si ``chunk_size`` no es ``None`` ni un entero ≥ 1, o ``commit_every_n_chunks`` tampoco.
    """

    chunk_size: int | None = None
    commit_every_n_chunks: int | None = None
    prefetch_blocks: bool = False

    def __post_init__(self) -> None:
        if self.chunk_size is not None:
            validate_chunk_size(self.chunk_size)
        every = self.commit_every_n_chunks
        if every is not None and (isinstance(every, bool) or not isinstance(every, int) or every < 1):
            raise ValueError(f"commit_every_n_chunks debe ser None o un entero ≥ 1, recibido: {every}")


@dataclass(frozen=True, kw_only=True)
class AuditOptions:
    """Auditoría de las operaciones: CSV heredado y eventos (:mod:`util_bbdd.audit`).

    Attributes:
        csv_path: CSV de auditoría (``str`` o ``Path``; se lee como ``Path``). ``None`` (default): sin CSV. Las
            escrituras de varios hilos al mismo CSV se serializan con un lock por ruta.
        strict: Con ``False`` (default) un fallo al escribir la auditoría no hace fallar la operación (se registra como
            ERROR y se cuenta en ``audit_failures``). Con ``True`` se propaga; dentro de una sesión, la auditoría se
            escribe antes del commit y el fallo la deshace.
        sink: Destino opcional de eventos (p. ej. ``JsonLinesAuditSink``), con la misma política de fallo que ``strict``.
            Se puede usar sin ``csv_path``.
        run_id: ``run_id`` de los eventos. ``None``: uno nuevo por instancia (o por carga paralela) si hay ``sink``.
        warn_if_disabled: Sin ``csv_path`` ni ``sink``, avisa una vez con un WARNING. Quien crea muchas instancias (los
            workers de ``ParallelBulkLoader``, ``dump``) lo desactiva y avisa una sola vez.

    Raises:
        ValueError: Si ``csv_path`` no es ``None``, ``str`` ni ``Path``.
    """

    csv_path: OptionalPathField = OptionalPathField(label="audit.csv_path")
    strict: bool = False
    sink: AuditSink | None = None
    run_id: str | None = None
    warn_if_disabled: bool = True

    @property
    def enabled(self) -> bool:
        """``True`` si hay CSV o destino de eventos."""
        return self.csv_path is not None or self.sink is not None


@dataclass(frozen=True, kw_only=True)
class RejectOptions:
    """Qué hacer con las filas que el destino no admite (PK duplicada, NOT NULL, valor demasiado largo...).

    Attributes:
        on_error: ``"raise"`` (default): un error de datos hace fallar la operación. ``"isolate"``: cada lote se envía
            en un SAVEPOINT; si falla con un error de datos se reenvía por mitades hasta aislar las filas malas, que se
            escriben en ``csv_path``, y el resto se aplica.
        csv_path: CSV de rechazos (``str`` o ``Path``). Obligatorio con ``"isolate"``; contiene datos de las filas.
        max_rejects: Filas que una operación (o una partición) puede rechazar; la siguiente la hace fallar. ``None``:
            sin límite.

    Raises:
        ValueError: Si ``on_error`` no es ``"raise"`` ni ``"isolate"``, ``"isolate"`` no lleva ``csv_path``, ``csv_path``
            o ``max_rejects`` se indican con ``"raise"``, o ``max_rejects`` no es ``None`` ni un entero ≥ 0.
    """

    on_error: Literal["raise", "isolate"] = "raise"
    csv_path: OptionalPathField = OptionalPathField(label="rejects.csv_path")
    max_rejects: int | None = None

    def __post_init__(self) -> None:
        validate_isolation(self.on_error, self.csv_path, self.max_rejects)
        optional_non_negative_int(self.max_rejects, "max_rejects")


@dataclass(frozen=True, kw_only=True)
class ExecutionOptions:
    """Vía de ejecución por motor y tratamiento de los datos antes de enviarlos.

    Attributes:
        fast_executemany: Con ``mssql+pyodbc``, activa ``fast_executemany`` en el dialecto del engine (afecta a todo el
            engine; INSERT ~12× más rápido con ODBC Driver 18). Default ``True``.
        insert_resolver: Estrategia INSERT propia. ``None``: la resolución automática por motor y driver. En una carga
            paralela la misma instancia se comparte entre hilos: debe ser thread-safe (las estrategias incluidas no
            guardan estado por ejecución).
        update_via_staging: MySQL/MariaDB y PostgreSQL: el UPDATE carga cada lote en una tabla temporal y aplica un único
            ``UPDATE`` con join (MySQL/MariaDB ~12,5×, PostgreSQL 2,35×). Sin el privilegio, WARNING y fila a fila.
        strip_strings: Quita los espacios de los extremos de las cadenas. ``dump`` lo desactiva (copia fiel, PD-05).
        reflect_foreign_keys: La reflexión de la tabla destino lee sus FK. ``BulkCrud`` no las usa: con ``False`` la
            reflexión es más barata (``dump``, Q9).
    """

    fast_executemany: bool = True
    insert_resolver: InsertStrategyResolver | None = None
    update_via_staging: bool = True
    strip_strings: bool = True
    reflect_foreign_keys: bool = True


@dataclass(frozen=True, kw_only=True)
class RetryOptions:
    """Reintentos de una partición de una carga paralela ante errores transitorios.

    Attributes:
        max_retries: Reintentos por partición. Por defecto se decide por el código del error (``is_retriable``):
            desconexiones, deadlocks, lock wait timeouts, serialización y timeouts. UPDATE y DELETE reintentan al menos 2
            veces aunque sea 0 (son idempotentes por PK; InnoDB da deadlock en la frontera de particiones contiguas).
        backoff: ``(base, máximo)`` en segundos: antes de cada reintento se espera un valor aleatorio entre 0 y
            ``min(máximo, base · 2**(intento − 1))``. ``(0, 0)`` reintenta sin esperar.
        retry_on: Criterio propio de reintento (recibe la excepción). ``None``: ``is_retriable``.

    Raises:
        ValueError: Si ``max_retries`` no es un entero ≥ 0 o ``backoff`` no son dos números finitos ≥ 0.
    """

    max_retries: int = 0
    backoff: tuple[float, float] = (0.5, 30.0)
    retry_on: Callable[[BaseException], bool] | None = None

    def __post_init__(self) -> None:
        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int) or self.max_retries < 0:
            raise ValueError(f"max_retries debe ser un entero ≥ 0, recibido: {self.max_retries!r}")
        if len(self.backoff) != 2 or not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
            for value in self.backoff
        ):
            raise ValueError(f"backoff debe ser (base, máximo) con números finitos ≥ 0, recibido: {self.backoff!r}")
        object.__setattr__(self, "backoff", (float(self.backoff[0]), float(self.backoff[1])))

    def should_retry(self, exc: BaseException) -> bool:
        """``True`` si ``exc`` se reintenta (``retry_on`` o, sin él, ``is_retriable``)."""
        return (self.retry_on or is_retriable)(exc)


@dataclass(frozen=True, kw_only=True)
class ParallelOptions:
    """Ejecución paralela por particiones disjuntas, una ``BulkCrud`` y una conexión por hilo.

    En ``BulkCrud`` la carga paralela **deja de ser atómica**: cada partición es una transacción, y si alguna falla las
    demás quedan confirmadas (``ParallelLoadError``). Por eso ``BulkCrud`` no la usa salvo que se le pase este paquete.

    Attributes:
        mode: ``"manual"`` (default): ``max_workers`` hilos, recortados solo por los límites de seguridad (capacidad del
            pool, un solo escritor en SQLite, UPDATE de PostgreSQL sin privilegio ``TEMP``). ``"auto"``: además, las
            reglas medidas por motor y operación de :class:`~util_bbdd.bulk.ParallelPlanner` (en serie donde no ganan
            o no se han medido). ``"off"``: en serie.
        max_workers: Hilos como máximo (en ``"auto"``, tope de lo que decide el planificador). Default 4.
        partition_column: Columna por la que particionar un DataFrame en ``BulkCrud`` (UPDATE y DELETE). ``None``: la PK.
        min_rows: En ``"auto"``, filas mínimas para paralelizar. ``None`` (default): el menor volumen medido de cada
            regla (por debajo no hay medición).
        disable_constraints: Solo INSERT de ``ParallelBulkLoader``: desactiva las constraints de la tabla durante la
            carga (en SQL Server, PostgreSQL y Oracle una vez, antes de lanzar los hilos). Requiere permisos DDL.
        disable_indexes: Solo INSERT de ``ParallelBulkLoader`` (v3.2.0): ``True`` o ``"secondary"`` desactiva una vez,
            antes de lanzar los hilos, los índices secundarios no únicos de la tabla y los reconstruye al terminar
            (misma estrategia que ``DumpConfig.manage_indexes``; resultados en ``ParallelLoadResult.index_results``).
            Medido con 4 hilos y 1M filas: SQL Server −33 %, Oracle −82 % y MySQL −4 % a −6 % de tiempo total; en
            PostgreSQL (+3 %) y MariaDB (+11 %) fue **más lento** (se aplica igualmente y se avisa). Requiere permisos DDL.
            ``"all"`` (v3.3.0): además, índices únicos y PK/UNIQUE con sus FK entrantes (ver
            ``BulkCrud.maintenance_scope``); exige ``disable_constraints=True`` y lanza ``IndexRebuildError`` si un
            único no se reconstruye. Con 4 hilos solo compensa en SQL Server y Oracle.
        retry: Reintentos por partición (:class:`RetryOptions`).

    Raises:
        ValueError: Si ``mode`` no es ``"off"``, ``"manual"`` ni ``"auto"``, ``max_workers`` no es un entero ≥ 1 o
            ``min_rows`` no es ``None`` ni un entero ≥ 1, o ``disable_indexes`` no es ``bool``, ``"secondary"`` ni
            ``"all"`` (o es ``"all"`` sin ``disable_constraints``).
    """

    mode: ParallelMode = "manual"
    max_workers: int = 4
    partition_column: str | None = None
    min_rows: int | None = None
    disable_constraints: bool = False
    disable_indexes: bool | IndexMode = False
    retry: RetryOptions = field(default_factory=RetryOptions)

    def __post_init__(self) -> None:
        if self.mode not in _PARALLEL_MODES:
            raise ValueError(f"mode debe ser 'off', 'manual' o 'auto', recibido: {self.mode!r}")
        _positive_int(self.max_workers, "max_workers")
        if self.min_rows is not None:
            _positive_int(self.min_rows, "min_rows")
        if resolve_index_mode(self.disable_indexes, "disable_indexes") == "all" and not self.disable_constraints:
            raise ValueError("ParallelOptions(disable_indexes='all') exige disable_constraints=True.")


@dataclass(frozen=True, kw_only=True)
class BulkOptions:
    """Todos los paquetes de una ``BulkCrud`` o un ``ParallelBulkLoader``: lo que comparten con sus workers.

    ``BulkCrud(engine, **options.as_kwargs())`` crea una instancia con estas opciones.
    """

    batch: BatchOptions = field(default_factory=BatchOptions)
    # lambda y no la clase: pyright no acepta como Callable[[], T] un dataclass con un campo descriptor (csv_path),
    # porque toma la instancia del descriptor como default del __init__ y no encaja con el tipo de su __set__.
    audit: AuditOptions = field(default_factory=lambda: AuditOptions())
    rejects: RejectOptions = field(default_factory=lambda: RejectOptions())
    execution: ExecutionOptions = field(default_factory=ExecutionOptions)
    parallel: ParallelOptions | None = None

    def __post_init__(self) -> None:
        # F2 del AUDIT_PLAN (sesión 2026-10-18b): con disable_indexes="all" los duplicados no dan error que apartar.
        if self.parallel is not None and self.parallel.disable_indexes == "all" and self.rejects.on_error == "isolate":
            raise ValueError("ParallelOptions(disable_indexes='all') no admite RejectOptions(on_error='isolate').")

    @classmethod
    def of(
        cls,
        *,
        batch: BatchOptions | None = None,
        audit: AuditOptions | None = None,
        rejects: RejectOptions | None = None,
        execution: ExecutionOptions | None = None,
        parallel: ParallelOptions | None = None,
    ) -> BulkOptions:
        """``BulkOptions`` con los paquetes recibidos y los de por defecto en los ``None`` (salvo ``parallel``)."""
        return cls(
            batch=batch or BatchOptions(),
            audit=audit or AuditOptions(),
            rejects=rejects or RejectOptions(),
            execution=execution or ExecutionOptions(),
            parallel=parallel,
        )

    def for_worker(self, *, run_id: str | None) -> BulkOptions:
        """Opciones de la ``BulkCrud`` de una partición: sin ``parallel`` (un worker no vuelve a paralelizar), sin aviso
        de auditoría deshabilitada (lo da quien reparte, una vez) y con el ``run_id`` común de la carga."""
        # S5886 es un falso positivo: replace() devuelve el tipo de su argumento (BulkOptions), no DataclassInstance.
        return replace(self, audit=replace(self.audit, warn_if_disabled=False, run_id=run_id), parallel=None)  # NOSONAR

    def as_kwargs(self) -> dict[str, Any]:
        """Los paquetes como argumentos de ``BulkCrud`` o ``ParallelBulkLoader``."""
        return {
            "batch": self.batch,
            "audit": self.audit,
            "rejects": self.rejects,
            "execution": self.execution,
            "parallel": self.parallel,
        }


__all__: list[str] = [
    "AuditOptions",
    "BatchOptions",
    "BulkOptions",
    "ExecutionOptions",
    "ParallelMode",
    "ParallelOptions",
    "RejectOptions",
    "RetryOptions",
]
