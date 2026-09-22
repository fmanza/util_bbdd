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
import time

from collections.abc import Callable, Iterable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError as SQLAOperationalError, SQLAlchemyError

from ..crud import BulkCrud

_log = logging.getLogger(__name__)

# Un lector de partición: invocado en su hilo worker, produce los chunks a insertar.
PartitionReader = Callable[[], Iterable[pd.DataFrame]]


def _quote_mssql_table(tabla_destino: str) -> str:
    """Genera nombre de tabla MSSQL con corchetes para sentencias DDL."""
    if "." in tabla_destino:
        schema, table = tabla_destino.split(".", 1)
        return f"[{schema.replace(']', ']]')}].[{table.replace(']', ']]')}]"
    return f"[{tabla_destino.replace(']', ']]')}]"


def _quote_pg_table(tabla_destino: str) -> tuple[str | None, str, str]:
    """Descompone y cotiza un nombre de tabla para sentencias DDL de PostgreSQL.

    Returns:
        Tupla ``(schema, table_name, quoted_full_name)``.
        ``schema`` es ``None`` si no hay prefijo de esquema.
    """
    if "." in tabla_destino:
        schema, table = tabla_destino.split(".", 1)
        return schema, table, f'"{schema.replace(chr(34), chr(34) * 2)}"."{table.replace(chr(34), chr(34) * 2)}"'
    return None, tabla_destino, f'"{tabla_destino.replace(chr(34), chr(34) * 2)}"'


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
    """

    index: int
    rows: int
    elapsed_seconds: float
    error: str | None = None
    retries: int = 0


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
    """

    total_rows: int = 0
    partition_errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    partition_results: list[PartitionResult] = field(default_factory=list)

    @property
    def rows_per_second(self) -> float:
        """Throughput global de la carga. Devuelve 0.0 si elapsed_seconds ≤ 0."""
        if self.elapsed_seconds <= 0.0:
            return 0.0
        return self.total_rows / self.elapsed_seconds


class ParallelBulkLoader:
    """Inserta particiones de datos en paralelo, una ``BulkCrud`` por hilo.

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

    def __init__(
        self,
        engine: Engine,
        *,
        chunk_size: int = 5000,
        max_workers: int = 4,
        commit_every_n_chunks: int | None = None,
        audit_csv_path: Path | None = None,
        enable_fast_executemany: bool = True,
        max_retries: int = 0,
        disable_constraints: bool = False,
    ) -> None:
        """
        Args:
            engine: Engine SQLAlchemy compartido entre workers (thread-safe).
            chunk_size: Filas por lote dentro de cada worker.
            max_workers: Número máximo de hilos paralelos.
            commit_every_n_chunks: Commitea cada N lotes para evitar undo log en
                MariaDB/MySQL. Ignorado si ``None``.
            audit_csv_path: Ruta para auditoría CSV compartida (thread-safe).
            enable_fast_executemany: Activa ``cursor.fast_executemany`` en MSSQL/pyodbc.
            max_retries: Reintentos ante errores retriables (``OperationalError``,
                ``TimeoutError``). No reintenta errores permanentes (integridad, sintaxis).
            disable_constraints: Si ``True``, cada worker deshabilita constraints vía
                ``maintenance_scope`` antes de insertar y las restaura al finalizar.
                Requiere permisos DDL (propietario de tabla o superusuario).
                Usar ``disable_indexes=False`` implícito: deshabilitar índices en
                paralelo causa lock DDL en MSSQL (SCH-M global).

        Raises:
            ValueError: Si ``max_workers < 1`` o ``max_retries < 0``.
        """
        if max_workers < 1:
            raise ValueError(f"max_workers debe ser un entero ≥ 1, recibido: {max_workers}")
        if max_retries < 0:
            raise ValueError(f"max_retries debe ser un entero ≥ 0, recibido: {max_retries}")
        if commit_every_n_chunks is not None and max_retries > 0:
            raise ValueError(
                "commit_every_n_chunks y max_retries > 0 son incompatibles: "
                "un reintento tras commits parciales duplicaría las filas ya committeadas. "
                "Usa max_retries=0 con commit_every_n_chunks, o mantén "
                "commit_every_n_chunks=None si necesitas reintentos."
            )
        self._engine = engine
        self._chunk_size = chunk_size
        self._commit_every_n_chunks = commit_every_n_chunks
        self._audit_csv_path = audit_csv_path
        self._enable_fast_executemany = enable_fast_executemany
        self._max_retries = max_retries
        self._disable_constraints = disable_constraints
        self._max_workers = self._resolve_max_workers(max_workers)

    def _resolve_max_workers(self, requested: int) -> int:
        """Devuelve el número efectivo de workers, acotado al pool size para evitar deadlock.

        Con pool_size < requested todos los workers con ``bulk_session`` activo retienen
        su conexión mientras esperan una nueva, lo que produce deadlock determinista.
        Reducir max_workers a pool_size elimina la contención.

        NullPool, StaticPool y mocks no tienen ``.size()``: se devuelve requested sin cambio.
        """
        try:
            pool = getattr(self._engine, "pool", None)
            if pool is None:
                return requested
            size_attr = getattr(pool, "size", None)
            if not callable(size_attr):
                return requested
            size = size_attr()
            if isinstance(size, int) and size < requested:
                _log.warning(
                    "max_workers (%d) reducido a pool size (%d) para evitar deadlock "
                    "por agotamiento de conexiones. Crea el engine con "
                    "pool_size >= %d para usar más workers.",
                    requested,
                    size,
                    requested,
                )
                return size
            return requested
        except Exception:  # noqa: BLE001
            return requested  # NullPool, StaticPool, MagicMock en tests — sin cap

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
        if not partition_readers:
            return ParallelLoadResult()

        if partition_ranges is not None:
            _validate_partition_ranges(partition_ranges, len(partition_readers))

        result = ParallelLoadResult()
        t_start = time.perf_counter()
        workers = min(self._max_workers, len(partition_readers))

        constraint_ctx = (
            self._hoist_constraints_for_workers(tabla_destino)
            if self._disable_constraints
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

    def _load_partition(
        self,
        tabla_destino: str,
        reader: PartitionReader,
        override_identity: bool,
        exclude_autoincrement_pk: bool,
        index: int,
        skip_maintenance: bool = False,
    ) -> PartitionResult:
        """Tarea de hilo: carga una partición con su propia ``BulkCrud``.

        Reintenta hasta ``max_retries`` veces ante ``OperationalError`` o
        ``TimeoutError`` (errores retriables). Errores permanentes (integridad,
        sintaxis, validación) no se reintentan.

        Args:
            skip_maintenance: Si ``True``, omite ``maintenance_scope`` aunque
                ``disable_constraints=True``. Usado cuando MSSQL o PostgreSQL ya
                deshabilitaron constraints globalmente antes del pool
                (``_hoist_constraints_for_workers``).
        """
        crud = BulkCrud(
            self._engine,
            chunk_size=self._chunk_size,
            audit_csv_path=self._audit_csv_path,
            commit_every_n_chunks=self._commit_every_n_chunks,
            enable_fast_executemany=self._enable_fast_executemany,
        )

        t_start = time.perf_counter()
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                if self._disable_constraints and not skip_maintenance:
                    rows = self._load_with_maintenance(
                        crud,
                        tabla_destino,
                        reader,
                        override_identity,
                        exclude_autoincrement_pk,
                    )
                else:
                    rows = crud.bulk_insert_from_chunks(
                        reader(),
                        tabla_destino,
                        override_identity=override_identity,
                        exclude_autoincrement_pk=exclude_autoincrement_pk,
                    )
                elapsed = time.perf_counter() - t_start
                return PartitionResult(index=index, rows=rows, elapsed_seconds=elapsed, retries=attempt)

            except (SQLAOperationalError, TimeoutError) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    _log.warning(
                        "Partición %d intento %d/%d fallido (retriable): %s",
                        index,
                        attempt + 1,
                        self._max_retries + 1,
                        exc,
                    )
                # continúa al siguiente intento

            except (SQLAlchemyError, ValueError, pd.errors.DatabaseError) as exc:
                elapsed = time.perf_counter() - t_start
                _log.warning("Error permanente cargando partición %d de '%s': %s", index, tabla_destino, exc)
                return PartitionResult(
                    index=index,
                    # BLK-08: crud.rows_committed refleja filas ya comprometidas vía
                    # commit_every_n_chunks antes del fallo (0 en modo atómico, donde
                    # un fallo revierte toda la sesión).
                    rows=crud.rows_committed,
                    elapsed_seconds=elapsed,
                    error=f"partición {index}: {exc}",
                    retries=attempt,
                )

        # Reintentos agotados
        elapsed = time.perf_counter() - t_start
        _log.warning("Partición %d agotó %d reintentos: %s", index, self._max_retries, last_exc)
        return PartitionResult(
            index=index,
            rows=crud.rows_committed,
            elapsed_seconds=elapsed,
            error=f"partición {index}: {last_exc}",
            retries=self._max_retries,
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
        with crud.bulk_session():
            with crud.maintenance_scope(tabla_destino, disable_constraints=True, disable_indexes=False):
                for chunk in reader():
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
    def _hoist_constraints_for_workers(self, tabla_destino: str) -> Iterator[bool]:
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

        if dialect == "mssql":
            quoted = _quote_mssql_table(tabla_destino)
            with self._engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {quoted} NOCHECK CONSTRAINT ALL"))
            try:
                yield True
            finally:
                with self._engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {quoted} WITH CHECK CHECK CONSTRAINT ALL"))

        elif dialect == "postgresql":
            schema, table_name, quoted_pg = _quote_pg_table(tabla_destino)
            with self._engine.begin() as conn:
                can_disable: bool = bool(
                    conn.execute(
                        text(
                            "SELECT current_setting('is_superuser') = 'on' OR EXISTS ("
                            "  SELECT 1 FROM pg_tables "
                            "  WHERE schemaname = COALESCE(:schema, current_schema()) "
                            "  AND tablename = :tbl AND tableowner = current_user"
                            ")"
                        ),
                        {"schema": schema, "tbl": table_name},
                    ).scalar()
                )
                if not can_disable:
                    _log.warning(
                        "PostgreSQL: privilegios insuficientes para deshabilitar triggers "
                        "en '%s'. Los workers usarán maintenance_scope individual.",
                        tabla_destino,
                    )
                    yield False
                    return
                conn.execute(text(f"ALTER TABLE {quoted_pg} DISABLE TRIGGER ALL"))
            try:
                yield True
            finally:
                with self._engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {quoted_pg} ENABLE TRIGGER ALL"))

        else:
            yield False


__all__: list[str] = [
    "ParallelBulkLoader",
    "ParallelLoadResult",
    "PartitionReader",
    "PartitionResult",
]
