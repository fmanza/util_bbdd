"""DELETE en SQL Server con ``SqlBasedDeleteStrategy`` (hallazgo P-05 del performance-audit de bulk).

SQL Server admite como máximo 2100 parámetros por petición y no admite constructores de fila en ``IN``
(``WHERE (a, b) IN ((..), (..))``). La estrategia debe trocear la PK simple en sentencias de como mucho
``_MSSQL_MAX_DELETE_PARAMS`` parámetros y resolver la PK compuesta con ``DELETE ... WHERE a = ? AND b = ?``.
Los demás dialectos conservan una sola sentencia por lote.
"""

from __future__ import annotations

import re

from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Column, Integer, MetaData, Table
from sqlalchemy.dialects import mssql, mysql
from sqlalchemy.sql.dml import Delete

from util_bbdd.bulk._execution.batch import _MSSQL_MAX_DELETE_PARAMS, SqlBasedDeleteStrategy

pytestmark = pytest.mark.unit


def _single_pk_table() -> Table:
    return Table("T", MetaData(), Column("ID", Integer, primary_key=True))


def _composite_pk_table() -> Table:
    return Table("T", MetaData(), Column("K1", Integer, primary_key=True), Column("K2", Integer, primary_key=True))


def _connection(dialect: object) -> MagicMock:
    connection = MagicMock()
    connection.dialect = dialect
    return connection


def _placeholders(stmt: object) -> int:
    return len(re.findall(r":pk_\d+_\d+", str(stmt)))


def test_mssql_single_pk_never_exceeds_parameter_limit() -> None:
    rows = 4_500
    connection = _connection(mssql.dialect())
    batch_df = pd.DataFrame({"ID": range(rows)})

    SqlBasedDeleteStrategy().execute(connection=connection, table=_single_pk_table(), batch_df=batch_df, pk_cols=["ID"])

    calls = connection.execute.call_args_list
    assert [_placeholders(call.args[0]) for call in calls] == [2_000, 2_000, 500]
    assert all(_placeholders(call.args[0]) <= _MSSQL_MAX_DELETE_PARAMS < 2_100 for call in calls)
    # Todas las PK se borran exactamente una vez.
    deleted = [value for call in calls for value in call.args[1].values()]
    assert sorted(deleted) == list(range(rows))


def test_mssql_composite_pk_does_not_use_row_value_constructor() -> None:
    connection = _connection(mssql.dialect())
    batch_df = pd.DataFrame({"K1": [1, 1, 2], "K2": [10, 20, 10]})

    SqlBasedDeleteStrategy().execute(
        connection=connection, table=_composite_pk_table(), batch_df=batch_df, pk_cols=["K1", "K2"]
    )

    assert connection.execute.call_count == 1
    stmt, records = connection.execute.call_args.args
    assert isinstance(stmt, Delete)
    sql = str(stmt.compile(dialect=mssql.dialect()))
    assert ") IN (" not in sql
    assert "WHERE [T].[K1] = :K1 AND [T].[K2] = :K2" in sql
    assert records == [{"K1": 1, "K2": 10}, {"K1": 1, "K2": 20}, {"K1": 2, "K2": 10}]


def test_mysql_keeps_single_statement_per_batch() -> None:
    connection = _connection(mysql.dialect())
    batch_df = pd.DataFrame({"ID": range(4_500)})

    SqlBasedDeleteStrategy().execute(connection=connection, table=_single_pk_table(), batch_df=batch_df, pk_cols=["ID"])

    assert connection.execute.call_count == 1
    assert _placeholders(connection.execute.call_args.args[0]) == 4_500


def test_mysql_composite_pk_keeps_row_value_constructor() -> None:
    connection = _connection(mysql.dialect())
    batch_df = pd.DataFrame({"K1": [1, 2], "K2": [10, 20]})

    SqlBasedDeleteStrategy().execute(
        connection=connection, table=_composite_pk_table(), batch_df=batch_df, pk_cols=["K1", "K2"]
    )

    assert connection.execute.call_count == 1
    assert ") IN ((" in str(connection.execute.call_args.args[0])
