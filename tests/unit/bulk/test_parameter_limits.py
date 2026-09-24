"""Límite de parámetros por sentencia en MySQL/MariaDB (hallazgo P-13 del performance-audit de bulk).

El conector ``mariadb`` prepara las sentencias en el servidor, que admite como máximo 65.535 parámetros. El INSERT
multi-fila (1000 filas por sentencia) fallaba a partir de 66 columnas y el ``DELETE ... IN`` con lotes grandes o PK
compuesta, con "Prepared statement contains too many placeholders".
"""

from __future__ import annotations

import re

from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Column, Integer, MetaData, Table, insert
from sqlalchemy.dialects import mysql

from util_bbdd.bulk._execution.batch import (
    _MYSQL_MAX_STATEMENT_PARAMS,
    MySQLMultiRowInsertStrategy,
    SqlBasedDeleteStrategy,
)

pytestmark = pytest.mark.unit


def _connection() -> MagicMock:
    connection = MagicMock()
    connection.dialect = mysql.dialect()
    return connection


def _wide_table(ncols: int) -> Table:
    return Table("t", MetaData(), *(Column(f"c{i}", Integer, primary_key=(i == 0)) for i in range(ncols)))


@pytest.mark.parametrize(("ncols", "expected_rows"), [(3, [1000, 500]), (70, [936, 564]), (71, [923, 577])])
def test_multirow_insert_respects_parameter_limit(ncols: int, expected_rows: list[int]) -> None:
    connection = _connection()
    records = [{f"c{i}": row * 1000 + i for i in range(ncols)} for row in range(1500)]

    MySQLMultiRowInsertStrategy().execute(connection=connection, stmt=insert(_wide_table(ncols)), records=records)

    params = [call.args[1] for call in connection.execute.call_args_list]
    assert [len(p) // ncols for p in params] == expected_rows
    assert all(len(p) <= _MYSQL_MAX_STATEMENT_PARAMS for p in params)
    assert sorted(v for p in params for k, v in p.items() if k.endswith("_0")) == [r * 1000 for r in range(1500)]


def _placeholders(stmt: object) -> int:
    return len(re.findall(r":pk_\d+_\d+", str(stmt)))


@pytest.mark.parametrize("dialect_name", ["mysql", "mariadb"])
def test_delete_composite_pk_respects_parameter_limit(dialect_name: str) -> None:
    connection = _connection()
    connection.dialect.name = dialect_name
    table = Table("t", MetaData(), Column("k1", Integer, primary_key=True), Column("k2", Integer, primary_key=True))
    rows = 40_000
    batch_df = pd.DataFrame({"k1": range(rows), "k2": range(rows)})

    SqlBasedDeleteStrategy().execute(connection=connection, table=table, batch_df=batch_df, pk_cols=["k1", "k2"])

    calls = connection.execute.call_args_list
    assert [_placeholders(call.args[0]) for call in calls] == [65_534, 14_466]
    deleted = sorted(v for call in calls for k, v in call.args[1].items() if k.endswith("_0"))
    assert deleted == list(range(rows))
