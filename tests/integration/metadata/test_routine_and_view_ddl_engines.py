"""DDL de vistas y routines y parámetros de routines con ``SyncDatabaseManager`` contra PostgreSQL y SQL Server reales.

H-10: ``get_view_ddl()``/``get_routine_ddl()`` fallaban siempre en PostgreSQL (``{esquema}`` sin rellenar).
H-17: ``get_routine_parameters()`` fallaba siempre en SQL Server (``INFORMATION_SCHEMA.PARAMETERS.PARAMETER_DEFAULT``
no existe). ``doc`` absorbía ambos errores y documentaba sin DDL ni parámetros.

Requiere ``UTIL_BBDD_TEST_POSTGRESQL_URL`` / ``UTIL_BBDD_TEST_MSSQL_URL`` (``scripts/bench_env.example.sh``); crea y
borra un schema propio.
"""

from __future__ import annotations

import os
import uuid

from collections.abc import Iterator
from typing import Any

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from util_bbdd import SyncDatabaseManager

pytestmark = pytest.mark.integration

SUFFIX = uuid.uuid4().hex[:8]


def _url(env: str) -> str:
    url = os.environ.get(env)
    if not url:
        pytest.skip(f"{env} no definida")
    return url


def _base_params(url: str) -> dict[str, Any]:
    u = make_url(url)
    return {"host": u.host, "port": u.port, "user": u.username, "password": u.password, "database": u.database}


@pytest.fixture(scope="module")
def postgresql_schema() -> Iterator[tuple[str, dict[str, Any]]]:
    url = _url("UTIL_BBDD_TEST_POSTGRESQL_URL")
    schema = f"zz_util_bbdd_rt_{SUFFIX}"
    eng = create_engine(url, isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
        conn.execute(text(f"CREATE TABLE {schema}.t (id integer PRIMARY KEY, name varchar(20))"))
        conn.execute(text(f"CREATE VIEW {schema}.v AS SELECT id, name FROM {schema}.t"))
        conn.execute(text(f"CREATE FUNCTION {schema}.f(x integer) RETURNS integer LANGUAGE sql AS 'SELECT x + 1'"))
    try:
        yield schema, {**_base_params(url), "schema": schema}
    finally:
        with eng.connect() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        eng.dispose()


@pytest.fixture(scope="module")
def sqlserver_schema() -> Iterator[tuple[str, dict[str, Any]]]:
    url = _url("UTIL_BBDD_TEST_MSSQL_URL")
    schema = f"zz_rt_{SUFFIX}"
    eng = create_engine(url, isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
        conn.execute(text(f"CREATE TABLE {schema}.t (id INT PRIMARY KEY, name VARCHAR(20))"))
        conn.execute(text(f"CREATE VIEW {schema}.v AS SELECT id, name FROM {schema}.t"))
        conn.execute(text(f"CREATE FUNCTION {schema}.f(@x INT) RETURNS INT AS BEGIN RETURN @x + 1 END"))
        conn.execute(text(f"CREATE PROCEDURE {schema}.p @x INT AS BEGIN SET NOCOUNT ON; SELECT @x END"))
    try:
        yield schema, {**_base_params(url), "schema": schema}
    finally:
        with eng.connect() as conn:
            for stmt in (f"DROP PROCEDURE {schema}.p", f"DROP FUNCTION {schema}.f", f"DROP VIEW {schema}.v",
                         f"DROP TABLE {schema}.t", f"DROP SCHEMA {schema}"):  # fmt: skip
                conn.execute(text(stmt))
        eng.dispose()


def test_postgresql_view_and_routine_ddl(postgresql_schema: tuple[str, dict[str, Any]]) -> None:
    schema, params = postgresql_schema
    with SyncDatabaseManager("postgresql", params, use_pool=False) as mgr:
        assert "FROM" in mgr.get_view_ddl("v").upper()
        ddl = mgr.get_routine_ddl("f", "FUNCTION")
        assert "CREATE OR REPLACE FUNCTION" in ddl
        assert f"{schema}.f" in ddl


def test_sqlserver_routine_parameters(sqlserver_schema: tuple[str, dict[str, Any]]) -> None:
    _schema, params = sqlserver_schema
    with SyncDatabaseManager("sqlserver", params, use_pool=False) as mgr:
        function_params = mgr.get_routine_parameters("f", "FUNCTION")
        procedure_params = mgr.get_routine_parameters("p", "PROCEDURE")
    assert any(p.name == "@x" for p in function_params)
    assert [p.name for p in procedure_params] == ["@x"]
