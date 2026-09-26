"""Estrategias DELETE por motor y su resolución (``DeleteStrategyResolver``).

Separado de ``batch`` (R10b del refactor de reutilización 2026-09-26) sin cambios de comportamiento.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

import pandas as pd

from sqlalchemy import (
    Delete,
    Table,
    and_,
    any_,
    bindparam,
    delete,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY

from ._driver_quirks import _MSSQL_MAX_DELETE_PARAMS, _MYSQL_MAX_STATEMENT_PARAMS

_DEFAULT_SQL_BASED_DELETE_DIALECTS: frozenset[str] = frozenset({"mysql", "mariadb", "mssql", "hsqldb"})


# Parámetros máximos por sentencia ``DELETE ... IN (...)`` por dialecto; sin entrada, una sentencia por lote.
_MAX_DELETE_PARAMS: dict[str, int] = {
    "mssql": _MSSQL_MAX_DELETE_PARAMS,
    "mysql": _MYSQL_MAX_STATEMENT_PARAMS,
    "mariadb": _MYSQL_MAX_STATEMENT_PARAMS,
}


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
    """Estrategia de DELETE SQL parametrizado para motores soportados.

    SQL Server (P-05, performance-audit de bulk 2026-09-23): admite como máximo 2100 parámetros por petición y no
    admite constructores de fila en ``IN``. La PK simple se trocea en sentencias de ``_MSSQL_MAX_DELETE_PARAMS``
    parámetros como máximo y la PK compuesta se delega en :class:`GenericDeleteStrategy`
    (``DELETE ... WHERE a = ? AND b = ?`` con executemany).

    MySQL/MariaDB (P-13): el conector ``mariadb`` admite como máximo 65.535 parámetros por sentencia; el lote se trocea
    en sentencias de ``65535 // columnas de la PK`` filas. El resto de dialectos usa una sentencia por lote.
    """

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        dialect_name: str = connection.dialect.name
        if dialect_name == "mssql" and len(pk_cols) > 1:
            GenericDeleteStrategy().execute(connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols)
            return
        max_params: int | None = _MAX_DELETE_PARAMS.get(dialect_name)
        if max_params is None:
            self._execute_statement(connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols)
            return
        rows_per_statement: int = max(1, max_params // len(pk_cols))
        for start in range(0, len(batch_df), rows_per_statement):
            self._execute_statement(
                connection=connection,
                table=table,
                batch_df=batch_df.iloc[start : start + rows_per_statement],
                pk_cols=pk_cols,
            )

    def _execute_statement(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        """Ejecuta un único ``DELETE ... WHERE pk IN (...)`` con todas las filas de ``batch_df``."""
        values: list[tuple[Any, ...]] = [tuple(r) for r in batch_df[pk_cols].itertuples(index=False, name=None)]
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


class PostgreSQLAnyDeleteStrategy:
    """DELETE para PostgreSQL con una sentencia por lote (P-10, performance-audit de bulk 2026-09-23).

    Un parámetro array por columna de la PK, sea cual sea el tamaño del lote:

    - PK simple: ``DELETE FROM t WHERE pk = ANY(:ids)``.
    - PK compuesta: ``DELETE FROM t AS tgt USING unnest(CAST(:k0 AS tipo[]), ...) AS k(a, b) WHERE tgt.a = k.a AND ...``.
      No se usa ``(a, b) IN ((..), ..)``: PostgreSQL lo resuelve mucho peor (100K filas en 35–47 s).

    Antes era un ``executemany`` de una sentencia por fila. 100K filas (mediana de 3, PostgreSQL 17 en local):
    PK simple 2,8 s → 1,0 s con psycopg 3 y 26,8 s → 1,0 s con psycopg2; PK compuesta 2,8 s → 1,2 s y 28,8 s → 1,2 s.
    """

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        if len(pk_cols) == 1:
            column = table.c[pk_cols[0]]
            stmt: Any = delete(table).where(column == any_(bindparam("pk_ids", type_=ARRAY(column.type))))
            connection.execute(stmt, {"pk_ids": batch_df[pk_cols[0]].tolist()})
            return

        dialect = connection.dialect
        preparer = dialect.identifier_preparer
        quoted: list[str] = [preparer.quote(column) for column in pk_cols]
        arrays: str = ", ".join(
            f"CAST(:pk_{i} AS {table.c[column].type.compile(dialect=dialect)}[])" for i, column in enumerate(pk_cols)
        )
        condition: str = " AND ".join(f"_bulk_del_t.{q} = _bulk_del_k.{q}" for q in quoted)
        sql: str = (
            f"DELETE FROM {preparer.format_table(table)} AS _bulk_del_t "
            f"USING unnest({arrays}) AS _bulk_del_k({', '.join(quoted)}) WHERE {condition}"
        )
        stmt = text(sql).bindparams(
            *(bindparam(f"pk_{i}", type_=ARRAY(table.c[column].type)) for i, column in enumerate(pk_cols))
        )
        connection.execute(stmt, {f"pk_{i}": batch_df[column].tolist() for i, column in enumerate(pk_cols)})


class DeleteStrategyResolver:
    """Resuelve estrategia DELETE según dialecto."""

    def __init__(
        self,
        *,
        sql_based_dialects: frozenset[str] | None = None,
        sql_based_strategy: DeleteExecutionStrategyProtocol | None = None,
        generic_strategy: DeleteExecutionStrategyProtocol | None = None,
        postgresql_strategy: DeleteExecutionStrategyProtocol | None = None,
    ) -> None:
        self._sql_based_dialects: frozenset[str] = sql_based_dialects or _DEFAULT_SQL_BASED_DELETE_DIALECTS
        self._sql_based_strategy: DeleteExecutionStrategyProtocol = sql_based_strategy or SqlBasedDeleteStrategy()
        self._generic_strategy: DeleteExecutionStrategyProtocol = generic_strategy or GenericDeleteStrategy()
        self._postgresql_strategy: DeleteExecutionStrategyProtocol = (
            postgresql_strategy or PostgreSQLAnyDeleteStrategy()
        )

    def resolve(self, dialect_name: str) -> DeleteExecutionStrategyProtocol:
        """Devuelve la estrategia adecuada para el dialecto indicado."""
        if dialect_name in self._sql_based_dialects:
            return self._sql_based_strategy
        if dialect_name == "postgresql":
            return self._postgresql_strategy
        return self._generic_strategy


__all__: list[str] = [
    "DeleteExecutionStrategyProtocol",
    "DeleteStrategyResolver",
    "GenericDeleteStrategy",
    "PostgreSQLAnyDeleteStrategy",
    "SqlBasedDeleteStrategy",
]
