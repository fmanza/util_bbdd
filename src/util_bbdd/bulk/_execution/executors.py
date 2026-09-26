"""Ejecutores por lotes con la cadencia de commit (``BatchStatementExecutor``, ``DeleteBatchExecutor``).

Separado de ``batch`` (R10b del refactor de reutilización 2026-09-26) sin cambios de comportamiento.
"""

from __future__ import annotations

import operator

from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any

import pandas as pd

from sqlalchemy import (
    Engine,
    Table,
)

from ._driver_quirks import _driver_decimal_context, _pymssql_plain_decimals, _register_fast_executemany
from .delete_strategies import DeleteExecutionStrategyProtocol, DeleteStrategyResolver
from .insert_strategies import InsertExecutionStrategyProtocol, InsertStrategyResolver


def validate_chunk_size(chunk_size: Any) -> int:
    """Devuelve ``chunk_size`` como ``int`` si es un entero ≥ 1; si no, ``ValueError``.

    Sin esta validación, un ``chunk_size`` negativo no generaba ningún lote (``range`` vacío): la carga no escribía nada,
    sin error, y la auditoría registraba las filas como procesadas. Con 0, fallaba al ejecutar con
    ``range() arg 3 must not be zero``. Acepta enteros de numpy; rechaza ``bool`` y decimales.
    """
    if isinstance(chunk_size, bool):
        raise ValueError(f"chunk_size debe ser un entero ≥ 1, recibido: {chunk_size!r}")
    try:
        value = operator.index(chunk_size)
    except TypeError:
        raise ValueError(f"chunk_size debe ser un entero ≥ 1, recibido: {chunk_size!r}") from None
    if value < 1:
        raise ValueError(f"chunk_size debe ser un entero ≥ 1, recibido: {chunk_size!r}")
    return value


def _commit_periodico(connection: Any, commit_hook: Callable[[Any], None] | None) -> None:
    """Commit periódico de ``commit_every_n_chunks``.

    Dentro de ``BulkCrud.bulk_session`` pasa por ``commit_hook``, que además vuelca al CSV la auditoría de las
    operaciones que ese commit confirma (M-1, audit-code de AuditManager 2026-09-25).
    """
    if commit_hook is not None:
        commit_hook(connection)
    else:
        connection.commit()


class BatchStatementExecutor:
    """Ejecutor OO de statements SQLAlchemy por lotes."""

    def __init__(
        self,
        *,
        engine: Engine,
        chunk_size: int,
        enable_fast_executemany: bool = True,
        insert_resolver: InsertStrategyResolver | None = None,
        commit_every_n_chunks: int | None = None,
    ) -> None:
        self._engine: Engine = engine
        self._chunk_size: int = validate_chunk_size(chunk_size)
        self._active_connection: Any | None = None
        # Gancho de commit que inyecta ``BulkCrud.bulk_session()`` junto con ``_active_connection``.
        self._commit_hook: Callable[[Any], None] | None = None
        self._commit_every_n_chunks: int | None = commit_every_n_chunks
        self._chunks_since_commit: int = 0
        # BLK-08 (AUDIT_CODE 2026-09-22): filas durablemente comprometidas (ya vía
        # commit periódico, ya vía el commit final) frente a las ejecutadas pero
        # aún no commiteadas — permite reportar cuántas filas sobreviven si una
        # carga falla a mitad de sesión con commit_every_n_chunks activo.
        self.rows_committed: int = 0
        self._rows_pending_commit: int = 0
        drivername: str = str(engine.url.drivername).lower()
        self._insert_strategy: InsertExecutionStrategyProtocol = (insert_resolver or InsertStrategyResolver()).resolve(
            engine.dialect.name, drivername
        )
        if enable_fast_executemany and engine.dialect.name == "mssql" and "pyodbc" in drivername:
            _register_fast_executemany(engine)

    @property
    def insert_strategy(self) -> InsertExecutionStrategyProtocol:
        """Estrategia INSERT resuelta para el motor (la usa también el UPDATE por staging para cargar la temporal)."""
        return self._insert_strategy

    def execute(
        self,
        *,
        records: Sequence[Mapping[str, Any]],
        stmt: Any,
        strategy: InsertExecutionStrategyProtocol | None = None,
    ) -> None:
        """Ejecuta un statement SQLAlchemy por batches.

        ``strategy`` sustituye a la estrategia INSERT resuelta para este motor (p.ej.
        :class:`MySQLStagingUpdateStrategy` en el UPDATE por staging); ``None`` usa la resuelta.

        Si ``_active_connection`` está activo (inyectado via ``BulkCrud.bulk_session()``),
        reutiliza esa conexión en lugar de abrir una nueva transacción por lote.

        Cuando ``commit_every_n_chunks`` está configurado y no hay conexión activa,
        usa ``engine.connect()`` (commit-as-you-go) en lugar de ``engine.begin()``
        para poder commitear lotes intermedios, y hace un commit final del resto.
        """
        if self._active_connection is not None:
            self._execute_on_connection(self._active_connection, records, stmt, strategy)
        elif self._commit_every_n_chunks is not None:
            self._chunks_since_commit = 0
            with self._engine.connect() as connection:
                self._execute_on_connection(connection, records, stmt, strategy)
                connection.commit()
                self._chunks_since_commit = 0
                self.rows_committed += self._rows_pending_commit
                self._rows_pending_commit = 0
        else:
            with self._engine.begin() as connection:
                self._execute_on_connection(connection, records, stmt, strategy)

    def _execute_on_connection(
        self,
        connection: Any,
        records: Sequence[Mapping[str, Any]],
        stmt: Any,
        strategy: InsertExecutionStrategyProtocol | None = None,
    ) -> None:
        """Ejecuta los batches sobre una conexión ya abierta.

        Si ``commit_every_n_chunks`` está activo, commitea sobre ``connection``
        (que debe estar en modo commit-as-you-go) cada N lotes. El commit del
        resto (tail) es responsabilidad del llamador (``execute`` / ``bulk_session``).
        """
        for start in range(0, len(records), self._chunk_size):
            batch: Sequence[Mapping[str, Any]] = records[start : start + self._chunk_size]
            with _driver_decimal_context(self._engine):
                (strategy or self._insert_strategy).execute(
                    connection=connection,
                    stmt=stmt,
                    records=_pymssql_plain_decimals(self._engine, batch),
                )
            if self._commit_every_n_chunks is not None:
                self._rows_pending_commit += len(batch)
                self._chunks_since_commit += 1
                if self._chunks_since_commit >= self._commit_every_n_chunks:
                    _commit_periodico(connection, self._commit_hook)
                    self._chunks_since_commit = 0
                    self.rows_committed += self._rows_pending_commit
                    self._rows_pending_commit = 0


class DeleteBatchExecutor:
    """Template Method para ejecutar DELETE por lotes."""

    def __init__(
        self,
        *,
        engine: Engine,
        chunk_size: int,
        resolver: DeleteStrategyResolver | None = None,
        commit_every_n_chunks: int | None = None,
    ) -> None:
        self._engine: Engine = engine
        self._chunk_size: int = validate_chunk_size(chunk_size)
        self._resolver: DeleteStrategyResolver = resolver or DeleteStrategyResolver()
        # Conexión de ``BulkCrud.bulk_session()`` (P-26): el DELETE participa en la transacción de la sesión.
        self._active_connection: Any | None = None
        self._commit_hook: Callable[[Any], None] | None = None
        self._commit_every_n_chunks: int | None = commit_every_n_chunks

    def execute(self, *, table: Table, df: pd.DataFrame, pk_cols: Sequence[str]) -> None:
        """Ejecuta DELETE por lotes usando la estrategia resuelta por dialecto.

        Dentro de ``BulkCrud.bulk_session()`` usa la conexión de la sesión; fuera, una transacción propia. Con
        ``commit_every_n_chunks`` confirma cada N lotes, como INSERT y UPDATE (auditoría de bulk 2026-09-24,
        hallazgo 7: fuera de la sesión todo el DELETE iba en una sola transacción); si falla, quedan borrados los lotes
        ya confirmados.
        """
        if self._active_connection is not None:
            self._execute_on_connection(self._active_connection, table=table, df=df, pk_cols=pk_cols)
            return
        if self._commit_every_n_chunks is not None:
            with self._engine.connect() as connection:
                self._execute_on_connection(connection, table=table, df=df, pk_cols=pk_cols)
                connection.commit()
            return
        with self._engine.begin() as connection:
            self._execute_on_connection(connection, table=table, df=df, pk_cols=pk_cols)

    def _execute_on_connection(
        self, connection: Any, *, table: Table, df: pd.DataFrame, pk_cols: Sequence[str]
    ) -> None:
        strategy: DeleteExecutionStrategyProtocol = self._resolver.resolve(self._engine.dialect.name)
        batches_since_commit = 0
        for batch_df in self._iter_batches(df=df, pk_cols=pk_cols):
            self._execute_batch(
                strategy=strategy, connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols
            )
            if self._commit_every_n_chunks is not None:
                batches_since_commit += 1
                if batches_since_commit >= self._commit_every_n_chunks:
                    _commit_periodico(connection, self._commit_hook)
                    batches_since_commit = 0

    def _iter_batches(self, *, df: pd.DataFrame, pk_cols: Sequence[str]) -> Iterator[pd.DataFrame]:
        """Genera batches no vacíos para la ejecución sin materializar la lista completa."""
        pk_list = list(pk_cols)
        for start in range(0, len(df), self._chunk_size):
            batch_df: pd.DataFrame = df[pk_list].iloc[start : start + self._chunk_size]
            if not batch_df.empty:
                yield batch_df

    def _execute_batch(
        self,
        *,
        strategy: DeleteExecutionStrategyProtocol,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        """Hook del template para ejecutar cada batch."""
        with _driver_decimal_context(self._engine):
            strategy.execute(connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols)


__all__: list[str] = ["BatchStatementExecutor", "DeleteBatchExecutor", "validate_chunk_size"]
