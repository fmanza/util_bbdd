"""Ejecutores OO para operaciones batch internas de bulk_crud."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import pandas as pd

from sqlalchemy import Delete, Engine, Table, and_, bindparam, delete, text

_DEFAULT_SQL_BASED_DELETE_DIALECTS: frozenset[str] = frozenset({"mysql", "mariadb", "mssql", "hsqldb"})


class DeleteExecutionStrategyProtocol(Protocol):
    """Contrato para ejecutar DELETE de un batch."""

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        """Ejecuta borrado de un batch."""


class SqlBasedDeleteStrategy:
    """Estrategia de DELETE SQL parametrizado para motores soportados."""

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        values: list[tuple[Any, ...]] = [tuple(row[column] for column in pk_cols) for _, row in batch_df.iterrows()]
        if not values:
            return

        preparer = connection.dialect.identifier_preparer
        quoted_table: str = preparer.format_table(table)
        quoted_pk_cols: list[str] = [preparer.quote(column) for column in pk_cols]

        params: dict[str, Any] = {}
        if len(pk_cols) == 1:
            pk_col: str = quoted_pk_cols[0]
            placeholders: list[str] = []
            for row_index, row_values in enumerate(values):
                bind_name: str = f"pk_{row_index}_0"
                placeholders.append(f":{bind_name}")
                params[bind_name] = row_values[0]
            sql = f"DELETE FROM {quoted_table} WHERE {pk_col} IN ({', '.join(placeholders)})"
        else:
            row_placeholders: list[str] = []
            for row_index, row_values in enumerate(values):
                bind_tokens: list[str] = []
                for column_index, raw_value in enumerate(row_values):
                    bind_name = f"pk_{row_index}_{column_index}"
                    bind_tokens.append(f":{bind_name}")
                    params[bind_name] = raw_value
                row_placeholders.append(f"({', '.join(bind_tokens)})")

            pk_tuple_sql: str = ", ".join(quoted_pk_cols)
            sql = f"DELETE FROM {quoted_table} WHERE ({pk_tuple_sql}) IN ({', '.join(row_placeholders)})"

        connection.execute(text(sql), params)


class GenericDeleteStrategy:
    """Estrategia de DELETE genérico con SQLAlchemy Core."""

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        stmt: Delete = delete(table).where(and_(*(table.c[column] == bindparam(column) for column in pk_cols)))
        records = batch_df.to_dict(orient="records")
        connection.execute(stmt, records)


class DeleteStrategyResolver:
    """Resuelve estrategia DELETE según dialecto."""

    def __init__(
        self,
        *,
        sql_based_dialects: frozenset[str] | None = None,
        sql_based_strategy: DeleteExecutionStrategyProtocol | None = None,
        generic_strategy: DeleteExecutionStrategyProtocol | None = None,
    ) -> None:
        self._sql_based_dialects: frozenset[str] = sql_based_dialects or _DEFAULT_SQL_BASED_DELETE_DIALECTS
        self._sql_based_strategy: DeleteExecutionStrategyProtocol = sql_based_strategy or SqlBasedDeleteStrategy()
        self._generic_strategy: DeleteExecutionStrategyProtocol = generic_strategy or GenericDeleteStrategy()

    def resolve(self, dialect_name: str) -> DeleteExecutionStrategyProtocol:
        """Devuelve la estrategia adecuada para el dialecto indicado."""
        if dialect_name in self._sql_based_dialects:
            return self._sql_based_strategy
        return self._generic_strategy


class BatchStatementExecutor:
    """Ejecutor OO de statements SQLAlchemy por lotes."""

    def __init__(self, *, engine: Engine, chunk_size: int) -> None:
        self._engine: Engine = engine
        self._chunk_size: int = chunk_size

    def execute(self, *, records: Sequence[Mapping[str, Any]], stmt: Any) -> None:
        """Ejecuta un statement SQLAlchemy por batches."""
        with self._engine.begin() as connection:
            for start in range(0, len(records), self._chunk_size):
                batch = records[start : start + self._chunk_size]
                payload = [{str(key): value for key, value in record.items()} for record in batch]
                connection.execute(stmt, payload)


class DeleteBatchExecutor:
    """Template Method para ejecutar DELETE por lotes."""

    def __init__(
        self,
        *,
        engine: Engine,
        chunk_size: int,
        resolver: DeleteStrategyResolver | None = None,
    ) -> None:
        self._engine: Engine = engine
        self._chunk_size: int = chunk_size
        self._resolver: DeleteStrategyResolver = resolver or DeleteStrategyResolver()

    def execute(self, *, table: Table, df: pd.DataFrame, pk_cols: Sequence[str]) -> None:
        """Ejecuta DELETE por lotes usando la estrategia resuelta por dialecto."""
        strategy: DeleteExecutionStrategyProtocol = self._resolver.resolve(self._engine.dialect.name)
        with self._engine.begin() as connection:
            for batch_df in self._iter_batches(df=df, pk_cols=pk_cols):
                self._execute_batch(
                    strategy=strategy, connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols
                )

    def _iter_batches(self, *, df: pd.DataFrame, pk_cols: Sequence[str]) -> Sequence[pd.DataFrame]:
        """Genera batches no vacíos para la ejecución."""
        batches: list[pd.DataFrame] = []
        for start in range(0, len(df), self._chunk_size):
            batch_df: pd.DataFrame = df[list(pk_cols)].iloc[start : start + self._chunk_size]
            if not batch_df.empty:
                batches.append(batch_df)
        return batches

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
        strategy.execute(connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols)


__all__: list[str] = [
    "BatchStatementExecutor",
    "DeleteBatchExecutor",
    "DeleteExecutionStrategyProtocol",
    "DeleteStrategyResolver",
    "GenericDeleteStrategy",
    "SqlBasedDeleteStrategy",
]
