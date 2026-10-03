"""``OracleCatalog``: SQL por tipo de objeto y parseo de filas (sin servidor)."""

from __future__ import annotations

import pytest

from util_bbdd.metadata._paramstyle import placeholders, to_driver
from util_bbdd.metadata.catalog_registry import get_catalog_dialect
from util_bbdd.metadata.contracts import CatalogDialect
from util_bbdd.metadata.model import ALL_KINDS, Kind, RoutineKey
from util_bbdd.metadata.oracle.catalog import OracleCatalog

ORA = OracleCatalog()


def test_is_a_catalog_dialect_resolved_by_name() -> None:
    assert isinstance(ORA, CatalogDialect)
    assert type(get_catalog_dialect("oracle")) is OracleCatalog


@pytest.mark.parametrize(
    ("name", "expected"), [("scott", "SCOTT"), ("SCOTT", "SCOTT"), ("Mixed", "Mixed"), ('"lower"', "lower")]
)
def test_normalize_name(name: str, expected: str) -> None:
    assert ORA.normalize_name(name) == expected


@pytest.mark.parametrize("kind", sorted(ALL_KINDS, key=lambda k: k.value))
def test_every_kind_uses_owner_bind_and_optional_table_filter(kind: Kind) -> None:
    query = ORA.query(kind, filtered=True)
    assert query is not None
    names = set(placeholders(query.sql))
    assert names <= {"schema", "tables"}
    assert ("tables" in names) == query.filterable
    assert "{" not in query.sql
    if kind != Kind.DATABASE:
        assert "schema" in names
    sql, args = to_driver(query.sql, {"schema": "S", "tables": ["T"]}, "named")  # oracledb: paramstyle named
    assert args is None or set(args) <= {"schema", "tables_0"}
    assert "'BIN$%'" in sql or "BIN$" not in query.sql


@pytest.mark.parametrize(
    ("row", "data_type", "length", "precision", "scale"),
    [
        (("VARCHAR2", 120, 30, "C", None, None), "VARCHAR2(30 CHAR)", 30, None, None),
        (("VARCHAR2", 30, 30, "B", None, None), "VARCHAR2(30)", 30, None, None),
        (("NUMBER", 22, None, None, 12, 2), "NUMBER(12,2)", None, 12, 2),
        (("NUMBER", 22, None, None, 10, 0), "NUMBER(10)", None, 10, 0),
        (("NUMBER", 22, None, None, None, None), "NUMBER", None, None, None),
        (("NUMBER", 22, None, None, None, 0), "NUMBER(*,0)", None, None, 0),
        (("RAW", 16, None, None, None, None), "RAW(16)", None, None, None),
        (("TIMESTAMP(6)", 11, None, None, None, 6), "TIMESTAMP(6)", None, None, None),
    ],
)
def test_parse_column_types(
    row: tuple, data_type: str, length: int | None, precision: int | None, scale: int | None
) -> None:
    dt, data_length, char_length, char_used, prec, sc = row
    rows = [("T", "C", 1, dt, data_length, char_length, char_used, prec, sc, "Y", None, None, "NO", None)]
    col = ORA.parse(Kind.COLUMNS, rows, "S")[0]
    assert (col.data_type, col.length, col.precision, col.scale) == (data_type, length, precision, scale)


def test_parse_identity_and_virtual_columns() -> None:
    rows = [
        (
            "T",
            "ID",
            1,
            "NUMBER",
            22,
            0,
            None,
            10,
            0,
            "N",
            '"S"."ISEQ$$_1".nextval ',
            "clave",
            "NO",
            "BY DEFAULT ON NULL",
        ),
        ("T", "TOTAL", 2, "NUMBER", 22, 0, None, None, None, "Y", '"A"*2', None, "YES", None),
    ]
    ident, virtual = ORA.parse(Kind.COLUMNS, rows, "S")
    assert (ident.identity, ident.default, ident.comment, ident.nullable) == (
        "by default",
        '"S"."ISEQ$$_1".nextval',
        "clave",
        False,
    )
    assert (virtual.generated, virtual.default) == ('"A"*2', None)


def test_constraints_are_grouped_by_name_in_column_order() -> None:
    pk = ORA.parse(Kind.PRIMARY_KEYS, [("T", "PK_T", "A", 1), ("T", "PK_T", "B", 2)], "S")
    assert [(p.name, p.columns) for p in pk] == [("PK_T", ("A", "B"))]
    fk = ORA.parse(
        Kind.FOREIGN_KEYS,
        [("C", "FK", "A", "S", "P", "X", "CASCADE", 1), ("C", "FK", "B", "S", "P", "Y", "CASCADE", 2)],
        "S",
    )[0]
    assert (fk.columns, fk.ref_columns, fk.on_delete, fk.on_update) == (("A", "B"), ("X", "Y"), "CASCADE", "NO ACTION")


def test_generated_not_null_checks_are_skipped() -> None:
    rows = [
        ("T", "SYS_C001", '"ID" IS NOT NULL', "GENERATED NAME"),
        ("T", "CK_POS", "amount > 0", "USER NAME"),
        ("T", "SYS_C002", "amount < 100", "GENERATED NAME"),
    ]
    assert [c.name for c in ORA.parse(Kind.CHECKS, rows, "S")] == ["CK_POS", "SYS_C002"]


def test_function_based_index_uses_the_expression() -> None:
    rows = [("T", "IX", "NONUNIQUE", "FUNCTION-BASED NORMAL", "SYS_NC00005$", 'UPPER("NAME")', 1, 0)]
    ix = ORA.parse(Kind.INDEXES, rows, "S")[0]
    assert (ix.columns, ix.unique, ix.method) == (('UPPER("NAME")',), False, "FUNCTION-BASED NORMAL")


def test_routines_join_source_lines_and_list_package_members() -> None:
    rows = [
        ("F", "FUNCTION", 1, "FUNCTION f(x NUMBER) RETURN NUMBER IS\n", "NUMBER", None),
        ("F", "FUNCTION", 2, "BEGIN RETURN x; END;\n", "NUMBER", None),
        ("PKG.P", "PROCEDURE", None, None, None, "1"),
        ("PKG.P", "FUNCTION", None, None, "VARCHAR2", "2"),
    ]
    f, p1, p2 = ORA.parse(Kind.ROUTINES, rows, "S")
    assert f.definition == "CREATE OR REPLACE FUNCTION f(x NUMBER) RETURN NUMBER IS\nBEGIN RETURN x; END;"
    assert (f.return_type, f.signature) == ("NUMBER", "")
    assert (p1.key, p1.definition) == (RoutineKey("PKG.P", "1"), None)
    assert (p2.routine_type, p2.key) == ("FUNCTION", RoutineKey("PKG.P", "2"))


def test_routine_parameters_keyed_by_package_and_overload() -> None:
    rows = [("P", "PKG", "2", 1, "X", "IN/OUT", "NUMBER"), ("F", None, None, 1, "Y", "IN", "VARCHAR2")]
    a, b = ORA.parse(Kind.ROUTINE_PARAMETERS, rows, "S")
    assert (a.routine, a.mode) == (RoutineKey("PKG.P", "2"), "INOUT")
    assert (b.routine, b.mode) == (RoutineKey("F", ""), "IN")


@pytest.mark.parametrize(
    ("data_type", "base_type"),
    [
        ("TIMESTAMP(6) WITH TIME ZONE", "TIMESTAMP WITH TIME ZONE"),
        ("TIMESTAMP(3)", "TIMESTAMP"),
        ("INTERVAL DAY(2) TO SECOND(6)", "INTERVAL DAY TO SECOND"),
        ("VARCHAR2", "VARCHAR2"),
    ],
)
def test_base_type_drops_modifiers_but_keeps_the_type(data_type: str, base_type: str) -> None:
    """C3: ``TIMESTAMP(6) WITH TIME ZONE`` → ``TIMESTAMP WITH TIME ZONE`` (antes ``TIMESTAMP``, sin la zona)."""
    rows = [("T", "C", 1, data_type, 13, None, None, None, None, "Y", None, None, "NO", None)]
    assert ORA.parse(Kind.COLUMNS, rows, "S")[0].base_type == base_type


def test_packages_are_listed_without_definition() -> None:
    """C3: los packages entran en ROUTINES (tipo ``PACKAGE``) como inventario para ``migrate``."""
    rows = [("PKG", "PACKAGE", None, None, None, None), ("PKG.F", "FUNCTION", None, None, "NUMBER", "1")]
    package, member = ORA.parse(Kind.ROUTINES, rows, "S")
    assert (package.name, package.routine_type, package.definition) == ("PKG", "PACKAGE", None)
    assert (member.name, member.routine_type) == ("PKG.F", "FUNCTION")
    assert "'PACKAGE'" in ORA.query(Kind.ROUTINES).sql  # type: ignore[union-attr]
