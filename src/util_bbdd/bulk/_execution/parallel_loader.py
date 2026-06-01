"""Carga masiva paralela por particiones.

``ParallelBulkLoader`` ejecuta la inserción de varias particiones de datos en
paralelo, una ``BulkCrud`` por hilo. Es un **mecanismo** agnóstico del origen: cada
partición se describe mediante un *lector* (``Callable[[], Iterable[DataFrame]]``)
que produce los chunks ya listos para insertar; el llamador decide de dónde salen
(p.ej. ``pandas.read_sql`` con un ``WHERE pk BETWEEN`` por rango).

Las particiones deben ser **disjuntas** (p.ej. rangos de PK no solapados) para que
los inserts concurrentes en la misma tabla no colisionen. El motor de inserción
(batching, ``commit_every_n_chunks``, estrategias por dialecto, auditoría
thread-safe) lo aporta cada ``BulkCrud`` worker vía ``bulk_insert_from_chunks``.
"""

from __future__ import annotations

import logging

from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from ..crud import BulkCrud

_log = logging.getLogger(__name__)

# Un lector de partición: invocado en su hilo worker, produce los chunks a insertar.
PartitionReader = Callable[[], Iterable[pd.DataFrame]]


@dataclass
class ParallelLoadResult:
    """Resultado agregado de una carga paralela por particiones."""

    total_rows: int = 0
    partition_errors: list[str] = field(default_factory=list)


class ParallelBulkLoader:
    """Inserta particiones de datos en paralelo, una ``BulkCrud`` por hilo.

    ``BulkCrud`` no es thread-safe: por eso cada partición se carga con su **propia**
    instancia ``BulkCrud`` y su propia conexión (el ``Engine`` sí es thread-safe).

    Ejemplo::

        loader = ParallelBulkLoader(engine, chunk_size=10_000, max_workers=4)
        result = loader.load("dbo.orders", [reader_rango1, reader_rango2, ...])
        print(result.total_rows, result.partition_errors)
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
    ) -> None:
        if max_workers < 1:
            raise ValueError(f"max_workers debe ser un entero ≥ 1, recibido: {max_workers}")
        self._engine = engine
        self._chunk_size = chunk_size
        self._max_workers = max_workers
        self._commit_every_n_chunks = commit_every_n_chunks
        self._audit_csv_path = audit_csv_path
        self._enable_fast_executemany = enable_fast_executemany

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
            override_identity: Propagado a ``bulk_insert_from_chunks``.
            exclude_autoincrement_pk: Propagado a ``bulk_insert_from_chunks``.

        Returns:
            ``ParallelLoadResult`` con filas totales y errores por partición (best-effort:
            un fallo en una partición no aborta las demás).
        """
        if not partition_readers:
            return ParallelLoadResult()

        result = ParallelLoadResult()
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
                rows, error = future.result()
                result.total_rows += rows
                if error is not None:
                    result.partition_errors.append(error)
        return result

    def _load_partition(
        self,
        tabla_destino: str,
        reader: PartitionReader,
        override_identity: bool,
        exclude_autoincrement_pk: bool,
        index: int,
    ) -> tuple[int, str | None]:
        """Tarea de hilo: carga una partición con su propia ``BulkCrud``."""
        crud = BulkCrud(
            self._engine,
            chunk_size=self._chunk_size,
            audit_csv_path=self._audit_csv_path,
            commit_every_n_chunks=self._commit_every_n_chunks,
            enable_fast_executemany=self._enable_fast_executemany,
        )
        try:
            rows = crud.bulk_insert_from_chunks(
                reader(),
                tabla_destino,
                override_identity=override_identity,
                exclude_autoincrement_pk=exclude_autoincrement_pk,
            )
            return rows, None
        except (SQLAlchemyError, ValueError, pd.errors.DatabaseError) as exc:
            _log.warning("Error cargando partición %d de '%s': %s", index, tabla_destino, exc)
            return 0, f"partición {index}: {exc}"


__all__: list[str] = ["ParallelBulkLoader", "ParallelLoadResult", "PartitionReader"]
