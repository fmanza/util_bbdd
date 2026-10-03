"""``SQLServerCatalog``: SQL por tipo de objeto y parseo de filas (sin servidor)."""

from __future__ import annotations

import pytest

from util_bbdd.metadata._paramstyle import placeholders, to_driver
from util_bbdd.metadata.catalog_registry import get_catalog_dialect
from util_bbdd.metadata.contracts import CatalogDialect
from util_bbdd.metadata.model import ALL_KINDS, Kind, RoutineKey
from util_bbdd.metadata.sqlserver.catalog import SQLServerCatalog

SS = SQLServerCatalog()


def test_resolved_by_db_type_and_sqlalchemy_name() -> None:
    assert isinstance(SS, CatalogDialect)
    assert type(get_catalog_dialect("sqlserver")) is SQLServerCatalog
    assert get_catalog_dialect("mssql") is get_catalog_dialect("sqlserver")


def test_normalize_name_strips_brackets_only() -> None:
    assert SS.normalize_name("[dbo]") == "dbo"
    assert SS.normalize_name("Ventas") == "Ventas"


@pytest.mark.parametrize("kind", sorted(ALL_KINDS, key=lambda k: k.value))
def test_every_kind_uses_sys_catalog_with_binds(kind: Kind) -> None:
    query = SS.query(kind, filtered=True)
    assert query is not None
    names = set(placeholders(query.sql))
    assert names <= {"schema", "tables"}
    assert ("tables" in names) == query.filterable
    assert "information_schema" not in query.sql.lower()
    sql, _ = to_driver(query.sql, {"schema": "dbo", "tables": ["t"]}, "pyformat")  # pymssql
    assert "{" not in sql


@pytest.mark.parametrize(
    ("type_name", "max_length", "precision", "scale", "expected"),
    [
        ("varchar", 30, 0, 0, ("varchar(30)", 30, None, None)),
        ("nvarchar", 60, 0, 0, ("nvarchar(30)", 30, None, None)),
        ("nvarchar", -1, 0, 0, ("nvarchar(max)", None, None, None)),
        ("decimal", 9, 12, 2, ("decimal(12,2)", None, 12, 2)),
        ("datetime2", 8, 27, 7, ("datetime2(7)", None, None, None)),
        ("int", 4, 10, 0, ("int", None, None, None)),
    ],
)
def test_parse_column_types(type_name: str, max_length: int, precision: int, scale: int, expected: tuple) -> None:
    row = ("t", "c", 1, type_name, type_name, max_length, precision, scale, True, None, None, None, False, None)
    col = SS.parse(Kind.COLUMNS, [row], "dbo")[0]
    assert (col.data_type, col.length, col.precision, col.scale) == expected


def test_parse_identity_default_computed_and_comment() -> None:
    rows = [
        ("t", "id", 1, "int", "int", 4, 10, 0, False, None, "clave", None, True, None),
        ("t", "total", 2, "int", "int", 4, 10, 0, True, "((0))", None, "Latin1_General_BIN", False, "([a]*(2))"),
    ]
    ident, computed = SS.parse(Kind.COLUMNS, rows, "dbo")
    assert (ident.identity, ident.comment, ident.nullable) == ("by default", "clave", False)
    assert (computed.generated, computed.default, computed.collation) == ("([a]*(2))", "((0))", "Latin1_General_BIN")


def test_parse_foreign_keys_rules_and_column_order() -> None:
    rows = [
        ("c", "fk", "a", "dbo", "p", "x", "CASCADE", "SET_NULL", 1),
        ("c", "fk", "b", "dbo", "p", "y", "CASCADE", "SET_NULL", 2),
    ]
    fk = SS.parse(Kind.FOREIGN_KEYS, rows, "dbo")[0]
    assert (fk.columns, fk.ref_columns, fk.on_delete, fk.on_update) == (("a", "b"), ("x", "y"), "CASCADE", "SET NULL")


def test_parse_indexes_and_key_constraints() -> None:
    ix = SS.parse(Kind.INDEXES, [("t", "ix", False, False, "NONCLUSTERED", "([a]>(0))", "a", 1)], "dbo")[0]
    assert (ix.unique, ix.method, ix.predicate) == (False, "NONCLUSTERED", "([a]>(0))")
    pk = SS.parse(Kind.PRIMARY_KEYS, [("t", "pk", "a", 1), ("t", "pk", "b", 2)], "dbo")[0]
    assert pk.columns == ("a", "b")


def test_parse_routines_and_parameters() -> None:
    rows = [
        ("f", "FN ", "CREATE FUNCTION f…", "decimal", 9, 12, 2, None),
        ("tvf", "IF", "CREATE FUNCTION tvf…", None, None, None, None, "tabla"),
        ("p", "P ", "CREATE PROCEDURE p…", None, None, None, None, None),
        ("clr", "PC", None, None, None, None, None, None),
    ]
    f, tvf, p, clr = SS.parse(Kind.ROUTINES, rows, "dbo")
    assert (f.routine_type, f.return_type, f.language) == ("FUNCTION", "decimal(12,2)", "TSQL")
    assert (tvf.return_type, tvf.comment) == ("TABLE", "tabla")
    assert (p.routine_type, p.return_type) == ("PROCEDURE", None)
    assert (clr.language, clr.definition) == ("CLR", None)
    params = SS.parse(Kind.ROUTINE_PARAMETERS, [("p", 1, "@x", True, "varchar", 10, 0, 0)], "dbo")
    assert (params[0].routine, params[0].mode, params[0].data_type) == (RoutineKey("p"), "INOUT", "varchar(10)")


def test_alias_type_is_sized_by_its_system_type() -> None:
    """C3: ``CREATE TYPE code FROM varchar(10)`` → ``data_type`` = ``code``, longitud 10 (antes sin longitud)."""
    row = ("t", "c", 1, "code", "varchar", 10, 0, 0, False, None, None, None, False, None)
    col = SS.parse(Kind.COLUMNS, [row], "dbo")[0]
    assert (col.data_type, col.base_type, col.length) == ("code", "varchar", 10)
