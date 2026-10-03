"""``SQLiteCatalog`` contra SQLite en memoria (sin servidor): snapshot completo, filtro por tablas y límites."""

from __future__ import annotations

import pytest

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from util_bbdd.metadata import ALL_KINDS, CatalogSource, Kind, get_catalog_dialect
from util_bbdd.metadata.sqlite.catalog import EXPRESSION, SQLiteCatalog

DDL = [
    "CREATE TABLE p (id INTEGER PRIMARY KEY AUTOINCREMENT, code VARCHAR(20) NOT NULL UNIQUE, "
    "x NUMERIC(12,2) DEFAULT 0, g INT GENERATED ALWAYS AS (x * 2), CHECK (x >= 0))",
    "CREATE TABLE c (id INT, pid INT REFERENCES p(id) ON DELETE CASCADE, label TEXT, PRIMARY KEY (id, pid))",
    "CREATE INDEX ix_c_label ON c (label)",
    "CREATE INDEX ix_c_expr ON c (lower(label))",
    "CREATE VIEW v AS SELECT id, code FROM p",
]


@pytest.fixture
def engine() -> Engine:
    eng = create_engine("sqlite://", poolclass=StaticPool)
    with eng.begin() as conn:
        for stmt in DDL:
            conn.execute(text(stmt))
    return eng


def test_registered() -> None:
    assert type(get_catalog_dialect("sqlite")) is SQLiteCatalog


def test_full_snapshot(engine: Engine) -> None:
    s = CatalogSource.from_engine(engine).snapshot()
    assert s.schema == "main"
    assert [t.name for t in s.tables()] == ["c", "p"]  # sin sqlite_sequence
    assert s.views()[0].definition == "CREATE VIEW v AS SELECT id, code FROM p"
    cols = {c.name: c for c in s.columns("p")}
    assert (cols["id"].identity, cols["code"].length, cols["code"].nullable) == ("by default", 20, False)
    assert (cols["x"].precision, cols["x"].scale, cols["x"].default) == (12, 2, "0")
    assert cols["g"].generated == EXPRESSION
    assert [c.name for c in s.columns("v")] == ["id", "code"]
    pk = s.primary_key("c")
    assert pk is not None and pk.columns == ("id", "pid")
    assert s.uniques("p")[0].columns == ("code",)
    fk = s.foreign_keys("c")[0]
    assert (fk.ref_table, fk.columns, fk.ref_columns, fk.on_delete) == ("p", ("pid",), ("id",), "CASCADE")
    indexes = {ix.name: ix for ix in s.indexes("c")}
    assert indexes["ix_c_label"].columns == ("label",)
    assert indexes["ix_c_expr"].columns == (EXPRESSION,)
    assert any(ix.primary for ix in indexes.values())
    assert [(i.table, i.column) for i in s.identity("p")] == [("p", "id")]
    assert s.checks("p") == () and s.routines() == ()  # SQLite no los expone por PRAGMA / no tiene routines
    database = s.database()
    assert database is not None and database.version.startswith("SQLite ")


def test_one_query_per_supported_kind(engine: Engine) -> None:
    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda *a: statements.append(a[2]))
    CatalogSource.from_engine(engine).snapshot("main")
    dialect = SQLiteCatalog()
    assert len(statements) == sum(1 for k in ALL_KINDS if dialect.query(k) is not None)


def test_filtered_snapshot(engine: Engine) -> None:
    s = CatalogSource.from_engine(engine).snapshot(kinds={Kind.TABLES, Kind.COLUMNS}, tables=["p"])
    assert [t.name for t in s.tables()] == ["p"]
    assert s.columns("c") == ()


def test_other_schema_is_empty_not_main(engine: Engine) -> None:
    s = CatalogSource.from_engine(engine).snapshot("attached", kinds={Kind.TABLES, Kind.COLUMNS})
    assert s.tables() == () and s.columns("p") == ()
