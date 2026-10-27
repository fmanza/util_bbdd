"""Carga masiva paralela por particiones.

``ParallelBulkLoader`` ejecuta la inserción de varias particiones de datos en
paralelo, una ``BulkCrud`` por hilo. Es un **mecanismo** agnóstico del origen: cada
partición se describe mediante un *lector* (``Callable[[], Iterable[DataFrame]]``)
que produce los chunks ya listos para insertar; el llamador decide de dónde salen
(p.ej. ``pandas.read_sql`` con un ``WHERE pk BETWEEN`` por rango).

Las particiones deben ser **disjuntas** (p.ej. rangos de PK no solapados) para que
los inserts concurrentes en la misma tabla no colisionen. El motor de inserción
(batching, ``commit_every_n_chunks``, estrategias por dialecto, auditoría
thread-safe) lo aporta cada ``BulkCrud`` worker vía ``bulk_insert_from_chunks``
(``disable_constraints=False``) o ``bulk_session`` + ``maintenance_scope``
(``disable_constraints=True``).

v3.0.0: recibe los mismos paquetes de opciones que ``BulkCrud`` (:mod:`util_bbdd.bulk.options`) y crea cada worker con
:meth:`BulkOptions.for_worker`; los hilos de cada carga los decide :class:`ParallelPlanner` (``ParallelOptions.mode``).
"""

from __future__ import annotations

import contextlib
import logging
import random
import time
import uuid

from collections.abc import Callable, Generator, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import ClassVar, Literal

import pandas as pd

from sqlalchemy import Engine, Table, text
from sqlalchemy.exc import SQLAlchemyError

from ...metadata import facts
from .._audit.counters import AuditCounters
from .._audit.errors import AuditError
from .._audit.events import BulkAuditEvents
from .._models import IndexActionResult
from .._support.dialect import can_disable_pg_triggers, disable_table_integrity_sql, enable_table_integrity_sql
from .._support.iterables import closing_iterable, skip_rows as skip_leading_rows
from .._support.pool import pool_capacity
from .._support.secondary_indexes import (
    SUPPORTED_DIALECTS,
    IndexDdlRunner,
    IndexMode,
    SecondaryIndexPlanner,
    rebuild_error,
    resolve_index_mode,
)
from ..audit import AuditManager
from ..crud import BulkCrud
from ..options import (
    AuditOptions,
    BatchOptions,
    BulkOptions,
    ExecutionOptions,
    ParallelOptions,
    RejectOptions,
    RetryOptions,
)
from .maintenance import TableMaintenance
from .parallel_planner import ParallelPlan, ParallelPlanner, PlanInput
from .range_partitioner import RangePartitioner

# Un lector de partición: invocado en su hilo worker, produce los chunks a insertar, actualizar o borrar.
PartitionReader = Callable[[], Iterable[pd.DataFrame]]

# Operación de una carga paralela: load() → insert, update() → update, delete() → delete.
_Operation = Literal["insert", "update", "delete"]


@dataclass
class PartitionResult:
    """Resultado de una partición individual dentro de una carga paralela.

    Attributes:
        index: Índice de la partición (0-based, orden del ``partition_readers``).
        rows: Filas insertadas correctamente en esta partición. Si la partición
            falló a mitad con ``commit_every_n_chunks`` activo, refleja las filas
            ya comprometidas en BD antes del fallo (no necesariamente 0) —
            ver ``BulkCrud.rows_committed``.
        elapsed_seconds: Tiempo de carga de la partición en segundos.
        error: Mensaje de error si la partición falló; ``None`` si tuvo éxito.
        retries: Número de reintentos realizados (0 si tuvo éxito en el primer intento).
        audit_failures: Registros de auditoría de esta partición que no se pudieron escribir en el CSV (solo con
            ``audit_strict=False``; ver ``BulkCrud.audit_failures``).
        audited_rows: Filas de esta partición que constan en el CSV de auditoría (ver ``BulkCrud.audited_rows``).
        unaudited_committed_rows: Filas confirmadas por commits periódicos que no constan en el CSV porque la partición
            falló a mitad de una operación (``commit_every_n_chunks``; ver ``BulkCrud.unaudited_committed_rows``).
        audit_uncommitted_records: Registros escritos en el CSV antes de un commit que falló (``audit_strict=True``;
            ver ``BulkCrud.audit_uncommitted_records``). Si es > 0 la partición no se reintenta.
        retry_wait_seconds: Segundos esperados entre intentos (``retry_backoff``); 0.0 sin reintentos.
        rows_rejected: Filas de esta partición escritas en el CSV de rechazos (``on_error="isolate"``). Cuentan en
            ``rows`` (posiciones de la partición), no en la BD ni en la auditoría. Si la partición falló, incluye los
            rechazos del intento que se deshizo (siguen en el CSV aunque ``rows`` no cuente esas posiciones).
    """

    index: int
    rows: int
    elapsed_seconds: float
    error: str | None = None
    retries: int = 0
    audit_failures: int = 0
    audited_rows: int = 0
    unaudited_committed_rows: int = 0
    audit_uncommitted_records: int = 0
    retry_wait_seconds: float = 0.0
    rows_rejected: int = 0


@dataclass
class ParallelLoadResult:
    """Resultado agregado de una carga paralela por particiones.

    Attributes:
        total_rows: Filas totales insertadas en todas las particiones.
        partition_errors: Mensajes de error de particiones fallidas (best-effort).
        elapsed_seconds: Tiempo total de la carga (wall-clock, incluye sincronización).
        partition_results: Resultados individuales por partición.

    Properties:
        rows_per_second: Throughput global (filas/s). 0.0 si ``elapsed_seconds`` ≤ 0.
        audit_failures: Registros de auditoría que no se pudieron escribir, sumados de todas las particiones.
        audited_rows: Filas que constan en el CSV de auditoría, sumadas de todas las particiones.
        unaudited_committed_rows: Filas confirmadas que no constan en el CSV (``commit_every_n_chunks`` con fallo).
        audit_uncommitted_records: Registros escritos en el CSV antes de un commit que falló (``audit_strict``).
        rows_rejected: Filas apartadas al CSV de rechazos, sumadas de todas las particiones (``on_error="isolate"``).

    Conciliación: con auditoría activa, ``audit_failures == 0``, ``audit_uncommitted_records == 0`` y **sin
    ``partition_errors``**, se cumple ``audited_rows + rows_rejected + unaudited_committed_rows == total_rows``. Una
    partición fallida no suma a ``total_rows`` lo deshecho, pero los rechazos que ya escribió siguen en el CSV y en
    ``rows_rejected`` (M-1, audit-code 2026-10-01).

    ``audit_run_id``: ``run_id`` de los eventos de ``audit.sink`` de la carga (``None`` sin destino).

    ``plan``: hilos usados y por qué (:class:`ParallelPlan`, v3.0.0); ``None`` si no había particiones.

    ``index_results``: con ``ParallelOptions(disable_indexes=...)`` (v3.2.0), un :class:`IndexActionResult` por índice
    desactivado antes de lanzar los hilos y reconstruido al terminar.
    """

    total_rows: int = 0
    partition_errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    partition_results: list[PartitionResult] = field(default_factory=list)
    audit_run_id: str | None = None
    plan: ParallelPlan | None = None
    index_results: list[IndexActionResult] = field(default_factory=list)

    @property
    def audit_failures(self) -> int:
        """Registros de auditoría perdidos en toda la carga (suma de ``PartitionResult.audit_failures``)."""
        return sum(pr.audit_failures for pr in self.partition_results)

    @property
    def audited_rows(self) -> int:
        """Filas que constan en el CSV de auditoría (suma de ``PartitionResult.audited_rows``)."""
        return sum(pr.audited_rows for pr in self.partition_results)

    @property
    def unaudited_committed_rows(self) -> int:
        """Filas confirmadas que no constan en el CSV (suma de ``PartitionResult.unaudited_committed_rows``)."""
        return sum(pr.unaudited_committed_rows for pr in self.partition_results)

    @property
    def audit_uncommitted_records(self) -> int:
        """Registros del CSV sin datos en la BD (suma de ``PartitionResult.audit_uncommitted_records``)."""
        return sum(pr.audit_uncommitted_records for pr in self.partition_results)

    @property
    def rows_rejected(self) -> int:
        """Filas apartadas al CSV de rechazos (suma de ``PartitionResult.rows_rejected``)."""
        return sum(pr.rows_rejected for pr in self.partition_results)

    @property
    def rows_per_second(self) -> float:
        """Throughput global de la carga. Devuelve 0.0 si elapsed_seconds ≤ 0."""
        if self.elapsed_seconds <= 0.0:
            return 0.0
        return self.total_rows / self.elapsed_seconds


class ParallelBulkLoader:
    """Inserta, actualiza o borra particiones de datos en paralelo, una ``BulkCrud`` por hilo.

    :meth:`load` inserta; :meth:`update` y :meth:`delete` (B-05, performance-audit de bulk 2026-10-01) actualizan o
    borran. Las particiones deben ser disjuntas por PK.

    ``BulkCrud`` no es thread-safe: por eso cada partición se carga con su **propia**
    instancia ``BulkCrud`` y su propia conexión (el ``Engine`` sí es thread-safe).

    Ejemplo sin mantenimiento::

        loader = ParallelBulkLoader(engine, batch=BatchOptions(chunk_size=10_000))
        result = loader.load("dbo.orders", [reader_rango1, reader_rango2, ...])
        print(result.total_rows, result.partition_errors, result.plan.reasons)

    Ejemplo para cargas >1M filas con deshabilitación de constraints y los hilos decididos por las mediciones::

        loader = ParallelBulkLoader(
            engine,
            batch=BatchOptions(commit_every_n_chunks=20),
            parallel=ParallelOptions(mode="auto", max_workers=8, disable_constraints=True),
        )
        result = loader.load("dbo.orders", readers)
        print(
            f"{result.total_rows} filas en {result.elapsed_seconds:.1f}s "
            f"({result.rows_per_second:.0f} filas/s)"
        )
    """

    logger: ClassVar[logging.Logger] = logging.getLogger(__name__)

    #: Reintentos mínimos de update()/delete() ante errores transitorios, aunque max_retries sea 0. Son idempotentes por
    #: PK y, con particiones contiguas, InnoDB puede dar deadlock (1213) en la frontera aunque sean disjuntas: medido en el
    #: banco con MySQL 8.4, DELETE de 1M filas con 2 hilos (performance-audit de bulk 2026-10-01, R-5).
    IDEMPOTENT_MIN_RETRIES: ClassVar[int] = 2

    #: Errores de datos, de BD o de auditoría estricta habituales en una carga: se anotan sin traza en el log (el de
    #: auditoría ya lo registró BulkCrud como ERROR). El resto también se anotan en partition_errors, pero con traza,
    #: porque suelen indicar un fallo del lector o de programación.
    EXPECTED_ERRORS: ClassVar[tuple[type[Exception], ...]] = (
        SQLAlchemyError,
        ValueError,
        pd.errors.DatabaseError,
        AuditError,
    )

    def __init__(
        self,
        engine: Engine,
        *,
        batch: BatchOptions | None = None,
        audit: AuditOptions | None = None,
        rejects: RejectOptions | None = None,
        execution: ExecutionOptions | None = None,
        parallel: ParallelOptions | None = None,
    ) -> None:
        """
        v3.0.0: los mismos paquetes de opciones que ``BulkCrud`` (:mod:`util_bbdd.bulk.options`), que se pasan tal cual
        a la ``BulkCrud`` de cada partición. Hasta v2.x eran 17 parámetros sueltos y los workers no recibían
        ``insert_resolver``, ``update_via_staging`` ni ``prefetch_blocks``.

        Args:
            engine: Engine SQLAlchemy compartido entre workers (thread-safe).
            batch: Lote, cadencia y preparación anticipada de cada worker (:class:`BatchOptions`). Con
                ``commit_every_n_chunks`` y reintentos, un reintento **reanuda** la partición desde la última fila
                confirmada (``BulkCrud.rows_committed``): el lector debe devolver las filas en el mismo orden en cada
                llamada (B-11).
            audit: Auditoría (:class:`AuditOptions`), común a las particiones: el CSV es thread-safe y ``sink`` recibe
                los eventos ``operation`` de las ``BulkCrud`` y, al terminar cada carga, uno ``partition`` por partición
                y un ``run`` de cierre (un fallo al escribir estos dos últimos se registra como ERROR y no cambia el
                resultado). Con ``strict=False`` un fallo al escribir el CSV no hace fallar la partición (se cuenta en
                ``audit_failures``); con ``True`` la deshace sin reintentarla. En modo estricto, si falla el commit,
                los registros ya escritos se cuentan en ``audit_uncommitted_records`` y la partición **no se
                reintenta**, para no duplicarlos. ``run_id=None``: uno nuevo por carga si hay ``sink``.
            rejects: Como en ``BulkCrud`` (:class:`RejectOptions`): con ``"isolate"`` cada partición aparta las filas
                con errores de datos al CSV común (con su número en la columna ``particion`` y la posición dentro de la
                partición). Si un intento que ya escribió rechazos falla después, la partición **no se reintenta**
                (los duplicaría). ``max_rejects`` es por partición (con N particiones, hasta N × ``max_rejects``).
            execution: Vía de ejecución de cada worker (:class:`ExecutionOptions`).
            parallel: Hilos, modo y reintentos (:class:`ParallelOptions`; por defecto ``mode="manual"`` con 4 hilos,
                como hasta v2.x). Los hilos de cada carga los decide :class:`ParallelPlanner`: en ``"manual"``, los
                pedidos recortados por la capacidad del pool, SQLite (un solo escritor; v3.0.0) y el UPDATE de
                PostgreSQL fila a fila; en ``"auto"``, además, las reglas medidas por motor y operación; ``"off"``, uno.
                ``disable_constraints`` desactiva las constraints en :meth:`load` (en SQL Server, PostgreSQL y Oracle una vez,
                antes de lanzar los hilos; en el resto, cada worker con ``maintenance_scope``). ``disable_indexes``
                (v3.2.0) desactiva los índices secundarios una vez antes de lanzar los hilos (por worker, el lock DDL de
                SQL Server serializaba la carga). Reintentos: ``parallel.retry`` (:class:`RetryOptions`).

        Raises:
            AuditConfigError: Si no se puede crear el directorio de ``audit.csv_path`` (subclase de ``ValueError``).
            ValueError: Si ``parallel.require_atomic`` es ``True``: cada partición es una transacción (G36).
        """
        if parallel is not None and parallel.require_atomic:
            raise ValueError(
                "ParallelBulkLoader carga cada partición en su transacción: ParallelOptions(require_atomic=True) solo "
                "aplica a BulkCrud."
            )
        options = BulkOptions.of(
            batch=batch, audit=audit, rejects=rejects, execution=execution, parallel=parallel or ParallelOptions()
        )
        if options.audit.csv_path is not None:
            # PL-4 (audit-code de ParallelBulkLoader 2026-09-25): antes del pool. Si no, cada partición fallaba por
            # separado y, con disable_constraints, el hoist se hacía para nada.
            AuditManager(options.audit.csv_path)
        self._engine = engine
        self._options: BulkOptions = options
        self._parallel: ParallelOptions = options.parallel or ParallelOptions()
        # Inyectables en tests (sin esperas reales ni azar).
        self._sleep: Callable[[float], None] = time.sleep
        self._jitter: Callable[[float, float], float] = random.uniform
        self._max_workers = self._resolve_max_workers(self._parallel.max_workers)
        #: Privilegio TEMP de PostgreSQL para el plan del UPDATE (None: sin comprobar). Una consulta por instancia; la
        #: fachada paralela de BulkCrud lo pasa ya comprobado. Los workers lo vuelven a comprobar en su sesión.
        self._temp_tables_allowed: bool | None = None

    @property
    def options(self) -> BulkOptions:
        """Paquetes de opciones del loader (``parallel`` nunca es ``None``)."""
        return self._options

    @property
    def _retry(self) -> RetryOptions:
        return self._parallel.retry

    @staticmethod
    def _partition_error(index: int, exc: Exception) -> str:
        """Texto de ``partition_errors``: como antes para los errores habituales; con el tipo para el resto."""
        if isinstance(exc, ParallelBulkLoader.EXPECTED_ERRORS):
            return f"partición {index}: {exc}"
        return f"partición {index}: {type(exc).__name__}: {exc}"

    def _resolve_max_workers(self, requested: int) -> int:
        """Devuelve el número efectivo de workers, acotado a la capacidad del pool para no agotarlo.

        Cada worker retiene una conexión durante su ``bulk_session``: con más workers que conexiones, los que esperan
        una nueva agotan el pool. La capacidad es ``pool_size + max_overflow`` (:func:`pool_capacity`, la misma regla que
        ``dump``); hasta v0.17.x se usaba solo ``pool_size`` porque la ruta ``disable_constraints=True`` usaba dos
        conexiones por worker (ver :meth:`_load_with_maintenance`). Sin capacidad determinable (``NullPool``,
        ``StaticPool``, ``max_overflow`` ilimitado, mocks) se respeta ``requested``.
        """
        capacity = pool_capacity(self._engine)
        if capacity is None or capacity >= requested:
            return requested
        self.logger.warning(
            "max_workers (%d) reducido a la capacidad del pool (%d = pool_size + max_overflow) para no agotar las "
            "conexiones. Crea el engine con pool_size + max_overflow >= %d para usar más workers.",
            requested,
            capacity,
            requested,
        )
        return capacity

    def load(
        self,
        tabla_destino: str,
        partition_readers: Sequence[PartitionReader],
        *,
        partition_ranges: Sequence[tuple[int, int]] | None = None,
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> ParallelLoadResult:
        """Carga en paralelo todas las particiones en ``tabla_destino``.

        Args:
            tabla_destino: Nombre lógico de la tabla (``schema.tabla`` o ``tabla``).
            partition_readers: Lectores de partición; cada uno produce los chunks de su
                partición (disjunta respecto a las demás).
            partition_ranges: Rangos opcionales ``(lo, hi)`` (inclusivos) asociados a cada
                lector. Si se proporcionan, se valida que no se solapen antes de lanzar el
                pool. Permite detectar lectores no disjuntos que causarían colisiones en
                INSERT o deadlocks de row-level lock.
            override_identity: Propagado a cada worker (solo PostgreSQL).
            exclude_autoincrement_pk: Propagado a cada worker.

        Returns:
            ``ParallelLoadResult`` con filas totales, métricas de throughput y resultados
            individuales por partición. Best-effort: un fallo en una partición no aborta
            las demás.

        Raises:
            ValueError: Si ``partition_ranges`` se proporciona y los rangos se solapan
                o su número no coincide con el de ``partition_readers``.
        """
        return self._run(
            "insert",
            tabla_destino,
            partition_readers,
            partition_ranges=partition_ranges,
            override_identity=override_identity,
            exclude_autoincrement_pk=exclude_autoincrement_pk,
        )

    def update(
        self,
        tabla_destino: str,
        partition_readers: Sequence[PartitionReader],
        *,
        partition_ranges: Sequence[tuple[int, int]] | None = None,
    ) -> ParallelLoadResult:
        """Actualiza en paralelo: cada partición con ``BulkCrud.bulk_update_from_chunks`` en su hilo (B-05).

        Las particiones deben ser **disjuntas por PK**: dos hilos que actualizan la misma fila se bloquean entre sí
        (o se pisan). En MySQL/MariaDB y PostgreSQL cada hilo usa el UPDATE por tabla temporal; en PostgreSQL sin el
        privilegio ``TEMP`` se usa un solo hilo, porque el UPDATE fila a fila en paralelo es más lento que en serie
        (1M filas: 25,7 s con 1 hilo, 56,8 s con 4). Medido con 1M filas y 4 hilos: SQL Server 2,9×, MySQL 2,2×,
        PostgreSQL 4× frente al UPDATE en serie fila a fila. ``disable_constraints`` no aplica.

        Como UPDATE y DELETE por PK son idempotentes, los errores transitorios (deadlocks incluidos) se reintentan al
        menos 2 veces aunque ``max_retries`` sea 0: con particiones contiguas, InnoDB puede dar deadlock en la frontera
        aunque sean disjuntas (medido en MySQL 8.4).

        Args:
            tabla_destino: Nombre lógico de la tabla (``schema.tabla`` o ``tabla``).
            partition_readers: Lectores de partición con la PK y las columnas a actualizar.
            partition_ranges: Rangos ``(lo, hi)`` de PK por lector, como en :meth:`load`.

        Returns:
            ``ParallelLoadResult``; ``total_rows`` son las filas enviadas.
        """
        return self._run("update", tabla_destino, partition_readers, partition_ranges=partition_ranges)

    def delete(
        self,
        tabla_destino: str,
        partition_readers: Sequence[PartitionReader],
        *,
        partition_ranges: Sequence[tuple[int, int]] | None = None,
    ) -> ParallelLoadResult:
        """Borra en paralelo: cada partición con ``BulkCrud.bulk_delete_from_chunks`` en su hilo (B-05).

        Mismas reglas que :meth:`update`, también los 2 reintentos mínimos ante errores transitorios.
        ``disable_constraints`` no aplica.

        Args:
            tabla_destino: Nombre lógico de la tabla (``schema.tabla`` o ``tabla``).
            partition_readers: Lectores de partición con las columnas de la PK de las filas a borrar.
            partition_ranges: Rangos ``(lo, hi)`` de PK por lector, como en :meth:`load`.

        Returns:
            ``ParallelLoadResult``; ``total_rows`` son las filas enviadas.
        """
        return self._run("delete", tabla_destino, partition_readers, partition_ranges=partition_ranges)

    def _run(
        self,
        operation: _Operation,
        tabla_destino: str,
        partition_readers: Sequence[PartitionReader],
        *,
        partition_ranges: Sequence[tuple[int, int]] | None = None,
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> ParallelLoadResult:
        """Ejecuta ``operation`` en paralelo sobre las particiones (común a :meth:`load`, :meth:`update`, :meth:`delete`)."""
        if not partition_readers:
            return ParallelLoadResult()

        if partition_ranges is not None:
            RangePartitioner.validate_disjoint(partition_ranges, len(partition_readers))

        audit = self._options.audit
        if not audit.enabled and audit.warn_if_disabled:
            # M-4: un aviso por carga; las BulkCrud de las particiones se crean sin el suyo. Sin él con
            # warn_if_disabled=False (la fachada paralela de BulkCrud, que ya avisó al crearse).
            self.logger.info("Auditoría deshabilitada en la carga paralela de '%s' (sin audit).", tabla_destino)
        # Un run_id por carga (o el recibido); se pasa a cada partición, sin estado compartido entre cargas.
        run_id: str | None = None if audit.sink is None else (audit.run_id or uuid.uuid4().hex)

        plan = self._plan(operation, tabla_destino, len(partition_readers))
        result = ParallelLoadResult(audit_run_id=run_id, plan=plan)
        t_start = time.perf_counter()
        workers = plan.workers
        retries: int = self._retry.max_retries
        if operation != "insert":
            retries = max(retries, self.IDEMPOTENT_MIN_RETRIES)

        constraint_ctx = (
            self._hoist_constraints_for_workers(tabla_destino)
            if self._parallel.disable_constraints and operation == "insert"
            else contextlib.nullcontext(False)
        )
        index_mode = resolve_index_mode(self._parallel.disable_indexes, "disable_indexes")
        index_errors: list[Exception] = []
        index_ctx = (
            self._hoist_indexes_for_workers(tabla_destino, result, workers, index_mode, index_errors)
            if index_mode is not None and operation == "insert"
            else contextlib.nullcontext()
        )
        # Constraints fuera e índices dentro: se reconstruyen los índices antes de reactivar las constraints (su validación
        # los aprovecha), como en dump y en maintenance_scope.
        with constraint_ctx as skip_maintenance, index_ctx, ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    self._load_partition,
                    tabla_destino,
                    reader,
                    override_identity,
                    exclude_autoincrement_pk,
                    index,
                    skip_maintenance,
                    operation=operation,
                    max_retries=retries,
                    audit_run_id=run_id,
                )
                for index, reader in enumerate(partition_readers)
            ]
            for future in as_completed(futures):
                pr: PartitionResult = future.result()
                result.total_rows += pr.rows
                result.partition_results.append(pr)
                if pr.error is not None:
                    result.partition_errors.append(pr.error)

        result.elapsed_seconds = time.perf_counter() - t_start
        self._write_load_events(result, tabla_destino, operation)
        if index_errors:
            # IndexRebuildError ("all"): tras reactivar las constraints y escribir la auditoría de la carga.
            raise index_errors[0]
        return result

    def _write_load_events(self, result: ParallelLoadResult, tabla_destino: str, operation: str) -> None:
        """Eventos ``partition`` (en orden de partición) y ``run`` de la carga en ``audit.sink``; fallo = ERROR."""
        sink = self._options.audit.sink
        if sink is None:
            return
        engine = self._engine.dialect.name
        # Construir dentro del try (hipótesis 5 del audit-code 2026-10-02c): un fallo aquí no debe perder el resultado.
        try:
            events = [
                BulkAuditEvents.partition(
                    pr, table=tabla_destino, operation=operation, engine=engine, run_id=result.audit_run_id
                )
                for pr in sorted(result.partition_results, key=lambda pr: pr.index)
            ]
            events.extend(
                BulkAuditEvents.index(r, engine=engine, run_id=result.audit_run_id) for r in result.index_results
            )
            events.append(
                BulkAuditEvents.load(
                    result, table=tabla_destino, operation=operation, engine=engine, run_id=result.audit_run_id
                )
            )
            sink.write(events)
        except Exception as exc:
            self.logger.error(
                "❌ No se pudo escribir la auditoría de la carga paralela de '%s' en audit_sink: %s",
                tabla_destino,
                exc,
                exc_info=True,
            )

    def _plan(self, operation: _Operation, tabla_destino: str, partitions: int) -> ParallelPlan:
        """Hilos de la carga (:class:`ParallelPlanner`); si recorta los pedidos, WARNING en ``"manual"`` e INFO en ``"auto"``.

        El privilegio ``TEMP`` de PostgreSQL solo se consulta si el UPDATE iría con varios hilos.
        """
        dialect: str = self._engine.dialect.name
        requested: int = min(self._max_workers, partitions)
        # La capacidad del pool ya recortó max_workers en el constructor (_resolve_max_workers, con su WARNING).
        facts_in = PlanInput(
            dialect=dialect,
            operation=operation,
            options=replace(self._parallel, max_workers=self._max_workers),
            partitions=partitions,
            staging_update=self._options.execution.update_via_staging,
            periodic_commits=self._options.batch.commit_every_n_chunks is not None,
        )
        plan = ParallelPlanner.plan(facts_in)
        if plan.parallel and operation == "update" and facts_in.staging_update and not self._staging_update_available():
            plan = ParallelPlanner.plan(replace(facts_in, staging_update=False))
        if plan.workers < requested and self._parallel.mode != "off":  # con "off", un hilo es lo pedido
            level = logging.WARNING if self._parallel.mode == "manual" else logging.INFO
            self.logger.log(
                level,
                "Carga paralela de '%s' con %d hilos en lugar de %d: %s",
                tabla_destino,
                plan.workers,
                requested,
                "; ".join(plan.reasons),
            )
        return plan

    def _staging_update_available(self) -> bool:
        """En PostgreSQL, ``False`` si falta el privilegio ``TEMP`` (el UPDATE paralelo sería fila a fila).

        Sin él, :meth:`_plan` deja la carga en un hilo y avisa; concede ``TEMP`` sobre la base de datos para usar varios.
        Se consulta una vez por instancia (``_temp_tables_allowed``).
        """
        if self._engine.dialect.name != "postgresql":
            return True
        if self._temp_tables_allowed is None:
            with self._engine.connect() as conn:
                self._temp_tables_allowed = facts.can_create_temp_tables(conn)
        return self._temp_tables_allowed

    def _load_partition(
        self,
        tabla_destino: str,
        reader: PartitionReader,
        override_identity: bool,
        exclude_autoincrement_pk: bool,
        index: int,
        skip_maintenance: bool = False,
        *,
        operation: _Operation = "insert",
        max_retries: int | None = None,
        audit_run_id: str | None = None,
    ) -> PartitionResult:
        """Tarea de hilo: carga (o actualiza o borra, ``operation``) una partición con su propia ``BulkCrud``.

        Reintenta hasta ``max_retries`` veces los errores transitorios (``retry_on``, por defecto ``is_retriable``),
        con una espera de ``retry_backoff`` antes de cada reintento. Con ``commit_every_n_chunks`` el reintento reanuda
        la partición tras sus filas ya confirmadas (``crud.rows_committed``; 0 en modo atómico, donde el fallo deshizo
        todo). Cualquier otra excepción (integridad, sintaxis,
        validación, errores del lector de la partición…) no se reintenta y queda en el ``PartitionResult`` sin abortar
        el resto de particiones.

        Args:
            skip_maintenance: Si ``True``, omite ``maintenance_scope`` aunque
                ``disable_constraints=True``. Usado cuando MSSQL, PostgreSQL u Oracle ya
                deshabilitaron constraints globalmente antes del pool
                (``_hoist_constraints_for_workers``).
        """
        t_start = time.perf_counter()
        try:
            crud = BulkCrud(self._engine, **self._options.for_worker(run_id=audit_run_id).as_kwargs())
        except Exception as exc:
            self.logger.warning(
                "No se pudo preparar la partición %d de '%s': %s", index, tabla_destino, exc, exc_info=True
            )
            return PartitionResult(
                index=index,
                rows=0,
                elapsed_seconds=time.perf_counter() - t_start,
                error=self._partition_error(index, exc),
            )

        retries: int = self._retry.max_retries if max_retries is None else max_retries
        last_exc: Exception | None = None
        waited: float = 0.0

        for attempt in range(retries + 1):
            if attempt:
                waited += self._wait_before_retry(index, attempt)
            resume_from: int = self._resume_offset(crud, index, attempt)
            rejected_before: int = crud.rows_rejected
            try:
                # Rechazos con la partición y su posición en ella (también tras saltar lo confirmado y en la vía de
                # maintenance_scope, que carga chunk a chunk), con un presupuesto de max_rejects por intento.
                with crud.rejects_scope(partition=index, row_offset=resume_from):
                    rows = self._run_attempt(
                        crud,
                        tabla_destino,
                        reader,
                        override_identity,
                        exclude_autoincrement_pk,
                        skip_maintenance,
                        operation=operation,
                        skip_rows=resume_from,
                    )
                return self._partition_result(
                    crud, index, t_start, rows=resume_from + rows, retries=attempt, retry_wait_seconds=waited
                )

            except Exception as exc:
                stop = self._stop_retrying(
                    crud,
                    index,
                    t_start,
                    tabla_destino,
                    exc,
                    attempt=attempt,
                    waited=waited,
                    rejected_now=crud.rows_rejected - rejected_before,
                )
                if stop is not None:
                    return stop
                last_exc = exc
                if attempt < retries:
                    self.logger.warning(
                        "Partición %d intento %d/%d fallido (transitorio): %s",
                        index,
                        attempt + 1,
                        retries + 1,
                        exc,
                    )
                # continúa al siguiente intento

        # Reintentos agotados: el bucle hace al menos un intento y cada fallo transitorio fija last_exc.
        assert last_exc is not None
        self.logger.warning("Partición %d agotó %d reintentos: %s", index, retries, last_exc)
        return self._partition_result(
            crud,
            index,
            t_start,
            rows=crud.rows_committed,
            retries=retries,
            retry_wait_seconds=waited,
            error=self._partition_error(index, last_exc),
        )

    def _resume_offset(self, crud: BulkCrud, index: int, attempt: int) -> int:
        """Filas iniciales de la partición que el intento ``attempt`` no vuelve a enviar.

        B-11: las filas confirmadas por intentos anteriores (prefijo de la partición) no se vuelven a enviar. Solo con
        cadencia: en modo atómico un fallo deshace la partición entera y se reintenta desde el principio.
        """
        resume_from: int = (
            crud.rows_committed if attempt and self._options.batch.commit_every_n_chunks is not None else 0
        )
        if resume_from:
            self.logger.info("Partición %d: se reanuda tras %d filas ya confirmadas", index, resume_from)
        return resume_from

    def _stop_retrying(
        self,
        crud: BulkCrud,
        index: int,
        t_start: float,
        tabla_destino: str,
        exc: Exception,
        *,
        attempt: int,
        waited: float,
        rejected_now: int,
    ) -> PartitionResult | None:
        """Resultado final si el fallo ``exc`` del intento ``attempt`` no se reintenta; ``None`` si se puede reintentar.

        No se reintenta un error permanente (``retry_on``) ni un intento que ya dejó efectos fuera de la transacción
        (rechazos o auditoría estricta escritos), porque reintentarlo los duplicaría.
        """
        if not self._retry.should_retry(exc):
            return self._permanent_failure(crud, index, t_start, tabla_destino, exc, attempt, waited)
        detail: str | None = None
        if rejected_now > 0:
            # Fase 3 (D-2): los rechazos de este intento ya están en el CSV; reintentarlo los escribiría otra vez.
            self.logger.warning(
                "Partición %d de '%s': falló tras escribir %d rechazos; no se reintenta para no duplicarlos: %s",
                index,
                tabla_destino,
                rejected_now,
                exc,
            )
            detail = (
                f"el CSV de rechazos contiene {rejected_now} filas de este intento; reintentar la partición las "
                "duplicaría"
            )
        elif crud.audit_uncommitted_records > 0:
            # PL-2 (audit-code de ParallelBulkLoader 2026-09-25): con audit_strict falló el commit después de
            # escribir la auditoría. Reintentar la escribiría otra vez: el CSV contaría el doble que la BD.
            self.logger.warning(
                "Partición %d de '%s': falló el commit con la auditoría estricta ya escrita; no se reintenta "
                "para no duplicarla: %s",
                index,
                tabla_destino,
                exc,
            )
            detail = (
                f"el CSV de auditoría contiene {crud.audit_uncommitted_records} registros de este intento sin datos "
                "en la BD"
            )
        if detail is None:
            return None
        return self._partition_result(
            crud,
            index,
            t_start,
            rows=crud.rows_committed,
            retries=attempt,
            retry_wait_seconds=waited,
            error=f"{self._partition_error(index, exc)} ({detail})",
        )

    def _wait_before_retry(self, index: int, attempt: int) -> float:
        """Espera antes del reintento ``attempt`` (≥ 1) con backoff exponencial y jitter completo; devuelve los segundos.

        B-14 (performance-audit de bulk 2026-10-01): antes se reintentaba al instante y, tras un corte o un pico de
        bloqueos, todas las particiones agotaban sus reintentos a la vez en milisegundos.
        """
        base, cap = self._retry.backoff
        delay: float = self._jitter(0.0, min(cap, base * 2 ** (attempt - 1)))
        if delay > 0:
            self.logger.info("Partición %d: reintento %d dentro de %.2f s", index, attempt, delay)
            self._sleep(delay)
        return delay

    def _permanent_failure(
        self,
        crud: BulkCrud,
        index: int,
        t_start: float,
        tabla_destino: str,
        exc: Exception,
        attempt: int,
        waited: float,
    ) -> PartitionResult:
        """Error permanente: queda en ``partition_errors`` sin abortar el resto de particiones.

        Antes solo se capturaban SQLAlchemyError, ValueError y pd.errors.DatabaseError, y un error del lector (OSError,
        KeyError…) abortaba load() entero.
        """
        self.logger.warning(
            "Error permanente cargando partición %d de '%s': %s",
            index,
            tabla_destino,
            exc,
            exc_info=not isinstance(exc, self.EXPECTED_ERRORS),  # traza solo para errores inesperados
        )
        # BLK-08: crud.rows_committed refleja filas ya comprometidas vía commit_every_n_chunks antes del fallo
        # (0 en modo atómico, donde un fallo revierte toda la sesión).
        return self._partition_result(
            crud,
            index,
            t_start,
            rows=crud.rows_committed,
            retries=attempt,
            retry_wait_seconds=waited,
            error=self._partition_error(index, exc),
        )

    def _run_attempt(
        self,
        crud: BulkCrud,
        tabla_destino: str,
        reader: PartitionReader,
        override_identity: bool,
        exclude_autoincrement_pk: bool,
        skip_maintenance: bool,
        *,
        operation: _Operation = "insert",
        skip_rows: int = 0,
    ) -> int:
        """Un intento sobre la partición, sin sus primeras ``skip_rows`` filas; devuelve las filas enviadas."""

        def read() -> Iterable[pd.DataFrame]:
            return skip_leading_rows(reader(), skip_rows) if skip_rows else reader()

        if operation == "update":
            with closing_iterable(read()) as chunks:
                sent: int = crud.bulk_update_from_chunks(chunks, tabla_destino)
            return sent
        if operation == "delete":
            with closing_iterable(read()) as chunks:
                sent = crud.bulk_delete_from_chunks(chunks, tabla_destino)
            return sent
        if self._parallel.disable_constraints and not skip_maintenance:
            return self._load_with_maintenance(crud, tabla_destino, read, override_identity, exclude_autoincrement_pk)
        with closing_iterable(read()) as chunks:
            rows: int = crud.bulk_insert_from_chunks(
                chunks,
                tabla_destino,
                override_identity=override_identity,
                exclude_autoincrement_pk=exclude_autoincrement_pk,
            )
        return rows

    @staticmethod
    def _partition_result(
        crud: BulkCrud,
        index: int,
        t_start: float,
        *,
        rows: int,
        retries: int,
        retry_wait_seconds: float = 0.0,
        error: str | None = None,
    ) -> PartitionResult:
        """``PartitionResult`` con los contadores de auditoría de ``crud``."""
        return PartitionResult(
            index=index,
            rows=rows,
            elapsed_seconds=time.perf_counter() - t_start,
            error=error,
            retries=retries,
            retry_wait_seconds=retry_wait_seconds,
            rows_rejected=crud.rows_rejected,
            **AuditCounters.of(crud).as_dict(),
        )

    def _load_with_maintenance(
        self,
        crud: BulkCrud,
        tabla_destino: str,
        reader: PartitionReader,
        override_identity: bool,
        exclude_autoincrement_pk: bool,
    ) -> int:
        """Inserta chunks dentro de ``bulk_session`` + ``maintenance_scope``.

        No usa ``bulk_insert_from_chunks`` porque éste gestiona su propio
        ``bulk_session`` (incompatible con ``maintenance_scope``, que requiere
        una sesión ya activa sobre la misma conexión). Itera los chunks del
        lector y delega en ``bulk_insert_from_df`` que respeta la conexión
        activa del ``bulk_session`` externo.

        ``disable_indexes`` se fuerza a ``False``: deshabilitar índices en
        cada worker adquiere un lock DDL global en MSSQL (SCH-M) que serializa
        la carga; con ``ParallelOptions.disable_indexes`` se hace una vez antes
        del pool (:meth:`_hoist_indexes_for_workers`).
        """
        total = 0
        # Reflejar antes de abrir la sesión: maintenance_scope y bulk_insert_from_df usan la tabla ya en caché y el worker
        # no pide una segunda conexión mientras retiene la de la sesión (guarda de la regla size + max_overflow).
        crud.reflect_table(tabla_destino)
        with (
            crud.bulk_session(),
            crud.maintenance_scope(tabla_destino, disable_constraints=True, disable_indexes=False),
            closing_iterable(reader()) as chunks,
        ):
            for chunk in chunks:
                if chunk.empty:
                    continue
                crud.bulk_insert_from_df(
                    chunk,
                    tabla_destino,
                    generar_sql=False,
                    override_identity=override_identity,
                    exclude_autoincrement_pk=exclude_autoincrement_pk,
                )
                total += len(chunk)
        return total

    @contextmanager
    def _hoist_constraints_for_workers(self, tabla_destino: str) -> Generator[bool, None, None]:
        """Deshabilita constraints globalmente antes del pool; devuelve si se hizo hoist.

        Devuelve ``True`` si los constraints fueron deshabilitados y los workers deben
        omitir ``maintenance_scope``; ``False`` si no fue necesario o posible (workers
        usan el path per-worker de ``_load_with_maintenance``).

        Motivación: en MSSQL y PostgreSQL, la sentencia DDL de deshabilitación adquiere
        un lock exclusivo sobre la tabla (SCH-M y ACCESS EXCLUSIVE respectivamente) que
        persiste durante **toda la transacción**. Si cada worker ejecuta esa sentencia en
        su propia transacción larga (que incluye los INSERTs), los workers se serializan
        esperando el turno del lock. Ejecutar el DDL **una sola vez** en el hilo principal
        en su propia transacción corta libera el lock antes de que arranquen los workers.

        - **MSSQL**: ``ALTER TABLE … NOCHECK CONSTRAINT ALL`` (SCH-M lock).
        - **PostgreSQL**: ``ALTER TABLE … DISABLE TRIGGER ALL`` (ACCESS EXCLUSIVE lock).
          Solo se ejecuta si el usuario tiene privilegios (superuser o propietario).
          Sin privilegios: devuelve ``False`` y los workers usan el path per-worker,
          que también comprueba privilegios y emite warning si fallan.
        - **Oracle**: ``DISABLE``/``ENABLE VALIDATE CONSTRAINT`` de cada FK, CHECK con nombre y UNIQUE
          (:meth:`_hoist_oracle_constraints`); por worker fallaban con ORA-00054 (hotfix 2026-10-19).
        - **MySQL/MariaDB** y otros: ``SET SESSION FOREIGN_KEY_CHECKS=0`` es una variable
          de sesión sin lock de tabla — el path per-worker es correcto; devuelve ``False``.
        """
        dialect = self._engine.dialect.name
        if dialect == "oracle":
            with self._hoist_oracle_constraints(tabla_destino):
                yield True
            return
        if dialect not in ("mssql", "postgresql"):
            yield False
            return

        # La misma tabla que usarán los workers (auditoría de bulk 2026-09-24, hallazgo 4): antes el nombre se citaba tal
        # cual, sin la normalización de BulkCrud, y con "Usuarios" en PostgreSQL la comprobación de propietario fallaba en
        # silencio o el ALTER TABLE "Usuarios" daba error.
        tabla = self._resolve_table(tabla_destino)
        quoted = self._engine.dialect.identifier_preparer.format_table(tabla)

        if dialect == "mssql":
            with self._engine.begin() as conn:
                conn.execute(text(disable_table_integrity_sql(dialect, quoted)))
            try:
                yield True
            finally:
                with self._engine.begin() as conn:
                    conn.execute(text(enable_table_integrity_sql(dialect, quoted)))

        else:  # postgresql
            with self._engine.begin() as conn:
                can_disable: bool = can_disable_pg_triggers(conn, tabla)
                if can_disable:
                    conn.execute(text(disable_table_integrity_sql(dialect, quoted)))
            if not can_disable:
                # Fuera del `with` (auditoría de bulk 2026-09-24): antes se cedía el control dentro de él y esa conexión
                # quedaba fuera del pool, con una transacción abierta, durante toda la carga de los workers.
                self.logger.warning(
                    "PostgreSQL: privilegios insuficientes para deshabilitar triggers "
                    "en '%s'. Los workers usarán maintenance_scope individual.",
                    tabla_destino,
                )
                yield False
                return
            try:
                yield True
            finally:
                with self._engine.begin() as conn:
                    conn.execute(text(enable_table_integrity_sql(dialect, quoted)))

    #: Motores y modos donde, con varios hilos, desactivar índices fue más lento en el banco (G0, 4 hilos, 1M filas):
    #: tiempo total frente a no tocarlos.
    _INDEXES_SLOWER_IN_PARALLEL: ClassVar[dict[tuple[str, str], str]] = {
        ("postgresql", "secondary"): "+3 % a +4 %",
        ("mariadb", "secondary"): "+11 %",
        ("postgresql", "all"): "+38 % a +41 %",
        ("mysql", "all"): "+4 % a +10 %",
        ("mariadb", "all"): "+15 % a +18 %",
    }

    @contextmanager
    def _hoist_indexes_for_workers(
        self,
        tabla_destino: str,
        result: ParallelLoadResult,
        workers: int,
        mode: IndexMode = "secondary",
        errors: list[Exception] | None = None,
    ) -> Generator[None, None, None]:
        """``ParallelOptions.disable_indexes``: desactiva una vez, antes del pool, los índices secundarios no únicos.

        Misma estrategia que ``dump.IndexManager`` (``bulk/_support/secondary_indexes.py``), con una conexión propia y
        un commit por sentencia (sin bloqueos largos; en SQL Server, el SCH-M de ``ALTER INDEX`` por worker serializaba
        la carga). Los reconstruye al terminar, también si falla una partición, y deja un resultado por índice en
        ``result.index_results``. Con varios hilos, en PostgreSQL y MariaDB fue más lento (la carga ya reparte el coste
        de los índices y la reconstrucción es en serie): se aplica igualmente y se avisa. Con ``mode="all"``, si un
        único no se reconstruye lanza ``IndexRebuildError`` al salir (las constraints se reactivan antes, fuera).
        """
        dialect = self._engine.dialect.name
        if dialect not in SUPPORTED_DIALECTS:
            self.logger.warning(
                "disable_indexes no está soportado en '%s': la carga de '%s' sigue sin tocar índices.",
                dialect,
                tabla_destino,
            )
            yield
            return
        slower = self._INDEXES_SLOWER_IN_PARALLEL.get((dialect, mode))
        if slower is not None and workers > 1:
            self.logger.warning(
                "disable_indexes='%s' en '%s' con %d hilos: en %s fue más lento en el banco (4 hilos, 1M filas: %s de "
                "tiempo total); en SQL Server y Oracle sí compensa. Se aplica igualmente.",
                mode,
                tabla_destino,
                workers,
                dialect,
                slower,
            )
        tabla = self._resolve_table(tabla_destino)
        planner = SecondaryIndexPlanner(dialect, self._engine.dialect.identifier_preparer)
        runner = IndexDdlRunner(dialect, self.logger, commit=True, savepoint=False)
        quoted = self._engine.dialect.identifier_preparer.format_table(tabla)
        with self._engine.connect() as conn:
            steps = planner.plan(conn, table=tabla.name, schema=tabla.schema, quoted_table=quoted, mode=mode)
            disabled = runner.disable(conn, steps)
        try:
            yield
        finally:
            if disabled:
                with self._engine.connect() as conn:
                    result.index_results = runner.restore(conn, disabled)
        error = rebuild_error(runner, result.index_results, f"ParallelBulkLoader.load('{tabla_destino}')")
        if error is not None:
            if errors is None:
                raise error
            errors.append(error)  # load() la lanza después de escribir la auditoría

    @contextmanager
    def _hoist_oracle_constraints(self, tabla_destino: str) -> Generator[None, None, None]:
        """Oracle: desactiva una vez, antes del pool, las FK, CHECK con nombre y UNIQUE; las reactiva al terminar.

        Hotfix 2026-10-19 (G0 de ``.ai/sessions/2026-10-18b-index-modes-bulk-dump``): cada worker lo hacía en su
        ``maintenance_scope``. Con otro worker insertando, ``DISABLE`` y ``ENABLE VALIDATE CONSTRAINT`` fallaban con
        ORA-00054 (solo un aviso en el log): los workers que no la desactivaron no la reactivaban y la del que sí, fallaba;
        la UNIQUE quedaba ``DISABLED`` y sin índice. Mismas constraints que ``maintenance_scope``. Si alguna no se puede
        reactivar, se intentan las demás y se propaga el primer error (si la carga no había fallado ya).
        """
        crud = BulkCrud(
            self._engine,
            batch=self._options.batch,
            audit=AuditOptions(warn_if_disabled=False),
            execution=self._options.execution,
        )
        tabla = crud.reflect_table(tabla_destino)
        names = TableMaintenance(
            engine=self._engine,
            session=crud._session,  # noqa: SLF001 — mismo paquete (bulk); solo se usa su lector de metadatos
            cadence=crud._batch_statement_executor.cadence,  # noqa: SLF001
            table_snapshot=crud._table_snapshot,  # noqa: SLF001
            logger=self.logger,
        )._oracle_fetch_constraint_names(tabla)  # noqa: SLF001
        prep = self._engine.dialect.identifier_preparer
        quoted = prep.format_table(tabla)
        disabled: list[str] = []
        for name in names:
            try:
                with self._engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {quoted} DISABLE CONSTRAINT {prep.quote_identifier(name)}"))
                disabled.append(name)
            except SQLAlchemyError as exc:
                self.logger.warning("No se pudo deshabilitar la constraint '%s' en '%s': %s", name, tabla_destino, exc)
        errors: list[SQLAlchemyError] = []
        try:
            yield
        finally:
            for name in disabled:
                try:
                    with self._engine.begin() as conn:
                        conn.execute(
                            text(f"ALTER TABLE {quoted} ENABLE VALIDATE CONSTRAINT {prep.quote_identifier(name)}")
                        )
                except SQLAlchemyError as exc:
                    self.logger.error("No se pudo rehabilitar la constraint '%s' en '%s': %s", name, tabla_destino, exc)
                    errors.append(exc)
        if errors:
            raise errors[0]

    def _resolve_table(self, tabla_destino: str) -> Table:
        """``Table`` reflejada con la misma resolución de nombre que ``BulkCrud`` (mayúsculas y esquema).

        PL-3 (audit-code de ``ParallelBulkLoader`` 2026-09-25): la ``BulkCrud`` recibe la ``execution`` del loader
        (``fast_executemany``). Con el valor por defecto activaba ``fast_executemany`` en el engine compartido
        (``mssql+pyodbc``) aunque el loader se hubiera creado con ``False``. Sin auditoría ni rechazos: solo refleja.
        """
        crud = BulkCrud(
            self._engine,
            batch=self._options.batch,
            audit=AuditOptions(warn_if_disabled=False),
            execution=self._options.execution,
        )
        return crud.reflect_table(tabla_destino)


__all__: list[str] = [
    "ParallelBulkLoader",
    "ParallelLoadResult",
    "PartitionReader",
    "PartitionResult",
]
