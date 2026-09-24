"""SQL generado con ``%`` en los datos (hallazgo P-23 del performance-audit de bulk).

Con paramstyle ``format``/``pyformat`` (psycopg, psycopg2, PyMySQL, mysqlclient), ``literal_binds`` duplica cada ``%``
del texto compilado porque supone que pasará por el driver con parámetros. El fichero generado se ejecuta sin
parámetros, así que ``'a%b'`` se guardaba como ``'a%%b'``. Se compila con los dialectos reales, sin servidor.
"""

from __future__ import annotations

import pytest

from sqlalchemy import Column, Integer, MetaData, String, Table, insert
from sqlalchemy.dialects.mssql.pymssql import MSDialect_pymssql
from sqlalchemy.dialects.mysql.pymysql import MySQLDialect_pymysql
from sqlalchemy.dialects.oracle.oracledb import OracleDialect_oracledb
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from sqlalchemy.dialects.sqlite.pysqlite import SQLiteDialect_pysqlite

from util_bbdd.bulk._support.sql_helpers import generate_delete_sql, generate_insert_sql, generate_update_sql

pytestmark = pytest.mark.unit

DIALECTS = [
    PGDialect_psycopg(),
    PGDialect_psycopg2(),
    MySQLDialect_pymysql(),
    MSDialect_pymssql(),
    OracleDialect_oracledb(),
    SQLiteDialect_pysqlite(),
]
# Sin textos con forma "%(nombre)s": en dialectos posicionales (SQLite) el propio compilador de SQLAlchemy los
# convierte en "?" dentro de los literales (comportamiento de SQLAlchemy, ajeno a P-23).
VALUES = ["a%b", "100%", "it's %s", "%%x"]


def _table() -> Table:
    return Table("t", MetaData(), Column("id", Integer, primary_key=True), Column("s", String(20)))


@pytest.mark.parametrize("dialect", DIALECTS, ids=lambda d: f"{d.name}+{d.driver}")
def test_insert_sql_keeps_percent_signs(dialect: object) -> None:
    table = _table()
    lines = generate_insert_sql(insert(table), [{"id": i, "s": v} for i, v in enumerate(VALUES)], dialect)

    for line, value in zip(lines, VALUES, strict=True):
        assert value.replace("'", "''") in line
        assert "%%" not in line.replace(value.replace("'", "''"), "")  # ningún % duplicado fuera del dato


@pytest.mark.parametrize("dialect", DIALECTS, ids=lambda d: f"{d.name}+{d.driver}")
def test_update_and_delete_sql_keep_percent_signs(dialect: object) -> None:
    table = _table()
    update_lines = generate_update_sql(
        table=table,
        records=[{"s": "50% off", "pk_id": 1}],
        update_cols=["s"],
        pk_param_map={"id": "pk_id"},
        pk_cols=["id"],
        dialect=dialect,
    )
    delete_lines = generate_delete_sql(
        records=[{"id": 1}],
        table=Table("t%1", MetaData(), Column("id", Integer, primary_key=True)),
        pk_cols=["id"],
        dialect=dialect,
    )

    assert "'50% off'" in update_lines[0]
    assert "%%" not in delete_lines[0]
    assert "t%1" in delete_lines[0]


def test_percent_updates_are_not_touched_for_unaffected_dialects() -> None:
    # SQLite (qmark) nunca duplicaba: el texto no cambia.
    (line,) = generate_insert_sql(insert(_table()), [{"id": 1, "s": "a%%b"}], SQLiteDialect_pysqlite())
    assert "'a%%b'" in line
