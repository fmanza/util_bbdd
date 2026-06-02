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

import logging
import time

from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError as SQLAOperationalError, SQLAlchemyError

from ..crud import BulkCrud

_log = logging.getLogger(__name__)

# Un lector de partición: invocado en su hilo worker, produce los chunks a insertar.
PartitionReader = Callable[[], Iterable[pd.DataFrame]]


@dataclass
class PartitionResult:
    """Resultado de una partición individual dentro de una carga paralela.

    Attributes:
        index: Índice de la partición (0-based, orden del ``partition_readers``).
        rows: Filas insertadas correctamente en esta partición.
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
        self._engine = engine
        self._chunk_size = chunk_size
        self._max_workers = max_workers
        self._commit_every_n_chunks = commit_every_n_chunks
        self._audit_csv_path = audit_csv_path
        self._enable_fast_executemany = enable_fast_executemany
        self._max_retries = max_retries
        self._disable_constraints = disable_constraints
        self._warn_pool_size()

    def _warn_pool_size(self) -> None:
        """Emite warning si el connection pool puede ser insuficiente para max_workers.

        NullPool, StaticPool y mocks no tienen ``.size()``: se ignoran silenciosamente.
        """
        try:
            pool = getattr(self._engine, "pool", None)
            if pool is None:
                return
            size_attr = getattr(pool, "size", None)
            if not callable(size_attr):
                return
            size = size_attr()
            if isinstance(size, int) and size < self._max_workers:
                _log.warning(
                    "connection pool size (%d) < max_workers (%d): los workers adicionales "
                    "esperarán un slot disponible. Considera crear el engine con "
                    "pool_size >= max_workers para evitar contención.",
                    size,
                    self._max_workers,
                )
        except Exception:  # noqa: BLE001
            pass  # NullPool, StaticPool, MagicMock en tests — ignorar

    def load(
        self,
        tabla_destino: str,
        partition_readers: Sequence[PartitionReader],
        *,
        override_identity: bool = False,
        exclude_autoincrement_pk: bool = False,
    ) -> ParallelLoadResult:
        """Carga en paralelo todas las particiones en ``tabla_destino``.

        Args:
            tabla_destino: Nombre lógico de la tabla (``schema.tabla`` o ``tabla``).
            partition_readers: Lectores de partición; cada uno produce los chunks de su
                partición (disjunta respecto a las demás).
            override_identity: Propagado a cada worker (solo PostgreSQL).
            exclude_autoincrement_pk: Propagado a cada worker.

        Returns:
            ``ParallelLoadResult`` con filas totales, métricas de throughput y resultados
            individuales por partición. Best-effort: un fallo en una partición no aborta
            las demás.
        """
        if not partition_readers:
            return ParallelLoadResult()

        result = ParallelLoadResult()
        t_start = time.perf_counter()
        workers = min(self._max_workers, len(partition_readers))

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    self._load_partition,
                    tabla_destino,
                    reader,
                    override_identity,
                    exclude_autoincrement_pk,
                    index,
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
    ) -> PartitionResult:
        """Tarea de hilo: carga una partición con su propia ``BulkCrud``.

        Reintenta hasta ``max_retries`` veces ante ``OperationalError`` o
        ``TimeoutError`` (errores retriables). Errores permanentes (integridad,
        sintaxis, validación) no se reintentan.
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
                if self._disable_constraints:
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
                    rows=0,
                    elapsed_seconds=elapsed,
                    error=f"partición {index}: {exc}",
                    retries=attempt,
                )

        # Reintentos agotados
        elapsed = time.perf_counter() - t_start
        _log.warning("Partición %d agotó %d reintentos: %s", index, self._max_retries, last_exc)
        return PartitionResult(
            index=index,
            rows=0,
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


__all__: list[str] = [
    "ParallelBulkLoader",
    "ParallelLoadResult",
    "PartitionReader",
    "PartitionResult",
]
