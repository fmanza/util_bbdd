"""``doc``: filas neutras de la documentación desde el snapshot de ``metadata/`` (D1, ADR-003)."""

from __future__ import annotations

from typing import Any

from util_bbdd.doc.application.use_cases.catalog_rows import CatalogRows
from util_bbdd.metadata.model import (
    ColumnMeta,
    ForeignKeyMeta,
    IndexMeta,
    Kind,
    PrimaryKeyMeta,
    RoutineKey,
    RoutineMeta,
    RoutineParameterMeta,
    SchemaSnapshot,
    TableMeta,
    UniqueMeta,
    ViewMeta,
)

DATA: dict[Kind, tuple[Any, ...]] = {
    Kind.TABLES: (TableMeta("t", "tabla", "utf8mb4_bin"), TableMeta("u")),
    Kind.VIEWS: (
        ViewMeta("v", " SELECT 1", "vista"),
        ViewMeta("w", "CREATE VIEW w AS SELECT 2"),
        ViewMeta("mv", "SELECT 3", materialized=True),
    ),  # fmt: skip
    Kind.COLUMNS: (
        ColumnMeta("t", "id", 1, "integer", "integer", False, identity="always", default="nextval('s')"),
        ColumnMeta("t", "code", 2, "character varying(20)", "character varying", True, default="'x'", comment="c"),
        ColumnMeta("t", "g", 3, "integer", "integer", True, generated="(id * 2)"),
    ),
    Kind.PRIMARY_KEYS: (PrimaryKeyMeta("t", "pk_t", ("id",)),),
    Kind.FOREIGN_KEYS: (ForeignKeyMeta("u", "fk", ("a", "b"), "s", "t", ("x", "y"), "CASCADE"),),
    Kind.UNIQUES: (UniqueMeta("t", "uk", ("code", "g")),),
    Kind.INDEXES: (IndexMeta("t", "ix", ("code", "lower(code)"), True, method="btree"),),
    Kind.ROUTINES: (
        RoutineMeta("f", "FUNCTION", "a integer", definition="CREATE FUNCTION f(a integer)", comment="uno"),
        RoutineMeta("f", "FUNCTION", "a text", definition="CREATE FUNCTION f(a text)"),
        RoutineMeta("p", "PROCEDURE", definition=" CREATE PROCEDURE p() "),
        RoutineMeta("PKG", "PACKAGE"),
    ),
    Kind.ROUTINE_PARAMETERS: (
        RoutineParameterMeta(RoutineKey("f", "a text"), 1, "a", "IN", "text", "'z'"),
        RoutineParameterMeta(RoutineKey("f", "a integer"), 1, "a", "IN", "integer"),
    ),
}


def _rows() -> tuple[CatalogRows, list[frozenset[Kind]]]:
    loads: list[frozenset[Kind]] = []

    def load(kinds: frozenset[Kind]) -> SchemaSnapshot:
        loads.append(kinds)
        return SchemaSnapshot("postgresql", "s", {k: DATA.get(k, ()) for k in kinds})

    return CatalogRows(load), loads


def test_inventory_rows() -> None:
    rows, _ = _rows()
    assert rows.tables() == [("t", "tabla", "utf8mb4_bin"), ("u", "", "")]
    assert rows.views() == [("v", "vista"), ("w", "")]  # sin vistas materializadas
    assert rows.routines() == [
        ("f(a integer)", "FUNCTION", "uno"),
        ("f(a text)", "FUNCTION", ""),
        ("p", "PROCEDURE", ""),
    ]


def test_column_rows_and_each_kind_loaded_once() -> None:
    rows, loads = _rows()
    expected = [
        ("id", "integer", "NO", "", "IDENTITY (ALWAYS)", ""),
        ("code", "character varying(20)", "YES", "'x'", "", "c"),
        ("g", "integer", "YES", "", "CALCULADA: (id * 2)", ""),
    ]
    assert rows.columns("t") == expected
    assert rows.columns("T") == expected  # búsqueda sin distinguir mayúsculas
    assert rows.columns("t") == expected
    assert loads == [frozenset({Kind.COLUMNS})]


def test_constraint_and_index_rows() -> None:
    rows, _ = _rows()
    assert rows.primary_keys("t") == [("id",)]
    assert rows.primary_keys("u") == []
    assert rows.foreign_keys("u") == [
        ("fk", "a", "t", "x", "CASCADE", "NO ACTION"),
        ("fk", "b", "t", "y", "CASCADE", "NO ACTION"),
    ]
    assert rows.unique_constraints("t") == [("uk", "code"), ("uk", "g")]
    assert rows.indices("t") == [("ix", "code", "Sí", "btree"), ("ix", "lower(code)", "Sí", "btree")]


def test_view_and_routine_definitions_and_parameters() -> None:
    rows, _ = _rows()
    assert rows.view_ddl("v") == "CREATE VIEW v AS\nSELECT 1"
    assert rows.view_ddl("w") == "CREATE VIEW w AS SELECT 2"
    assert rows.view_ddl("missing") == ""
    assert rows.routine_ddl("p", "procedure") == "CREATE PROCEDURE p()"
    assert rows.routine_parameters("f(a text)", "FUNCTION") == [("IN", "a", "text", "'z'", 1)]
    assert rows.routine_parameters("f(a integer)", "FUNCTION") == [("IN", "a", "integer", "", 1)]
    assert rows.routine_parameters("nope", "FUNCTION") == []
