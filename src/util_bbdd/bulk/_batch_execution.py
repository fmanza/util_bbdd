"""Helpers internos para ejecución por lotes en bulk_crud."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from sqlalchemy import Delete, Engine, Table, and_, bindparam, delete

_SQL_BASED_DELETE_DIALECTS: frozenset[str] = frozenset({"mysql", "mariadb", "mssql", "hsqldb"})


def execute_batch_statement(
    *,
    engine: Engine,
    records: Sequence[Mapping[str, Any]],
    stmt: Any,
    chunk_size: int,
) -> None:
    """Ejecuta un statement SQLAlchemy en chunks."""
    with engine.begin() as connection:
        for start in range(0, len(records), chunk_size):
            batch = records[start : start + chunk_size]
            payload = [{str(key): value for key, value in record.items()} for record in batch]
            connection.execute(stmt, payload)


def execute_delete_batch(
    *,
    engine: Engine,
    table: Table,
    table_name: str,
    df: pd.DataFrame,
    pk_cols: Sequence[str],
    chunk_size: int,
) -> None:
    """Ejecuta DELETE por lotes usando SQL nativo o SQLAlchemy según el dialecto."""
    is_sql_based: bool = engine.dialect.name in _SQL_BASED_DELETE_DIALECTS

    with engine.begin() as connection:
        for start in range(0, len(df), chunk_size):
            batch_df: pd.DataFrame = df[list(pk_cols)].iloc[start : start + chunk_size]
            if batch_df.empty:
                continue

            if is_sql_based:
                execute_sql_based_delete_batch(
                    connection=connection,
                    table_name=table_name,
                    batch_df=batch_df,
                    pk_cols=pk_cols,
                )
            else:
                execute_generic_delete_batch(
                    connection=connection,
                    table=table,
                    batch_df=batch_df,
                    pk_cols=pk_cols,
                )


def execute_sql_based_delete_batch(
    *, connection: Any, table_name: str, batch_df: pd.DataFrame, pk_cols: Sequence[str]
) -> None:
    """Ejecuta DELETE en drivers que soportan tuple-IN nativo."""
    values: list[tuple[Any, ...]] = [tuple(row[column] for column in pk_cols) for _, row in batch_df.iterrows()]
    if not values:
        return
    if not all(isinstance(value, tuple) for value in values):
        raise ValueError("❌ Los valores deben ser tuplas.")

    placeholder: str = "(" + ", ".join(["%s"] * len(pk_cols)) + ")"
    placeholders: str = ", ".join([placeholder] * len(values))
    pk_tuple: str = ", ".join(pk_cols)
    sql: str = f"DELETE FROM {table_name} WHERE ({pk_tuple}) IN ({placeholders})"
    flat_values: list[Any] = [value for row_values in values for value in row_values]
    connection.exec_driver_sql(sql, tuple(flat_values))


def execute_generic_delete_batch(
    *, connection: Any, table: Table, batch_df: pd.DataFrame, pk_cols: Sequence[str]
) -> None:
    """Ejecuta DELETE parametrizado con SQLAlchemy Core."""
    stmt: Delete = delete(table).where(and_(*(table.c[column] == bindparam(column) for column in pk_cols)))
    records = batch_df.to_dict(orient="records")
    connection.execute(stmt, records)


__all__: list[str] = [
    "execute_batch_statement",
    "execute_delete_batch",
    "execute_generic_delete_batch",
    "execute_sql_based_delete_batch",
]
