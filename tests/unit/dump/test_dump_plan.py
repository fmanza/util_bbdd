"""U-V1 (G29 de util_bbdd_web): ``DumpOrchestrator.plan()``, vista previa del volcado sin escribir."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.dump import DumpConfig, DumpError, DumpOrchestrator, DumpPlan

SOURCE_DDL = [
    "CREATE TABLE externa (id INTEGER PRIMARY KEY)",
    "CREATE TABLE padre (id INTEGER PRIMARY KEY, nombre TEXT)",
    "CREATE TABLE hija (id INTEGER PRIMARY KEY, padre_id INTEGER REFERENCES padre(id), extra TEXT)",
    "CREATE TABLE con_ext (id INTEGER PRIMARY KEY, ext_id INTEGER REFERENCES externa(id))",
    "CREATE TABLE ciclo_a (id INTEGER PRIMARY KEY, b_id INTEGER REFERENCES ciclo_b(id))",
    "CREATE TABLE ciclo_b (id INTEGER PRIMARY KEY, a_id INTEGER REFERENCES ciclo_a(id))",
    "CREATE TABLE solo_origen (id INTEGER PRIMARY KEY)",
    "CREATE TABLE sin_comunes (a INTEGER)",
    "INSERT INTO padre VALUES (1, 'uno')",
    "INSERT INTO hija VALUES (1, 1, 'x')",
]
TARGET_DDL = [
    "CREATE TABLE PADRE (id INTEGER PRIMARY KEY, nombre TEXT)",
    "CREATE TABLE hija (id INTEGER PRIMARY KEY, padre_id INTEGER, obligatoria TEXT NOT NULL, opcional TEXT)",
    "CREATE TABLE con_ext (id INTEGER PRIMARY KEY, ext_id INTEGER)",
    "CREATE TABLE ciclo_a (id INTEGER PRIMARY KEY, b_id INTEGER)",
    "CREATE TABLE ciclo_b (id INTEGER PRIMARY KEY, a_id INTEGER)",
    "CREATE TABLE sin_comunes (b INTEGER)",
    "INSERT INTO PADRE VALUES (7, 'siete')",
]
TABLES = ["padre", "hija", "con_ext", "ciclo_a", "ciclo_b", "solo_origen", "sin_comunes"]


def _engine(path: Path, ddl: list[str]) -> Any:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        for statement in ddl:
            conn.execute(text(statement))
    return engine


@pytest.fixture
def config(tmp_path: Path) -> DumpConfig:
    out = tmp_path / "out"
    out.mkdir()
    return DumpConfig(
        source_engine=_engine(tmp_path / "src.db", SOURCE_DDL),
        target_engine=_engine(tmp_path / "dst.db", TARGET_DDL),
        tables=TABLES,
        output_dir=out,
        truncate_target=True,
    )


def _codes(plan: DumpPlan, table: str | None) -> list[str]:
    return [w.code for w in plan.warnings if w.table == table]


def test_plan_order_matches_run(config: DumpConfig) -> None:
    plan = DumpOrchestrator(config).plan()
    result = DumpOrchestrator(config).run()

    assert plan.load_order == result.load_order
    assert plan.cycles == result.cycles_detected
    assert plan.missing_target == ["solo_origen"]
    assert [t.table_name for t in plan.tables] == plan.load_order
    by_name = {r.table_name: r for r in result.table_results}
    for entry in plan.tables:
        assert entry.load_order_position == by_name[entry.table_name].load_order_position
        assert entry.in_cycle == by_name[entry.table_name].in_cycle
        assert list(entry.skipped_columns) == by_name[entry.table_name].skipped_columns


def test_plan_tables_and_warnings(config: DumpConfig) -> None:
    plan = DumpOrchestrator(config).plan()
    tables = {t.table_name: t for t in plan.tables}

    assert plan.load_order.index("padre") < plan.load_order.index("hija")
    assert sorted(map(sorted, plan.cycles)) == [["ciclo_a", "ciclo_b"]]
    assert tables["padre"].target_table == "PADRE"  # nombre canónico del destino
    assert tables["hija"].skipped_columns == ("extra",)
    assert tables["hija"].required_target_columns == ("obligatoria",)
    assert tables["con_ext"].outside_references == ("externa",)
    assert tables["solo_origen"].target_table is None
    assert tables["solo_origen"].load_order_position == -1
    assert tables["ciclo_a"].in_cycle and tables["ciclo_b"].in_cycle

    assert _codes(plan, "hija") == ["SKIPPED_COLUMNS", "REQUIRED_TARGET_COLUMNS"]
    assert _codes(plan, "con_ext") == ["OUTSIDE_REFERENCES"]
    assert _codes(plan, "solo_origen") == ["MISSING_TARGET"]
    assert _codes(plan, "sin_comunes") == ["NO_COMMON_COLUMNS"]
    assert _codes(plan, "padre") == []
    assert _codes(plan, None) == ["FK_CYCLE", "CONSTRAINTS_NOT_MANAGED", "SQLITE_SOURCE"]
    assert plan.constraints_managed is False


def test_plan_writes_nothing(config: DumpConfig) -> None:
    DumpOrchestrator(config).plan()

    with config.target_engine.connect() as conn:
        assert conn.execute(text("SELECT id FROM PADRE")).scalars().all() == [7]  # sin limpiar ni cargar
        assert conn.execute(text("SELECT COUNT(*) FROM hija")).scalar() == 0
    assert list(config.output_dir.iterdir()) == []  # ni informe ni auditoría


def test_plan_wraps_introspection_errors(config: DumpConfig) -> None:
    orchestrator = DumpOrchestrator(config)
    with (
        patch.object(orchestrator, "_common_columns", side_effect=SQLAlchemyError("caída")),
        pytest.raises(DumpError, match="columnas"),
    ):
        orchestrator.plan()


def test_required_column_rules() -> None:
    required = DumpOrchestrator._is_required
    assert required({"name": "c", "nullable": False, "default": None})
    assert not required({"name": "c", "nullable": True, "default": None})
    assert not required({"name": "c", "nullable": False, "default": "0"})
    assert not required({"name": "c", "nullable": False, "default": None, "autoincrement": True})
    assert not required({"name": "c", "nullable": False, "default": None, "identity": {"start": 1}})
    assert not required({"name": "c", "nullable": False, "default": None, "computed": {"sqltext": "a+1"}})
