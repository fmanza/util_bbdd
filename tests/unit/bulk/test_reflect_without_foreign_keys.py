"""Q9 (performance-audit de dump 2026-09-26): ``BulkCrud(reflect_foreign_keys=False)``.

En SQL Server, leer las FK es la mitad de la reflexión de una tabla (≈ 17 de 32 ms) y ``BulkCrud`` no las usa. Con la
opción desactivada, ``reflect_table`` devuelve la misma tabla sin FK. ``dump`` la desactiva en sus ``BulkCrud`` y en su
``ParallelBulkLoader``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy import Engine, Inspector, create_engine, text
from sqlalchemy.exc import NoSuchTableError

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution import parallel_loader as pl_mod
from util_bbdd.bulk._execution.parallel_loader import ParallelBulkLoader
from util_bbdd.dump import DumpConfig, DumpOrchestrator

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'fk.db'}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        conn.execute(
            text(
                "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER NOT NULL REFERENCES parent (id), "
                "s VARCHAR(20) DEFAULT 'x')"
            )
        )
        conn.execute(text("CREATE INDEX ix_child_s ON child (s)"))
    yield eng
    eng.dispose()


def _signature(table: Any) -> list[tuple[Any, ...]]:
    return [(c.name, repr(c.type), c.nullable, c.primary_key, c.autoincrement) for c in table.columns]


def test_same_table_without_foreign_keys(engine: Engine) -> None:
    default = BulkCrud(engine, warn_if_audit_disabled=False).reflect_table("child")
    without_fk = BulkCrud(engine, warn_if_audit_disabled=False, reflect_foreign_keys=False).reflect_table("child")

    assert _signature(without_fk) == _signature(default)
    assert [c.name for c in without_fk.primary_key.columns] == ["id"]
    assert {i.name for i in without_fk.indexes} == {i.name for i in default.indexes} == {"ix_child_s"}
    assert len(default.foreign_keys) == 1
    assert not without_fk.foreign_keys
    assert set(without_fk.metadata.tables) == {"child"}


def test_foreign_keys_are_not_read(engine: Engine) -> None:
    with patch.object(Inspector, "get_multi_foreign_keys", side_effect=AssertionError("se leyeron las FK")):
        table = BulkCrud(engine, warn_if_audit_disabled=False, reflect_foreign_keys=False).reflect_table("child")
    assert [c.name for c in table.columns] == ["id", "parent_id", "s"]


def test_reflection_is_cached(engine: Engine) -> None:
    crud = BulkCrud(engine, warn_if_audit_disabled=False, reflect_foreign_keys=False)
    assert crud.reflect_table("child") is crud.reflect_table("child")


def test_missing_table_raises_like_the_default(engine: Engine) -> None:
    with pytest.raises(NoSuchTableError):
        BulkCrud(engine, warn_if_audit_disabled=False).reflect_table("missing")
    with pytest.raises(NoSuchTableError):
        BulkCrud(engine, warn_if_audit_disabled=False, reflect_foreign_keys=False).reflect_table("missing")


def test_parallel_loader_passes_the_option_to_its_bulkcruds(engine: Engine) -> None:
    loader = ParallelBulkLoader(engine, max_workers=1, reflect_foreign_keys=False)
    with patch.object(pl_mod, "BulkCrud", wraps=BulkCrud) as spy:
        loader._resolve_table("child")
        loader._load_partition("child", lambda: iter(()), False, False, 0)
    assert spy.call_count == 2
    assert all(call.kwargs["reflect_foreign_keys"] is False for call in spy.call_args_list)


def test_dump_creates_bulkcrud_without_foreign_keys(engine: Engine) -> None:
    orch = DumpOrchestrator.__new__(DumpOrchestrator)
    orch._cfg = DumpConfig(source_engine=MagicMock(), target_engine=engine)
    orch._reset_audit_tracking()
    assert orch._make_worker_crud()._reflect_foreign_keys is False
