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
"""

from __future__ import annotations

import contextlib
import logging
import math
import random
import time

from collections.abc import Callable, Generator, Iterable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Literal

import pandas as pd

from sqlalchemy import Engine, Table, text
from sqlalchemy.exc import SQLAlchemyError

from ...metadata.postgresql.tables import fetch_can_create_temp_tables_sql
from .._audit.counters import AuditCounters
from .._audit.errors import AuditError
from .._support.dialect import can_disable_pg_triggers, disable_table_integrity_sql, enable_table_integrity_sql
from .._support.iterables import close_if_closable, closing_iterable
from .._support.pool import pool_capacity
from .._support.retry import is_retriable
from ..audit import AuditManager
from ..crud import BulkCrud
from .batch import validate_chunk_size

# Un lector de partición: invocado en su hilo worker, produce los chunks a insertar, actualizar o borrar.
PartitionReader = Callable[[], Iterable[pd.DataFrame]]

# Operación de una carga paralela: load() → insert, update() → update, delete() → delete.
_Operation = Literal["insert", "update", "delete"]

# Reintentos mínimos de update()/delete() ante errores transitorios, aunque max_retries sea 0. Son idempotentes por PK y,
# con particiones contiguas, InnoDB puede dar deadlock (1213) en la frontera aunque sean disjuntas: medido en el banco con
# MySQL 8.4, DELETE de 1M filas con 2 hilos (performance-audit de bulk 2026-10-01, R-5).
_IDEMPOTENT_MIN_RETRIES: int = 2

# Errores de datos, de BD o de auditoría estricta habituales en una carga: se anotan sin traza en el log (el de
# auditoría ya lo registró BulkCrud como ERROR). El resto también se anotan en partition_errors, pero con traza, porque
# suelen indicar un fallo del lector o de programación.
_EXPECTED_ERRORS: tuple[type[Exception], ...] = (SQLAlchemyError, ValueError, pd.errors.DatabaseError, AuditError)


def _partition_error(index: int, exc: Exception) -> str:
    """Texto de ``partition_errors``: como antes para los errores habituales; con el tipo para el resto."""
    if isinstance(exc, _EXPECTED_ERRORS):
        return f"partición {index}: {exc}"
    return f"partición {index}: {type(exc).__name__}: {exc}"


def _skip_rows(chunks: Iterable[pd.DataFrame], rows: int) -> Iterator[pd.DataFrame]:
    """Los chunks de ``chunks`` sin sus primeras ``rows`` filas (reanudación de una partición, B-11).

    Cierra ``chunks`` al terminar, también si quien consume deja de iterar (el lector puede tener una conexión abierta).
    """
    try:
        for chunk in chunks:
            if rows >= len(chunk):
                rows -= len(chunk)
                continue
            if rows:
                chunk = chunk.iloc[rows:]
                rows = 0
            yield chunk
    finally:
        close_if_closable(chunks)


def _validate_partition_ranges(ranges: Sequence[tuple[int, int]], n_readers: int) -> None:
    """Valida que los rangos de partición sean disjuntos y coincidan con el nº de lectores.

    Raises:
        ValueError: Si len(ranges) != n_readers o algún par de rangos se solapa.
    """
    if len(ranges) != n_readers:
        raise ValueError(
            f"partition_ranges ({len(ranges)} rangos) debe tener la misma longitud "
            f"que partition_readers ({n_readers} lectores)."
        )
    sorted_r = sorted(ranges, key=lambda r: r[0])
    for i in range(len(sorted_r) - 1):
        _, hi1 = sorted_r[i]
        lo2, _ = sorted_r[i + 1]
        if hi1 >= lo2:
            raise ValueError(
                f"Rangos solapados detectados: {sorted_r[i]} solapa con {sorted_r[i + 1]}. "
                "Las particiones deben ser disjuntas para evitar colisiones en INSERT."
            )


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

    Conciliación: con auditoría activa, ``audit_failures == 0`` y ``audit_uncommitted_records == 0``, se cumple
    ``audited_rows + unaudited_committed_rows == total_rows``.
    """

    total_rows: int = 0
    partition_errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    partition_results: list[PartitionResult] = field(default_factory=list)

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

    Ejemplo sin mantenimiento (comportamiento previo)::

        loader = ParallelBulkLoader(engine, chunk_size=10_000, max_workers=4)
        result = loader.load("dbo.orders", [reader_rango1, reader_rango2, ...])
        print(result.total_rows, result.partition_errors)

    Ejemplo para cargas >1M filas con deshabilitación de constraints::

        loader = ParallelBulkLoader(
            engine,
            max_workers=4,
            disable_constraints=True,
            commit_every_n_chunks=20,
        )
        result = loader.load("dbo.orders", readers)
        print(
            f"{result.total_rows} filas en {result.elapsed_seconds:.1f}s "
            f"({result.rows_per_second:.0f} filas/s)"
        )
    """

    logger: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def __init__(
        self,
        engine: Engine,
        *,
        chunk_size: int | None = None,
        max_workers: int = 4,
        commit_every_n_chunks: int | None = None,
        audit_csv_path: Path | None = None,
        enable_fast_executemany: bool = True,
        max_retries: int = 0,
        disable_constraints: bool = False,
        audit_strict: bool = False,
        strip_strings: bool = True,
        reflect_foreign_keys: bool = True,
        retry_backoff: tuple[float, float] = (0.5, 30.0),
        retry_on: Callable[[BaseException], bool] | None = None,
    ) -> None:
        """
        Args:
            engine: Engine SQLAlchemy compartido entre workers (thread-safe).
            chunk_size: Filas por lote dentro de cada worker. ``None`` (default): el lote por motor y operación de
                ``BulkCrud`` (B-04).
            max_workers: Número máximo de hilos paralelos.
            commit_every_n_chunks: Commitea cada N lotes para evitar undo log en
                MariaDB/MySQL. Ignorado si ``None``. Con ``max_retries > 0``, un reintento **reanuda** la partición
                desde la última fila confirmada (``BulkCrud.rows_committed``): el lector debe devolver las filas en el
                mismo orden en cada llamada. Hasta v0.23.x la combinación lanzaba ``ValueError`` (B-11).
            audit_csv_path: Ruta para auditoría CSV compartida (thread-safe).
            enable_fast_executemany: Activa ``cursor.fast_executemany`` en MSSQL/pyodbc.
            max_retries: Reintentos de una partición ante errores transitorios. Por defecto se decide por el código del
                error (``is_retriable``): desconexiones, deadlocks, lock wait timeouts, serialización y timeouts. Los
                errores de datos, de integridad, de sintaxis o de permisos no se reintentan. Hasta v0.23.x se decidía
                por clase (``OperationalError``/``TimeoutError``): con PyMySQL se reintentaban errores permanentes y
                con Oracle no se reintentaba el deadlock (B-13, performance-audit de bulk 2026-10-01).
            disable_constraints: Si ``True``, cada worker deshabilita constraints vía
                ``maintenance_scope`` antes de insertar y las restaura al finalizar.
                Requiere permisos DDL (propietario de tabla o superusuario).
                Usar ``disable_indexes=False`` implícito: deshabilitar índices en
                paralelo causa lock DDL en MSSQL (SCH-M global).
            audit_strict: Se pasa a la ``BulkCrud`` de cada partición. Con ``False`` (default) un fallo al escribir el
                CSV de auditoría no hace fallar la partición: se registra como ERROR y se cuenta en
                ``PartitionResult.audit_failures`` / ``ParallelLoadResult.audit_failures``. Con ``True`` el fallo
                deshace la partición y queda en ``partition_errors`` sin reintentarse. En modo estricto la auditoría se
                escribe antes del commit: si es el commit el que falla, esos registros quedan en el CSV sin datos en la
                BD, se cuentan en ``audit_uncommitted_records`` y la partición **no se reintenta** aunque el error sea
                retriable, para no duplicarlos.
            strip_strings: Se pasa a la ``BulkCrud`` de cada partición: con ``False`` las cadenas se envían sin quitar
                los espacios de los extremos (``dump``, PD-05).
            reflect_foreign_keys: Se pasa a las ``BulkCrud`` del loader: con ``False`` la reflexión de la tabla destino
                no lee sus claves foráneas (``dump``, Q9).
            retry_backoff: ``(base, máximo)`` en segundos de la espera antes de cada reintento: un valor aleatorio entre
                0 y ``min(máximo, base · 2**(intento − 1))`` (backoff exponencial con *jitter* completo), para que las
                particiones no reintenten a la vez tras un corte. ``(0, 0)`` reintenta sin esperar (comportamiento
                hasta v0.23.x). Solo actúa con ``max_retries > 0``. Por defecto ``(0.5, 30.0)`` (B-14).
            retry_on: Criterio propio de reintento (recibe la excepción). ``None`` usa ``is_retriable``.

        Raises:
            ValueError: Si ``chunk_size`` no es un entero ≥ 1, ``max_workers < 1``, ``max_retries < 0`` o
                ``retry_backoff`` no son dos números finitos ≥ 0.
            AuditConfigError: Si no se puede crear el directorio de ``audit_csv_path`` (subclase de ``ValueError``).
        """
        if chunk_size is not None:
            chunk_size = validate_chunk_size(chunk_size)  # antes del pool: si no, fallaría cada partición
        if max_workers < 1:
            raise ValueError(f"max_workers debe ser un entero ≥ 1, recibido: {max_workers}")
        if max_retries < 0:
            raise ValueError(f"max_retries debe ser un entero ≥ 0, recibido: {max_retries}")
        if len(retry_backoff) != 2 or not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
            for value in retry_backoff
        ):
            raise ValueError(
                f"retry_backoff debe ser (base, máximo) con números finitos ≥ 0, recibido: {retry_backoff!r}"
            )
        if audit_csv_path is not None:
            # PL-4 (audit-code de ParallelBulkLoader 2026-09-25): antes del pool, como chunk_size. Si no, cada
            # partición fallaba por separado y, con disable_constraints, el hoist se hacía para nada.
            AuditManager(audit_csv_path)
        self._engine = engine
        self._chunk_size = chunk_size
        self._commit_every_n_chunks = commit_every_n_chunks
        self._audit_csv_path = audit_csv_path
        self._enable_fast_executemany = enable_fast_executemany
        self._max_retries = max_retries
        self._disable_constraints = disable_constraints
        self._audit_strict = audit_strict
        self._strip_strings = strip_strings
        self._reflect_foreign_keys = reflect_foreign_keys
        self._retry_backoff: tuple[float, float] = (float(retry_backoff[0]), float(retry_backoff[1]))
        self._retry_on: Callable[[BaseException], bool] = retry_on or is_retriable
        # Inyectables en tests (sin esperas reales ni azar).
        self._sleep: Callable[[float], None] = time.sleep
        self._jitter: Callable[[float, float], float] = random.uniform
        self._max_workers = self._resolve_max_workers(max_workers)

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
            _validate_partition_ranges(partition_ranges, len(partition_readers))

        if self._audit_csv_path is None:
            # M-4: un aviso por carga; las BulkCrud de las particiones se crean sin el suyo.
            self.logger.info(
                "Auditoría deshabilitada en la carga paralela de '%s' (audit_csv_path=None).", tabla_destino
            )

        result = ParallelLoadResult()
        t_start = time.perf_counter()
        workers = min(self._max_workers, len(partition_readers))
        if operation == "update" and workers > 1 and not self._staging_update_available():
            workers = 1

        constraint_ctx = (
            self._hoist_constraints_for_workers(tabla_destino)
            if self._disable_constraints and operation == "insert"
            else contextlib.nullcontext(False)
        )
        with constraint_ctx as skip_maintenance:
            with ThreadPoolExecutor(max_workers=workers) as pool:
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
                        max_retries=self._max_retries
                        if operation == "insert"
                        else max(self._max_retries, _IDEMPOTENT_MIN_RETRIES),
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
        return result

    def _staging_update_available(self) -> bool:
        """En PostgreSQL, ``False`` si falta el privilegio ``TEMP`` (el UPDATE paralelo sería fila a fila); WARNING."""
        if self._engine.dialect.name != "postgresql":
            return True
        with self._engine.connect() as conn:
            available = bool(conn.execute(text(fetch_can_create_temp_tables_sql())).scalar())
        if not available:
            self.logger.warning(
                "PostgreSQL sin privilegio TEMP: el UPDATE paralelo se hace con un solo hilo, porque fila a fila en "
                "paralelo es más lento que en serie. Concede TEMP sobre la base de datos para usar varios hilos."
            )
        return available

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
                ``disable_constraints=True``. Usado cuando MSSQL o PostgreSQL ya
                deshabilitaron constraints globalmente antes del pool
                (``_hoist_constraints_for_workers``).
        """
        t_start = time.perf_counter()
        try:
            crud = BulkCrud(
                self._engine,
                chunk_size=self._chunk_size,
                audit_csv_path=self._audit_csv_path,
                commit_every_n_chunks=self._commit_every_n_chunks,
                enable_fast_executemany=self._enable_fast_executemany,
                audit_strict=self._audit_strict,
                warn_if_audit_disabled=False,  # M-4: load() avisa una vez por carga
                strip_strings=self._strip_strings,
                reflect_foreign_keys=self._reflect_foreign_keys,
            )
        except Exception as exc:
            self.logger.warning(
                "No se pudo preparar la partición %d de '%s': %s", index, tabla_destino, exc, exc_info=True
            )
            return PartitionResult(
                index=index,
                rows=0,
                elapsed_seconds=time.perf_counter() - t_start,
                error=_partition_error(index, exc),
            )

        retries: int = self._max_retries if max_retries is None else max_retries
        last_exc: Exception | None = None
        waited: float = 0.0

        for attempt in range(retries + 1):
            if attempt:
                waited += self._wait_before_retry(index, attempt)
            # B-11: las filas confirmadas por intentos anteriores (prefijo de la partición) no se vuelven a enviar.
            # Solo con cadencia: en modo atómico un fallo deshace la partición entera y se reintenta desde el principio.
            resume_from: int = crud.rows_committed if attempt and self._commit_every_n_chunks is not None else 0
            if resume_from:
                self.logger.info("Partición %d: se reanuda tras %d filas ya confirmadas", index, resume_from)
            try:
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
                if not self._retry_on(exc):
                    return self._permanent_failure(crud, index, t_start, tabla_destino, exc, attempt, waited)
                last_exc = exc
                if crud.audit_uncommitted_records > 0:
                    # PL-2 (audit-code de ParallelBulkLoader 2026-09-25): con audit_strict falló el commit después de
                    # escribir la auditoría. Reintentar la escribiría otra vez: el CSV contaría el doble que la BD.
                    self.logger.warning(
                        "Partición %d de '%s': falló el commit con la auditoría estricta ya escrita; no se reintenta "
                        "para no duplicarla: %s",
                        index,
                        tabla_destino,
                        exc,
                    )
                    return self._partition_result(
                        crud,
                        index,
                        t_start,
                        rows=crud.rows_committed,
                        retries=attempt,
                        retry_wait_seconds=waited,
                        error=(
                            f"{_partition_error(index, exc)} (el CSV de auditoría contiene "
                            f"{crud.audit_uncommitted_records} registros de este intento sin datos en la BD)"
                        ),
                    )
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
            error=_partition_error(index, last_exc),
        )

    def _wait_before_retry(self, index: int, attempt: int) -> float:
        """Espera antes del reintento ``attempt`` (≥ 1) con backoff exponencial y jitter completo; devuelve los segundos.

        B-14 (performance-audit de bulk 2026-10-01): antes se reintentaba al instante y, tras un corte o un pico de
        bloqueos, todas las particiones agotaban sus reintentos a la vez en milisegundos.
        """
        base, cap = self._retry_backoff
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
            exc_info=not isinstance(exc, _EXPECTED_ERRORS),  # traza solo para errores inesperados
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
            error=_partition_error(index, exc),
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
            return _skip_rows(reader(), skip_rows) if skip_rows else reader()

        if operation == "update":
            with _closing_iterable(read()) as chunks:
                sent: int = crud.bulk_update_from_chunks(chunks, tabla_destino)
            return sent
        if operation == "delete":
            with _closing_iterable(read()) as chunks:
                sent = crud.bulk_delete_from_chunks(chunks, tabla_destino)
            return sent
        if self._disable_constraints and not skip_maintenance:
            return self._load_with_maintenance(crud, tabla_destino, read, override_identity, exclude_autoincrement_pk)
        with _closing_iterable(read()) as chunks:
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
        paralelo adquiere un lock DDL global en MSSQL (SCH-M) que serializa
        la carga y cancela el beneficio del paralelismo.
        """
        total = 0
        # Reflejar antes de abrir la sesión: maintenance_scope y bulk_insert_from_df usan la tabla ya en caché y el worker
        # no pide una segunda conexión mientras retiene la de la sesión (guarda de la regla size + max_overflow).
        crud.reflect_table(tabla_destino)
        with crud.bulk_session():
            with crud.maintenance_scope(tabla_destino, disable_constraints=True, disable_indexes=False):
                with _closing_iterable(reader()) as chunks:
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
        - **MySQL/MariaDB** y otros: ``SET SESSION FOREIGN_KEY_CHECKS=0`` es una variable
          de sesión sin lock de tabla — el path per-worker es correcto; devuelve ``False``.
        """
        dialect = self._engine.dialect.name
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

    def _resolve_table(self, tabla_destino: str) -> Table:
        """``Table`` reflejada con la misma resolución de nombre que ``BulkCrud`` (mayúsculas y esquema).

        PL-3 (audit-code de ``ParallelBulkLoader`` 2026-09-25): la ``BulkCrud`` recibe ``enable_fast_executemany`` del
        loader. Con el valor por defecto activaba ``fast_executemany`` en el engine compartido (``mssql+pyodbc``)
        aunque el loader se hubiera creado con ``False``.
        """
        crud = BulkCrud(
            self._engine,
            chunk_size=self._chunk_size,
            enable_fast_executemany=self._enable_fast_executemany,
            warn_if_audit_disabled=False,
            reflect_foreign_keys=self._reflect_foreign_keys,
        )
        return crud.reflect_table(tabla_destino)


_closing_iterable = closing_iterable  # A2: cierra el generador del lector si falla la escritura

__all__: list[str] = [
    "ParallelBulkLoader",
    "ParallelLoadResult",
    "PartitionReader",
    "PartitionResult",
]
