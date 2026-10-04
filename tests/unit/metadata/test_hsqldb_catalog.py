"""``HSQLDBCatalog`` (parseo sin servidor) y ``DbapiCatalogExecutor`` sobre un driver DB-API real (``sqlite3``)."""

from __future__ import annotations

import sqlite3

import pytest

from util_bbdd.metadata import ALL_KINDS, CatalogSource, Kind, RoutineKey, get_catalog_dialect
from util_bbdd.metadata._paramstyle import placeholders
from util_bbdd.metadata.hsqldb.catalog import HSQLDBCatalog
from util_bbdd.metadata.source import DbapiCatalogExecutor

HS = HSQLDBCatalog()


def test_registered_without_sqlalchemy_dialect() -> None:
    assert type(get_catalog_dialect("hsqldb")) is HSQLDBCatalog
    assert HS.sqlalchemy_names == frozenset()


@pytest.mark.parametrize("kind", sorted(ALL_KINDS, key=lambda k: k.value))
def test_queries_never_use_registry_views_that_hsqldb_lacks(kind: Kind) -> None:
    query = HS.query(kind, filtered=True)
    assert query is not None
    assert set(placeholders(query.sql)) <= {"schema", "tables"}
    assert "INFORMATION_SCHEMA.INDEXES" not in query.sql  # H-19: no existe en HSQLDB 2.x


def test_parse_columns() -> None:
    rows = [
        ("T", "ID", 1, "INTEGER", "NO", None, None, 32, 0, None, None, "YES", "BY DEFAULT", "NEVER", None),
        (
            "T",
            "CODE",
            2,
            "CHARACTER VARYING",
            "NO",
            None,
            20,
            None,
            None,
            "código",
            "SQL_TEXT",
            "NO",
            None,
            "NEVER",
            None,
        ),
        ("T", "N", 3, "NUMERIC", "YES", "0.00", None, 12, 2, None, None, "NO", None, "NEVER", None),
        ("T", "G", 4, "INTEGER", "YES", None, None, 32, 0, None, None, "NO", None, "ALWAYS", "N*2"),
    ]
    ident, code, n, g = HS.parse(Kind.COLUMNS, rows, "S")
    assert (ident.identity, ident.precision) == ("by default", None)
    assert (code.data_type, code.length, code.comment, code.collation) == ("CHARACTER VARYING(20)", 20, "código", None)
    assert (n.data_type, n.precision, n.scale, n.default) == ("NUMERIC(12,2)", 12, 2, "0.00")
    assert (g.generated, g.default) == ("N*2", None)


def test_parse_checks_skip_generated_not_null() -> None:
    rows = [("T", "SYS_CT_10092", "S.T.CODE IS NOT NULL"), ("T", "CK_X", "S.T.X>=0")]
    assert [c.name for c in HS.parse(Kind.CHECKS, rows, "S")] == ["CK_X"]


def test_parse_indexes_and_routines() -> None:
    ix = HS.parse(Kind.INDEXES, [("T", "PK_T", False, "PRIMARY KEY", "ID", 1), ("T", "IX", True, None, "A", 1)], "S")
    assert [(i.primary, i.unique) for i in ix] == [(True, True), (False, False)]
    (routine,) = HS.parse(Kind.ROUTINES, [("F", "F_1", "FUNCTION", "INTEGER", "CREATE FUNCTION …", None)], "S")
    assert (routine.key, routine.return_type, routine.language) == (RoutineKey("F", "F_1", "FUNCTION"), "INTEGER", "SQL")
    (param,) = HS.parse(Kind.ROUTINE_PARAMETERS, [("F", "F_1", 1, "X", "IN", "INTEGER")], "S")
    assert param.routine.matches(routine.key)


def test_normalize_name_like_oracle() -> None:
    assert (HS.normalize_name("zz_gold"), HS.normalize_name("Mixed"), HS.normalize_name('"low"')) == (
        "ZZ_GOLD",
        "Mixed",
        "low",
    )


@pytest.mark.parametrize("paramstyle", ["qmark", "named"])
def test_dbapi_executor_translates_to_the_driver_paramstyle(paramstyle: str) -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript("CREATE TABLE a (id INTEGER PRIMARY KEY); CREATE TABLE b (id INTEGER); CREATE TABLE c (x INT);")
    source = CatalogSource(
        get_catalog_dialect("sqlite"),
        DbapiCatalogExecutor(conn, paramstyle),  # type: ignore[arg-type]
        source_id="dbapi",
    )
    snapshot = source.snapshot(kinds={Kind.TABLES, Kind.COLUMNS}, tables=["a", "b"])
    assert [t.name for t in snapshot.tables()] == ["a", "b"]
    assert source.snapshot(kinds={Kind.DATABASE}).database() is not None  # SQL sin parámetros
    conn.close()
