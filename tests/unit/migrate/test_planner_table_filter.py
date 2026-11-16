"""5.9.0 (G56 de util_bbdd_web): ``MigrationPlanner.plan(table_filter=...)``, como el filtro de la documentación."""

from __future__ import annotations

import json

from typing import Any

import pytest

from util_bbdd.exceptions import MigrationPlanValidationError
from util_bbdd.metadata import TableFilter
from util_bbdd.migrate import MigrationPlan, MigrationPlanner

from ._snapshot_source import col, fake_manager, fk, pk, routine, table, view


def _source() -> Any:
    """MVG_PEDIDO → MVG_CLIENTE (dentro) y → COB_MONEDA (fuera); AUX_LOG → MVG_PEDIDO (fuera, hija); MVG_PEDIDO_BAK."""
    objects: list[Any] = []
    for name in ("MVG_CLIENTE", "MVG_PEDIDO", "MVG_PEDIDO_BAK", "COB_MONEDA", "AUX_LOG"):
        objects += [table(name), col(name, "ID", 1, "int(11)", "int", nullable=False), pk(name, "ID")]
    objects += [
        col("MVG_PEDIDO", "CLIENTE_ID", 2, "int(11)", "int"),
        col("MVG_PEDIDO", "MONEDA_ID", 3, "int(11)", "int"),
        fk("MVG_PEDIDO", "FK_PED_CLI", ("CLIENTE_ID",), "MVG_CLIENTE", ("ID",), ref_schema="S"),
        fk("MVG_PEDIDO", "FK_PED_MON", ("MONEDA_ID",), "COB_MONEDA", ("ID",), ref_schema="S"),
        col("AUX_LOG", "PEDIDO_ID", 2, "int(11)", "int"),
        fk("AUX_LOG", "FK_LOG_PED", ("PEDIDO_ID",), "MVG_PEDIDO", ("ID",), ref_schema="S"),
        col("MVG_PEDIDO_BAK", "MONEDA_ID", 2, "int(11)", "int"),
        fk("MVG_PEDIDO_BAK", "FK_BAK_MON", ("MONEDA_ID",), "COB_MONEDA", ("ID",), ref_schema="S"),
        view("MVG_V_PEDIDOS", "SELECT p.ID, m.ID AS MONEDA FROM MVG_PEDIDO p JOIN COB_MONEDA m ON m.ID = p.MONEDA_ID"),
        view("COB_V_MONEDAS", "SELECT ID FROM COB_MONEDA"),
        routine("P_NADA", "PROCEDURE", "BEGIN END"),
    ]
    return fake_manager("mariadb", *objects)


def _plan(table_filter: TableFilter | None = None, **planner: Any) -> MigrationPlan:
    return MigrationPlanner(source_engine="mariadb", target_engine="postgresql", **planner).plan(
        _source(), "S", table_filter=table_filter
    )


MVG = TableFilter.from_patterns(include="mvg_*", exclude="*_BAK")


def _names(objects: list[Any]) -> list[str]:
    return sorted(obj.name.upper() for obj in objects)


@pytest.mark.parametrize("view_strategy", ["auto", "passthrough"])
def test_only_matching_tables_and_views_routines_untouched(view_strategy: str) -> None:
    plan = _plan(MVG, view_strategy=view_strategy)

    assert _names(plan.tables) == ["MVG_CLIENTE", "MVG_PEDIDO"]
    assert _names(plan.views) == ["MVG_V_PEDIDOS"]
    assert _names(plan.routines) == _names(_plan(view_strategy=view_strategy).routines)  # como la documentación
    assert plan.table_filter is MVG
    # Los avisos son solo de lo que queda en el plan
    assert {(w.table or "").upper() for w in plan.warnings} <= {"MVG_CLIENTE", "MVG_PEDIDO", "MVG_V_PEDIDOS", "P_NADA"}


def test_fk_to_a_filtered_table_is_deferred_with_its_warning() -> None:
    plan = _plan(MVG)

    pedido = next(t for t in plan.tables if t.name.upper() == "MVG_PEDIDO")
    fks = {fk_.name.upper(): fk_ for fk_ in pedido.foreign_keys}
    assert fks["FK_PED_MON"].outside_filter
    assert fks["FK_PED_MON"].is_external
    assert not fks["FK_PED_CLI"].outside_filter
    assert not fks["FK_PED_CLI"].is_external
    outside = [w for w in plan.warnings if w.code == "FK_OUTSIDE_FILTER"]
    assert [(w.table.upper(), w.target_type.upper(), w.severity) for w in outside] == [
        ("MVG_PEDIDO", "COB_MONEDA", "WARNING")
    ]
    assert not [w for w in plan.warnings if w.code == "FK_DEFERRED"]
    assert plan.error_count == 0


@pytest.mark.parametrize("target", ["postgresql", "oracle", "sqlserver", "mysql"])
def test_fk_to_a_filtered_table_goes_at_the_end_of_the_script(target: str) -> None:
    plan = MigrationPlanner(source_engine="mariadb", target_engine=target).plan(_source(), "S", table_filter=MVG)

    statements = plan.emit_statements()
    create = next(s for s in statements if "CREATE TABLE" in s.upper() and "MVG_PEDIDO" in s.upper())
    assert "COB_MONEDA" not in create.upper()  # no va en línea: la tabla no está en el script
    alter = [s for s in statements if "ALTER TABLE" in s.upper() and "COB_MONEDA" in s.upper()]
    assert len(alter) == 1
    assert "fuera del filtro de tablas del plan" in alter[0]
    assert statements.index(alter[0]) > statements.index(create)
    assert not [s for s in statements if "CREATE TABLE" in s.upper() and "COB_MONEDA" in s.upper().split("(")[0]]


def test_frontier_lists_neighbours_by_fk_in_both_directions_but_not_excluded() -> None:
    assert [name.upper() for name in _plan(MVG).frontier] == ["AUX_LOG", "COB_MONEDA"]

    excluding = TableFilter.from_patterns(include="MVG_*", exclude=["*_BAK", "AUX_*"])
    assert [name.upper() for name in _plan(excluding).frontier] == ["COB_MONEDA"]

    no_frontier = TableFilter.from_config({"incluir": ["MVG_*"], "frontera": False})
    assert no_frontier is not None
    assert _plan(no_frontier).frontier == []


def test_exclude_only_keeps_the_rest() -> None:
    plan = _plan(TableFilter.from_patterns(exclude=["COB_*", "*_bak"]))
    assert _names(plan.tables) == ["AUX_LOG", "MVG_CLIENTE", "MVG_PEDIDO"]
    assert _names(plan.views) == ["MVG_V_PEDIDOS"]


def test_nothing_matches_raises() -> None:
    with pytest.raises(ValueError, match="Ninguna tabla ni vista"):
        _plan(TableFilter.from_patterns(include="NADA_*"))


def test_only_views_match_is_a_plan_without_tables() -> None:
    plan = _plan(TableFilter.from_patterns(include="*_V_*"))
    assert plan.tables == []
    assert _names(plan.views) == ["COB_V_MONEDAS", "MVG_V_PEDIDOS"]


def test_without_filter_the_plan_does_not_change() -> None:
    plan = _plan()
    assert plan.table_filter is None
    assert plan.frontier == []
    assert len(plan.tables) == 5
    assert not [w for w in plan.warnings if w.code == "FK_OUTSIDE_FILTER"]
    assert all(not fk_.outside_filter for t in plan.tables for fk_ in t.foreign_keys)


def test_filtered_view_is_rewritten_like_without_filter() -> None:
    """Las vistas del plan se reescriben con los nombres de todo el schema, aunque lean tablas de fuera."""
    with_filter = next(v for v in _plan(MVG).views if v.name.upper() == "MVG_V_PEDIDOS")
    without = next(v for v in _plan().views if v.name.upper() == "MVG_V_PEDIDOS")
    assert with_filter.query == without.query


def test_serialization_round_trip_keeps_filter_and_frontier() -> None:
    plan = _plan(MVG)
    data = json.loads(json.dumps(plan.to_dict()))
    assert data["table_filter"] == {"include": ["mvg_*"], "exclude": ["*_BAK"], "frontier": True}
    assert [name.upper() for name in data["frontier"]] == ["AUX_LOG", "COB_MONEDA"]

    restored = MigrationPlan.from_dict(data)
    assert restored.table_filter == MVG
    assert restored.frontier == plan.frontier
    assert restored.emit_statements() == plan.emit_statements()


def test_plan_without_the_new_keys_still_loads() -> None:
    """Un ``migration_plan.json`` anterior a 5.9.0 no tiene ``table_filter`` ni ``frontier`` ni ``outside_filter``."""
    data = json.loads(json.dumps(_plan().to_dict()))
    del data["table_filter"], data["frontier"]
    for table_ in data["tables"]:
        for fk_ in table_["foreign_keys"]:
            del fk_["outside_filter"]

    restored = MigrationPlan.from_dict(data)
    assert restored.table_filter is None
    assert restored.frontier == []


@pytest.mark.parametrize(
    "value",
    ["MVG_*", {"include": ["MVG_*"], "frontier": "sí"}, {"include": [""]}, {"include": "x" * 129}],
)
def test_invalid_serialized_filter_is_rejected(value: Any) -> None:
    data = json.loads(json.dumps(_plan(MVG).to_dict()))
    data["table_filter"] = value
    with pytest.raises(MigrationPlanValidationError, match="table_filter"):
        MigrationPlan.from_dict(data)


def test_table_filter_is_keyword_only() -> None:
    planner = MigrationPlanner(source_engine="mariadb", target_engine="postgresql")
    with pytest.raises(TypeError):
        planner.plan(_source(), "S", MVG)  # type: ignore[misc]
