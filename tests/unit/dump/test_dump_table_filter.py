"""5.9.0 (G57 de util_bbdd_web): ``DumpConfig.table_filter``, como el filtro de la documentación."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sqlalchemy import create_engine, text

from util_bbdd.dump import DumpConfig, DumpError, DumpOrchestrator
from util_bbdd.metadata import TableFilter

pytestmark = pytest.mark.unit

# MVG_PEDIDO → COB_MONEDA (fuera del filtro); MVG_PEDIDO_BAK, excluida
DDL = [
    "CREATE TABLE COB_MONEDA (id INTEGER PRIMARY KEY)",
    "CREATE TABLE MVG_CLIENTE (id INTEGER PRIMARY KEY)",
    "CREATE TABLE MVG_PEDIDO (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES MVG_CLIENTE(id), "
    "moneda_id INTEGER REFERENCES COB_MONEDA(id))",
    "CREATE TABLE MVG_PEDIDO_BAK (id INTEGER PRIMARY KEY)",
]
ROWS = [
    "INSERT INTO COB_MONEDA VALUES (1)",
    "INSERT INTO MVG_CLIENTE VALUES (1)",
    "INSERT INTO MVG_PEDIDO VALUES (1, 1, 1)",
    "INSERT INTO MVG_PEDIDO_BAK VALUES (1)",
]
MVG = TableFilter.from_patterns(include="mvg_*", exclude="*_bak")


def _engine(path: Path, statements: list[str]) -> Any:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    return engine


def _config(tmp_path: Path, **kw: Any) -> DumpConfig:
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    return DumpConfig(
        source_engine=_engine(tmp_path / "src.db", DDL + ROWS),
        target_engine=_engine(tmp_path / "dst.db", [*DDL, "INSERT INTO COB_MONEDA VALUES (1)"]),
        output_dir=out,
        truncate_target=True,
        **kw,
    )


def test_plan_and_run_dump_only_matching_tables(tmp_path: Path) -> None:
    config = _config(tmp_path, table_filter=MVG)
    plan = DumpOrchestrator(config).plan()

    assert [t.table_name for t in plan.tables] == ["MVG_CLIENTE", "MVG_PEDIDO"]
    assert [(w.code, w.table) for w in plan.warnings if w.code == "OUTSIDE_REFERENCES"] == [
        ("OUTSIDE_REFERENCES", "MVG_PEDIDO")
    ]

    result = DumpOrchestrator(config).run()
    assert result.load_order == plan.load_order
    assert sorted(t.table_name for t in result.table_results) == ["MVG_CLIENTE", "MVG_PEDIDO"]
    with config.target_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM MVG_PEDIDO_BAK")).scalar() == 0


def test_exclude_only(tmp_path: Path) -> None:
    plan = DumpOrchestrator(_config(tmp_path, table_filter=TableFilter.from_patterns(exclude="MVG_*"))).plan()
    assert [t.table_name for t in plan.tables] == ["COB_MONEDA"]


def test_nothing_matches_is_a_dump_error(tmp_path: Path) -> None:
    orchestrator = DumpOrchestrator(_config(tmp_path, table_filter=TableFilter.from_patterns(include="NADA_*")))
    with pytest.raises(DumpError, match="Ninguna tabla del origen casa con el filtro"):
        orchestrator.plan()


def test_tables_and_table_filter_are_exclusive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="tables o table_filter"):
        _config(tmp_path, tables=["MVG_PEDIDO"], table_filter=MVG)


def test_table_filter_must_be_a_table_filter(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="TableFilter"):
        _config(tmp_path, table_filter={"incluir": ["MVG_*"]})
