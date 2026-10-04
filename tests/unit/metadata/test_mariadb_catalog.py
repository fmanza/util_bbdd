"""``MariaDBCatalog`` / ``MySQLCatalog``: SQL por tipo de objeto, consultas ``extra`` y parseo (sin servidor)."""

from __future__ import annotations

import pytest

from util_bbdd.metadata._paramstyle import placeholders, to_driver
from util_bbdd.metadata.catalog_registry import get_catalog_dialect
from util_bbdd.metadata.contracts import CatalogDialect
from util_bbdd.metadata.mariadb.catalog import MariaDBCatalog, MySQLCatalog, build_create_routine
from util_bbdd.metadata.model import ALL_KINDS, Kind, RoutineKey, SchemaSnapshot

MARIA = MariaDBCatalog()
MY = MySQLCatalog()


def test_resolved_by_db_type_and_sqlalchemy_name() -> None:
    assert isinstance(MARIA, CatalogDialect) and isinstance(MY, CatalogDialect)
    assert type(get_catalog_dialect("mariadb")) is MariaDBCatalog
    assert type(get_catalog_dialect("mysql")) is MySQLCatalog


@pytest.mark.parametrize("dialect", [MARIA, MY], ids=["mariadb", "mysql"])
@pytest.mark.parametrize("kind", sorted(ALL_KINDS, key=lambda k: k.value))
def test_queries_bind_schema_and_never_join_information_schema_views(dialect: MariaDBCatalog, kind: Kind) -> None:
    query = dialect.query(kind, filtered=True)
    assert query is not None
    for sql in (query.sql, *query.extra):
        names = set(placeholders(sql))
        assert names <= {"schema", "tables"}
        assert " JOIN " not in sql.upper(), "H-16: nada de joins entre vistas de information_schema"
        sql_driver, _ = to_driver(sql, {"schema": "s", "tables": ["t"]}, "pyformat")  # pymysql
        assert "%%auto_increment%%" in sql_driver or "auto_increment" not in sql


def test_extra_queries_for_foreign_keys_and_routines() -> None:
    assert len(MARIA.query(Kind.FOREIGN_KEYS).extra) == 1  # type: ignore[union-attr]
    assert len(MARIA.query(Kind.ROUTINES).extra) == 1  # type: ignore[union-attr]
    assert MARIA.query(Kind.CHECKS).extra == ()  # type: ignore[union-attr]
    assert len(MY.query(Kind.CHECKS).extra) == 1  # type: ignore[union-attr]
    assert "EXPRESSION" in MY.query(Kind.INDEXES).sql and "EXPRESSION" not in MARIA.query(Kind.INDEXES).sql  # type: ignore[union-attr]


def test_parse_columns_defaults_identity_generated() -> None:
    rows = [
        ("t", "id", 1, "int(11)", "int", "NO", None, 10, 0, "NULL", "", None, "auto_increment", ""),
        ("t", "name", 2, "varchar(20)", "varchar", "YES", 20, None, None, "'x'", "nombre", "utf8mb4_bin", "", ""),
        ("t", "amount", 3, "decimal(12,2)", "decimal", "YES", None, 12, 2, None, "", None, "", ""),
        ("t", "total", 4, "int", "int", "YES", None, 10, 0, None, "", None, "VIRTUAL GENERATED", "`amount` * 2"),
    ]
    ident, name, amount, total = MARIA.parse(Kind.COLUMNS, rows, "s")
    assert (ident.identity, ident.default, ident.precision) == ("by default", None, None)
    assert (name.length, name.default, name.comment, name.collation) == (20, "'x'", "nombre", "utf8mb4_bin")
    assert (amount.precision, amount.scale) == (12, 2)
    assert (total.generated, total.default) == ("`amount` * 2", None)


def test_parse_foreign_keys_joins_rules_in_python() -> None:
    columns = [
        ("c", "fk", "a", "s", "p", "x", 1),
        ("c", "fk", "b", "s", "p", "y", 2),
        ("d", "fk2", "z", "s", "p", "x", 1),
    ]
    rules = [("c", "fk", "CASCADE", "RESTRICT")]
    fk, fk2 = MARIA.parse(Kind.FOREIGN_KEYS, [columns, rules], "s")
    assert (fk.columns, fk.ref_columns, fk.on_delete, fk.on_update) == (("a", "b"), ("x", "y"), "CASCADE", "RESTRICT")
    assert (fk2.on_delete, fk2.on_update) == ("NO ACTION", "NO ACTION")


def test_parse_indexes_uniques_and_primary() -> None:
    rows = [("t", "PRIMARY", 0, "BTREE", "id", None, 1), ("t", "ix_fn", 1, "BTREE", None, "lower(`name`)", 1)]
    pk, fn = MY.parse(Kind.INDEXES, rows, "s")
    assert (pk.primary, pk.unique) == (True, True)
    assert (fn.columns, fn.unique) == (("lower(`name`)",), False)
    assert MARIA.parse(Kind.UNIQUES, [("t", "uk", "a", 1), ("t", "uk", "b", 2)], "s")[0].columns == ("a", "b")


def test_mysql_checks_take_the_table_from_table_constraints() -> None:
    checks = [("ck_pos", "(`amount` > 0)"), ("ck_orphan", "(1)")]
    tables = [("t", "ck_pos")]
    (check,) = MY.parse(Kind.CHECKS, [checks, tables], "s")
    assert (check.table, check.name, check.expression) == ("t", "ck_pos", "(`amount` > 0)")
    assert MARIA.parse(Kind.CHECKS, [("t", "ck", "`a` > 0")], "s")[0].table == "t"


def test_parse_routines_rebuilds_create_with_parameters() -> None:
    routines = [
        ("f", "FUNCTION", "RETURN x + 1", "int", "suma", "YES", "NO SQL", "DEFINER"),
        ("p", "PROCEDURE", "BEGIN SELECT 1; END", "", "", "NO", "CONTAINS SQL", "INVOKER"),
        ("hidden", "PROCEDURE", None, "", "", "", "", ""),
    ]
    parameters = [("f", "FUNCTION", 1, "x", None, "int"), ("p", "PROCEDURE", 1, "y", "OUT", "varchar(10)")]
    f, p, hidden = MARIA.parse(Kind.ROUTINES, [routines, parameters], "s")
    assert f.definition == (
        "CREATE FUNCTION `f`(`x` int)\nRETURNS int\nCOMMENT 'suma'\nDETERMINISTIC\nNO SQL\nSQL SECURITY DEFINER\n"
        "RETURN x + 1"
    )
    assert (f.return_type, f.comment) == ("int", "suma")
    assert p.definition is not None and p.definition.startswith("CREATE PROCEDURE `p`(OUT `y` varchar(10))")
    assert (p.return_type, hidden.definition) == (None, None)


def test_parse_routine_parameters() -> None:
    (param,) = MARIA.parse(Kind.ROUTINE_PARAMETERS, [("p", "PROCEDURE", 1, "y", "INOUT", "int")], "s")
    assert (param.routine, param.mode, param.data_type) == (RoutineKey("p", routine_type="PROCEDURE"), "INOUT", "int")


def test_homonymous_function_and_procedure_keep_their_own_parameters() -> None:
    """MySQL/MariaDB admiten una FUNCTION y una PROCEDURE con el mismo nombre: sus parámetros no se mezclan."""
    routines = [
        ("x", "FUNCTION", "RETURN a", "int", "", "YES", "NO SQL", "DEFINER"),
        ("x", "PROCEDURE", "BEGIN END", "", "", "NO", "CONTAINS SQL", "DEFINER"),
    ]
    parameters = [("x", "FUNCTION", 1, "a", None, "int"), ("x", "PROCEDURE", 1, "b", "OUT", "date")]
    snapshot = SchemaSnapshot(
        "mariadb",
        "s",
        {
            Kind.ROUTINES: MARIA.parse(Kind.ROUTINES, [routines, parameters], "s"),
            Kind.ROUTINE_PARAMETERS: MARIA.parse(Kind.ROUTINE_PARAMETERS, parameters, "s"),
        },
    )
    function, procedure = snapshot.routines()
    assert [p.name for p in snapshot.routine_parameters(function.key)] == ["a"]
    assert [p.name for p in snapshot.routine_parameters(procedure.key)] == ["b"]
    # Sin tipo en la clave (lo que piden otros motores) valen los dos
    assert [p.name for p in snapshot.routine_parameters(RoutineKey("x"))] == ["a", "b"]


def test_build_create_routine_escapes_comment_and_identifiers() -> None:
    sql = build_create_routine("we`ird", "PROCEDURE", [], "BEGIN END", comment="it's \\ ok")
    assert sql.splitlines()[0] == "CREATE PROCEDURE `we``ird`()"
    assert "COMMENT 'it''s \\\\ ok'" in sql


def test_system_versioned_tables_are_tables() -> None:
    """E1: en MariaDB las tablas con SYSTEM VERSIONING tienen TABLE_TYPE = 'SYSTEM VERSIONED' (antes no salían)."""
    from util_bbdd.metadata.mariadb._show_create import TABLES_SQL
    from util_bbdd.metadata.mariadb.catalog import MariaDBCatalog

    assert "'SYSTEM VERSIONED'" in MariaDBCatalog().query(Kind.TABLES).sql  # type: ignore[union-attr]
    assert "'SYSTEM VERSIONED'" in TABLES_SQL
