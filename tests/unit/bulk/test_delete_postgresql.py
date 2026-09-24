"""DELETE en PostgreSQL con una sentencia por lote (hallazgo P-10 del performance-audit de bulk).

Antes era un ``executemany`` de una sentencia por fila (35K filas/s con psycopg 3, 3,7K con psycopg2). Ahora, un
parámetro array por columna de la PK: ``= ANY(:ids)`` con PK simple y ``USING unnest(...)`` con PK compuesta
(``(a, b) IN (...)`` resultó 17× más lento en PostgreSQL).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table
from sqlalchemy.dialects import postgresql

from util_bbdd.bulk._execution.batch import (
    DeleteStrategyResolver,
    GenericDeleteStrategy,
    PostgreSQLAnyDeleteStrategy,
    SqlBasedDeleteStrategy,
)

pytestmark = pytest.mark.unit


def _connection() -> MagicMock:
    connection = MagicMock()
    connection.dialect = postgresql.dialect()
    return connection


def _sql(connection: MagicMock) -> str:
    stmt = connection.execute.call_args.args[0]
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_simple_pk_uses_any_with_one_array_parameter() -> None:
    connection = _connection()
    table = Table("t", MetaData(), Column("id", Integer, primary_key=True), schema="s")

    PostgreSQLAnyDeleteStrategy().execute(
        connection=connection, table=table, batch_df=pd.DataFrame({"id": [3, 1, 2]}), pk_cols=["id"]
    )

    assert connection.execute.call_count == 1
    assert _sql(connection) == "DELETE FROM s.t WHERE s.t.id = ANY (%(pk_ids)s::INTEGER[])"
    assert connection.execute.call_args.args[1] == {"pk_ids": [3, 1, 2]}
    assert all(type(v) is int for v in connection.execute.call_args.args[1]["pk_ids"])  # sin numpy.int64


def test_composite_pk_uses_unnest_with_one_array_per_column() -> None:
    connection = _connection()
    table = Table(
        "Order",  # nombre que exige comillas
        MetaData(),
        Column("k1", Integer, primary_key=True),
        Column("Code", String(10), primary_key=True),
        Column("at", DateTime, primary_key=True),
    )
    at = pd.Timestamp("2026-01-01 10:00:00")
    batch_df = pd.DataFrame({"k1": [1, 2], "Code": ["a", "b"], "at": [at, at]})

    PostgreSQLAnyDeleteStrategy().execute(
        connection=connection, table=table, batch_df=batch_df, pk_cols=["k1", "Code", "at"]
    )

    assert connection.execute.call_count == 1
    assert _sql(connection) == (
        'DELETE FROM "Order" AS _bulk_del_t USING unnest(CAST(%(pk_0)s::INTEGER[] AS INTEGER[]), '
        "CAST(%(pk_1)s::VARCHAR(10)[] AS VARCHAR(10)[]), CAST(%(pk_2)s::TIMESTAMP WITHOUT TIME ZONE[] AS TIMESTAMP "
        'WITHOUT TIME ZONE[])) AS _bulk_del_k(k1, "Code", at) WHERE _bulk_del_t.k1 = _bulk_del_k.k1 AND '
        '_bulk_del_t."Code" = _bulk_del_k."Code" AND _bulk_del_t.at = _bulk_del_k.at'
    )
    assert connection.execute.call_args.args[1] == {"pk_0": [1, 2], "pk_1": ["a", "b"], "pk_2": [at, at]}


@pytest.mark.parametrize(
    ("dialect_name", "expected"),
    [
        ("postgresql", PostgreSQLAnyDeleteStrategy),
        ("mysql", SqlBasedDeleteStrategy),
        ("mssql", SqlBasedDeleteStrategy),
        ("sqlite", GenericDeleteStrategy),
        ("oracle", GenericDeleteStrategy),
    ],
)
def test_resolver_routes_postgresql_to_array_strategy(dialect_name: str, expected: type) -> None:
    assert isinstance(DeleteStrategyResolver().resolve(dialect_name), expected)


def test_resolver_accepts_custom_postgresql_strategy() -> None:
    custom = GenericDeleteStrategy()

    assert DeleteStrategyResolver(postgresql_strategy=custom).resolve("postgresql") is custom
