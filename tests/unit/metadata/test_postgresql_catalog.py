"""``PostgreSQLCatalog``: SQL por tipo de objeto y parseo de filas (sin servidor)."""

from __future__ import annotations

import pytest

from util_bbdd.metadata._paramstyle import placeholders, to_driver
from util_bbdd.metadata.catalog_registry import (
    CatalogDialectNotFoundError,
    get_catalog_dialect,
    register_catalog_dialect,
    supported_catalog_engines,
)
from util_bbdd.metadata.contracts import CatalogDialect
from util_bbdd.metadata.model import ALL_KINDS, Kind, RoutineKey
from util_bbdd.metadata.postgresql.catalog import PostgreSQLCatalog

PG = PostgreSQLCatalog()


def test_is_a_catalog_dialect_resolved_by_both_names() -> None:
    assert isinstance(PG, CatalogDialect)
    assert type(get_catalog_dialect("postgresql")) is PostgreSQLCatalog
    assert get_catalog_dialect("PostgreSQL") is get_catalog_dialect("postgresql")
    assert "postgresql" in supported_catalog_engines()


def test_unknown_engine_raises() -> None:
    with pytest.raises(CatalogDialectNotFoundError):
        get_catalog_dialect("db2")


def test_registered_dialect_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    from util_bbdd.metadata import catalog_registry

    monkeypatch.setattr(catalog_registry, "_extra", {})  # no deja el registro global modificado

    class Custom(PostgreSQLCatalog):
        name = "custompg"
        sqlalchemy_names = frozenset({"custom+pg"})

    register_catalog_dialect(Custom())
    assert type(get_catalog_dialect("custom+pg")) is Custom


@pytest.mark.parametrize("kind", sorted(ALL_KINDS, key=lambda k: k.value))
def test_every_kind_has_bound_sql_with_only_schema_and_tables(kind: Kind) -> None:
    query = PG.query(kind, filtered=True)
    assert query is not None
    names = set(placeholders(query.sql))
    assert names <= {"schema", "tables"}
    assert ("tables" in names) == query.filterable
    assert "{" not in query.sql and "information_schema" not in query.sql.lower()
    # traducible al estilo de psycopg sin romper los casts ::regclass
    sql, _ = to_driver(query.sql, {"schema": "s", "tables": ["a"]}, "pyformat")
    assert "%(schema)s" in sql or kind == Kind.DATABASE
    assert ":regclass" not in sql.replace("::regclass", "")


def test_unfiltered_sql_has_no_tables_parameter() -> None:
    assert "tables" not in placeholders(PG.query(Kind.COLUMNS).sql)  # type: ignore[union-attr]


def test_parse_columns_with_modifiers_identity_and_generated() -> None:
    rows = [
        ("t", "id", 1, "integer", "int4", True, 23, -1, None, None, None, "d", ""),
        ("t", "code", 2, "character varying(20)", "varchar", True, 1043, 24, None, "código", "C", "", ""),
        ("t", "amount", 3, "numeric(12,2)", "numeric", False, 1700, (12 << 16 | 2) + 4, "0", None, None, "", ""),
        ("t", "total", 4, "numeric", "numeric", False, 1700, -1, "(amount * 2)", None, None, "", "s"),
    ]
    cols = PG.parse(Kind.COLUMNS, rows, "s")
    assert (cols[0].identity, cols[0].nullable) == ("by default", False)
    assert (cols[1].length, cols[1].comment, cols[1].collation) == (20, "código", "C")
    assert (cols[2].precision, cols[2].scale, cols[2].default) == (12, 2, "0")
    assert (cols[3].generated, cols[3].default) == ("(amount * 2)", None)


def test_parse_constraints_accept_lists_and_array_literals() -> None:
    pk = PG.parse(Kind.PRIMARY_KEYS, [("t", "pk_t", ["a", "b"])], "s")[0]
    uk = PG.parse(Kind.UNIQUES, [("t", "uk_t", '{code,"Mixed Case"}')], "s")[0]
    assert pk.columns == ("a", "b")
    assert uk.columns == ("code", "Mixed Case")


def test_parse_foreign_keys_rules() -> None:
    fk = PG.parse(Kind.FOREIGN_KEYS, [("c", "fk", ["p_id"], "s", "p", ["id"], "c", "n")], "s")[0]
    assert (fk.on_delete, fk.on_update, fk.ref_table, fk.columns) == ("CASCADE", "SET NULL", "p", ("p_id",))


def test_parse_indexes_identity_routines_and_parameters() -> None:
    ix = PG.parse(Kind.INDEXES, [("t", "ix", False, False, "btree", "(x > 0)", ["lower(name)"])], "s")[0]
    assert (ix.columns, ix.predicate, ix.unique) == (("lower(name)",), "(x > 0)", False)
    ident = PG.parse(Kind.IDENTITY, [("t", "id", "", "s", "t_id_seq"), ("u", "id", "a", "s", "u_id_seq")], "s")
    assert [i.kind for i in ident] == ["sequence", "identity"]
    routine = PG.parse(Kind.ROUTINES, [("f", "f", "x integer", "integer", "CREATE …", None, "sql")], "s")[0]
    assert routine.key == RoutineKey("f", "x integer", "FUNCTION")
    assert routine.key.matches(RoutineKey("f", "x integer"))  # los parámetros de PostgreSQL no llevan tipo
    params = PG.parse(Kind.ROUTINE_PARAMETERS, [("f", "x integer", 1, "x", None, "integer", "1")], "s")
    assert (params[0].mode, params[0].default) == ("IN", "1")


def test_char_columns_as_bytes_like_asyncpg() -> None:
    """asyncpg devuelve el tipo ``"char"`` de pg_catalog como bytes: identidad, reglas de FK y prokind deben leerse igual."""
    cols = PG.parse(Kind.COLUMNS, [("t", "id", 1, "integer", "int4", True, 23, -1, None, None, None, b"d", b"")], "s")
    assert cols[0].identity == "by default"
    fk = PG.parse(Kind.FOREIGN_KEYS, [("c", "fk", ["p_id"], "s", "p", ["id"], b"c", b"a")], "s")[0]
    assert (fk.on_delete, fk.on_update) == ("CASCADE", "NO ACTION")
    routine = PG.parse(Kind.ROUTINES, [("p", b"p", "", None, "CREATE …", None, "plpgsql")], "s")[0]
    assert routine.routine_type == "PROCEDURE"
    param = PG.parse(Kind.ROUTINE_PARAMETERS, [("p", "", 1, "x", b"o", "integer", None)], "s")[0]
    assert param.mode == "OUT"


def test_bit_length_and_standard_base_type() -> None:
    """C3: ``bit(n)`` lleva su longitud en bits y ``base_type`` es el de ``information_schema`` (lo da el SQL)."""
    rows = [("t", "b", 1, "bit(3)", "bit", False, 1560, 3, None, None, None, "", "")]
    col = PG.parse(Kind.COLUMNS, rows, "s")[0]
    assert (col.data_type, col.base_type, col.length) == ("bit(3)", "bit", 3)
    sql = PG.query(Kind.COLUMNS).sql  # type: ignore[union-attr]
    assert "'USER-DEFINED'" in sql and "'ARRAY'" in sql and "typtypmod" in sql
