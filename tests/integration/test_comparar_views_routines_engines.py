"""``SchemaComparator``: vistas y routines leídas por lotes del catálogo de ``metadata/`` (C4, ADR-003), motor a motor.

Dos schemas con una vista y una routine iguales, una modificada y una exclusiva de cada lado: la comparación debe
encontrar exactamente esas diferencias, con una consulta de catálogo por lado para las vistas (antes una por vista y
lado). Oracle compara el schema del usuario del banco consigo mismo (no hay un segundo schema sin crear usuarios).
"""

from __future__ import annotations

import os

from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine

from util_bbdd.comparar import SchemaComparator

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class Case:
    engine: str
    url_env: str
    source: str
    target: str
    create: tuple[str, ...]
    drop: tuple[str, ...]


def _pg() -> Case:
    a, b = "zz_cmp_a", "zz_cmp_b"
    ddl = []
    for s, x in ((a, "1"), (b, "2")):
        ddl += [
            f"CREATE SCHEMA {s}",
            f"CREATE TABLE {s}.t (id integer PRIMARY KEY)",
            f"CREATE VIEW {s}.v_same AS SELECT 1 AS k",
            f"CREATE VIEW {s}.v_mod AS SELECT {x} AS y",
            f"CREATE FUNCTION {s}.f_same(a integer) RETURNS integer LANGUAGE sql AS 'SELECT a'",
            f"CREATE FUNCTION {s}.f_mod(a integer) RETURNS integer LANGUAGE sql AS 'SELECT a + {x}'",
        ]
    ddl += [
        f"CREATE VIEW {a}.v_only AS SELECT 1 AS k",
        f"CREATE FUNCTION {b}.f_only() RETURNS integer LANGUAGE sql AS 'SELECT 1'",
    ]
    return Case(
        "postgresql",
        "UTIL_BBDD_TEST_POSTGRESQL_URL",
        a,
        b,
        tuple(ddl),
        tuple(f"DROP SCHEMA IF EXISTS {s} CASCADE" for s in (a, b)),
    )


def _my(engine: str, env: str) -> Case:
    a, b = "zz_util_bbdd_cmp_a", "zz_util_bbdd_cmp_b"  # el usuario del banco solo crea bases zz_util_bbdd*
    ddl = []
    for s, x in ((a, "1"), (b, "2")):
        ddl += [
            f"CREATE DATABASE {s}",
            f"CREATE TABLE {s}.t (id INT PRIMARY KEY)",
            f"CREATE VIEW {s}.v_same AS SELECT 1 AS k",
            f"CREATE VIEW {s}.v_mod AS SELECT {x} AS y",
            f"CREATE FUNCTION {s}.f_same(a INT) RETURNS INT DETERMINISTIC RETURN a",
            f"CREATE FUNCTION {s}.f_mod(a INT) RETURNS INT DETERMINISTIC RETURN a + {x}",
        ]
    ddl += [
        f"CREATE VIEW {a}.v_only AS SELECT 1 AS k",
        f"CREATE FUNCTION {b}.f_only() RETURNS INT DETERMINISTIC RETURN 1",
    ]
    return Case(engine, env, a, b, tuple(ddl), tuple(f"DROP DATABASE IF EXISTS {s}" for s in (a, b)))


def _mssql() -> Case:
    a, b = "zz_cmp_a", "zz_cmp_b"
    ddl, drop = [], []
    for s, x in ((a, "1"), (b, "2")):
        ddl += [
            f"CREATE SCHEMA {s}",
            f"CREATE TABLE {s}.t (id INT PRIMARY KEY)",
            f"CREATE VIEW {s}.v_same AS SELECT 1 AS k",
            f"CREATE VIEW {s}.v_mod AS SELECT {x} AS y",
            f"CREATE FUNCTION {s}.f_same(@a INT) RETURNS INT AS BEGIN RETURN @a END",
            f"CREATE FUNCTION {s}.f_mod(@a INT) RETURNS INT AS BEGIN RETURN @a + {x} END",
        ]
        drop += [
            *(f"DROP VIEW IF EXISTS {s}.{v}" for v in ("v_same", "v_mod", "v_only")),
            *(f"DROP FUNCTION IF EXISTS {s}.{f}" for f in ("f_same", "f_mod", "f_only")),
            f"DROP TABLE IF EXISTS {s}.t",
            f"IF SCHEMA_ID('{s}') IS NOT NULL EXEC('DROP SCHEMA {s}')",
        ]
    ddl += [
        f"CREATE VIEW {a}.v_only AS SELECT 1 AS k",
        f"CREATE FUNCTION {b}.f_only() RETURNS INT AS BEGIN RETURN 1 END",
    ]
    return Case("sqlserver", "UTIL_BBDD_TEST_MSSQL_URL", a, b, tuple(ddl), tuple(drop))


def _oracle() -> Case:
    return Case(
        "oracle",
        "UTIL_BBDD_TEST_ORACLE_URL",
        "BENCH",
        "BENCH",
        (
            "CREATE TABLE zz_cmp_t (id NUMBER PRIMARY KEY)",
            "CREATE VIEW zz_cmp_v AS SELECT id FROM zz_cmp_t",
            "CREATE OR REPLACE FUNCTION zz_cmp_f(a NUMBER) RETURN NUMBER IS BEGIN RETURN a; END;",
            "CREATE OR REPLACE PACKAGE zz_cmp_pkg AS PROCEDURE p; END zz_cmp_pkg;",
        ),
        (
            "DROP PACKAGE zz_cmp_pkg",
            "DROP FUNCTION zz_cmp_f",
            "DROP VIEW zz_cmp_v",
            "DROP TABLE zz_cmp_t PURGE",
        ),
    )


CASES = [
    _pg(),
    _my("mysql", "UTIL_BBDD_TEST_MYSQL_URL"),
    _my("mariadb", "UTIL_BBDD_TEST_MARIADB_URL"),
    _mssql(),
    _oracle(),
]


def _run(eng: Engine, statements: tuple[str, ...], *, ignore: bool) -> None:
    with eng.connect() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception:  # noqa: BLE001 - limpieza de objetos inexistentes
                if not ignore:
                    raise


@pytest.fixture(scope="module", params=CASES, ids=lambda c: c.engine)
def case(request: pytest.FixtureRequest) -> Iterator[tuple[Case, Engine]]:
    c: Case = request.param
    if not os.environ.get(c.url_env):
        pytest.skip(f"{c.url_env} no definida")
    eng = create_engine(os.environ[c.url_env], isolation_level="AUTOCOMMIT")
    _run(eng, c.drop, ignore=True)
    _run(eng, c.create, ignore=False)
    try:
        yield c, eng
    finally:
        _run(eng, c.drop, ignore=True)
        eng.dispose()


def test_views_and_routines_differences(case: tuple[Case, Engine]) -> None:
    c, eng = case
    statements: list[str] = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(eng, "before_cursor_execute", listener)
    try:
        diff = SchemaComparator().compare(
            inspect(eng),
            inspect(eng),
            source_schema=c.source,
            target_schema=c.target,
            include_tables=False,
            include_routines=True,
        )
    finally:
        event.remove(eng, "before_cursor_execute", listener)

    views = sorted((d.view_name.lower(), d.status) for d in diff.view_diffs)
    routines = sorted((d.routine_name.lower(), d.status) for d in diff.routine_diffs)
    if c.source == c.target:  # Oracle: el schema consigo mismo, con routines sueltas y un package
        assert (views, routines) == ([], [])
    else:
        assert views == [("v_mod", "modified"), ("v_only", "added")]
        assert routines == [("f_mod", "modified"), ("f_only", "removed")]
        added = next(d for d in diff.view_diffs if d.status == "added")
        assert "1" in added.source_definition  # la definición viaja al informe
    # Una consulta de definiciones de vistas por lado (antes, una por vista y lado)
    view_queries = [
        s for s in statements if "definition" in s.lower() or "all_views" in s.lower() or "sql_modules" in s.lower()
    ]
    assert len(view_queries) <= 4, view_queries
