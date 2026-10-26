"""U-M2 (G28 de util_bbdd_web): la columna FK recibe el tipo destino de la columna que referencia."""

from __future__ import annotations

import pytest

from util_bbdd.migrate import CanonicalColumn, CanonicalFK, CanonicalTable, MigrationPlanner, MigrationWarning
from util_bbdd.migrate.transformers._fk_types import align_fk_types

from ._snapshot_source import col, fake_manager, fk, pk, table


def _oracle_int_pk_and_fk() -> object:
    """Oracle ``INT`` (``NUMBER`` sin precisión) en la PK de PADRE y en la FK de HIJO."""
    return fake_manager(
        "oracle",
        table("PADRE"),
        col("PADRE", "ID", 1, "NUMBER", "NUMBER", scale=0, nullable=False),
        pk("PADRE", "ID"),
        table("HIJO"),
        col("HIJO", "ID", 1, "NUMBER(10)", "NUMBER", precision=10, scale=0, nullable=False),
        col("HIJO", "PADRE_ID", 2, "NUMBER", "NUMBER", scale=0),
        pk("HIJO", "ID"),
        fk("HIJO", "FK_HIJO_PADRE", ("PADRE_ID",), "PADRE", ("ID",), ref_schema="S"),
    )


def _column(plan_tables: list[CanonicalTable], table_name: str, column_name: str) -> CanonicalColumn:
    table_ = next(t for t in plan_tables if t.name.lower() == table_name.lower())
    return next(c for c in table_.columns if c.name.lower() == column_name.lower())


@pytest.mark.parametrize("target", ["mariadb", "mysql", "sqlserver", "postgresql"])
def test_oracle_int_fk_takes_the_pk_type(target: str) -> None:
    plan = MigrationPlanner(source_engine="oracle", target_engine=target).plan(_oracle_int_pk_and_fk(), "S")

    parent = _column(plan.tables, "PADRE", "ID")
    child = _column(plan.tables, "HIJO", "PADRE_ID")
    assert child.target_type == parent.target_type
    assert child.ddl_comment is None
    assert plan.error_count == 0
    aligned = [w for w in plan.warnings if w.code == "FK_TYPE_ALIGNED"]
    assert [(w.table.upper(), (w.column or "").upper(), w.severity) for w in aligned] == [("HIJO", "PADRE_ID", "INFO")]
    # El aviso del tipo descartado (NUMBER sin precisión → DOUBLE/FLOAT) ya no describe la columna.
    assert not [w for w in plan.warnings if w.category == "TYPE" and (w.column or "").upper() == "PADRE_ID"]
    ddl_line = next(
        line for line in plan.emit_ddl().splitlines() if "PADRE_ID" in line.upper() and "FOREIGN" not in line
    )
    assert "DOUBLE" not in ddl_line.upper() and "FLOAT" not in ddl_line.upper()


def _col(name: str, target_type: str, *, omit: bool = False) -> CanonicalColumn:
    return CanonicalColumn(name, name, target_type, target_type, True, None, "", 1, omit=omit)


def _table(name: str, columns: list[CanonicalColumn], fks: list[CanonicalFK] | None = None) -> CanonicalTable:
    return CanonicalTable(name, name, "s", columns, [columns[0].name], [], fks or [], "", [])


def _fk(columns: list[str], ref_table: str, ref_columns: list[str], *, external: bool = False) -> CanonicalFK:
    return CanonicalFK(f"fk_{ref_table}", f"fk_{ref_table}", columns, ref_table, ref_columns, "", "", external)


def _codes(tables: list[CanonicalTable]) -> list[tuple[str, str | None, str | None, str]]:
    return [(w.table, w.column, w.code, w.severity) for t in tables for w in t.warnings]


def test_same_type_up_to_int_display_width_is_left_alone() -> None:
    tables = [
        _table("a", [_col("id", "INT(11)")]),
        _table("b", [_col("id", "INT"), _col("a_id", "int")], [_fk(["a_id"], "a", ["id"])]),
    ]
    align_fk_types(tables)
    assert tables[1].columns[1].target_type == "int"
    assert _codes(tables) == []


def test_chain_takes_the_type_at_the_end() -> None:
    # c.b_id → b.a_id → a.id: las dos FK acaban en BIGINT, aunque b se procese antes que a.
    tables = [
        _table("c", [_col("id", "INT"), _col("b_id", "DOUBLE")], [_fk(["b_id"], "b", ["a_id"])]),
        _table("b", [_col("a_id", "DECIMAL(38,10)")], [_fk(["a_id"], "a", ["id"])]),
        _table("a", [_col("id", "BIGINT")]),
    ]
    align_fk_types(tables)
    assert tables[0].columns[1].target_type == "BIGINT"
    assert tables[1].columns[0].target_type == "BIGINT"
    assert [code for *_, code, _ in _codes(tables)] == ["FK_TYPE_ALIGNED", "FK_TYPE_ALIGNED"]


def test_self_reference_and_type_warning_removed() -> None:
    parent = _col("parent_id", "DOUBLE")
    parent.ddl_comment = "-- AVISO: NUMBER sin precisión → DOUBLE"
    parent.warnings.append(MigrationWarning("t", "parent_id", "TYPE", "DOUBLE", "NUMBER sin precisión → DOUBLE"))
    parent.warnings.append(MigrationWarning("t", "parent_id", "IDENTIFIER", "parent_id", "nombre", "WARNING"))
    tables = [_table("t", [_col("id", "INT(11)"), parent], [_fk(["parent_id"], "t", ["id"])])]
    align_fk_types(tables)
    assert parent.target_type == "INT(11)"
    assert parent.ddl_comment is None
    assert [w.category for w in parent.warnings] == ["IDENTIFIER"]


def test_cycle_does_not_recurse_forever() -> None:
    tables = [
        _table("a", [_col("id", "INT"), _col("b_id", "INT")], [_fk(["b_id"], "b", ["a_id"])]),
        _table("b", [_col("id", "INT"), _col("a_id", "INT")], [_fk(["a_id"], "a", ["b_id"])]),
    ]
    align_fk_types(tables)
    assert _codes(tables) == []


def test_external_and_unknown_tables_are_skipped() -> None:
    tables = [
        _table(
            "b",
            [_col("id", "INT"), _col("x_id", "DOUBLE"), _col("y_id", "DOUBLE")],
            [_fk(["x_id"], "x", ["id"], external=True), _fk(["y_id"], "fuera_del_plan", ["id"])],
        ),
    ]
    align_fk_types(tables)
    assert [c.target_type for c in tables[0].columns] == ["INT", "DOUBLE", "DOUBLE"]
    assert _codes(tables) == []


@pytest.mark.parametrize(
    ("ref_columns", "detail"),
    [(["no_existe"], "no existe en el plan"), (["rowid_col"], "se omite en el destino")],
)
def test_missing_or_omitted_referenced_column_is_an_error(ref_columns: list[str], detail: str) -> None:
    tables = [
        _table("a", [_col("id", "INT"), _col("rowid_col", "", omit=True)]),
        _table("b", [_col("id", "INT"), _col("a_ref", "DOUBLE")], [_fk(["a_ref"], "a", ref_columns)]),
    ]
    align_fk_types(tables)
    assert tables[1].columns[1].target_type == "DOUBLE"
    (warning,) = tables[1].warnings
    assert (warning.code, warning.severity, warning.column) == ("FK_TYPE_UNRESOLVED", "ERROR", "a_ref")
    assert detail in warning.message


def test_two_references_of_different_types_are_an_error() -> None:
    tables = [
        _table("a", [_col("id", "INT")]),
        _table("b", [_col("id", "BIGINT")]),
        _table("c", [_col("id", "INT"), _col("x", "DOUBLE")], [_fk(["x"], "a", ["id"]), _fk(["x"], "b", ["id"])]),
    ]
    align_fk_types(tables)
    assert tables[2].columns[1].target_type == "DOUBLE"
    (warning,) = tables[2].warnings
    assert warning.code == "FK_TYPE_UNRESOLVED"
    assert "a.id: INT" in warning.message and "b.id: BIGINT" in warning.message


def test_unresolved_blocks_execute() -> None:
    manager = fake_manager(
        "oracle",
        table("PADRE"),
        col("PADRE", "ID", 1, "NUMBER(10)", "NUMBER", precision=10, scale=0, nullable=False),
        col("PADRE", "RID", 2, "ROWID", "ROWID"),
        pk("PADRE", "ID"),
        table("HIJO"),
        col("HIJO", "ID", 1, "NUMBER(10)", "NUMBER", precision=10, scale=0, nullable=False),
        col("HIJO", "PADRE_RID", 2, "VARCHAR2(18)", "VARCHAR2", length=18),
        pk("HIJO", "ID"),
        fk("HIJO", "FK_HIJO_PADRE", ("PADRE_RID",), "PADRE", ("RID",), ref_schema="S"),
    )
    plan = MigrationPlanner(source_engine="oracle", target_engine="mariadb").plan(manager, "S")
    # ROWID ya es ERROR por sí mismo (COLUMN_OMITTED); la FK que lo referencia añade el suyo.
    assert [w.code for w in plan.warnings if w.severity == "ERROR"] == ["COLUMN_OMITTED", "FK_TYPE_UNRESOLVED"]
    with pytest.raises(ValueError, match="ERROR"):
        plan.execute(object())
