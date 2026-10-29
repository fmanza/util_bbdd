"""U-8.1 (G30 de util_bbdd_web): ``truncate_target=False`` por defecto desde 5.0.0, sin ``FutureWarning``."""

from __future__ import annotations

import dataclasses
import warnings

from pathlib import Path

import pytest

from sqlalchemy import create_engine, text

from util_bbdd.dump import DumpConfig, DumpOrchestrator

pytestmark = pytest.mark.unit

ENGINE = create_engine("sqlite://")


def test_default_is_false_and_does_not_warn() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        config = DumpConfig(ENGINE, ENGINE)

    assert config.truncate_target is False
    (field,) = [f for f in dataclasses.fields(DumpConfig) if f.name == "truncate_target"]
    assert field.default is False


@pytest.mark.parametrize("value", [True, False])
def test_explicit_value_is_kept(value: bool) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        config = DumpConfig(ENGINE, ENGINE, truncate_target=value)

    assert config.truncate_target is value


def test_manage_indexes_all_requires_explicit_truncate() -> None:
    """Con ``False`` por defecto, ``manage_indexes="all"`` sin el argumento falla (antes valía el ``True`` implícito)."""
    with pytest.raises(ValueError, match="manage_indexes='all' exige truncate_target=True"):
        DumpConfig(ENGINE, ENGINE, manage_indexes="all")

    assert DumpConfig(ENGINE, ENGINE, manage_indexes="all", truncate_target=True).truncate_target is True


def test_run_without_argument_keeps_target_rows(tmp_path: Path) -> None:
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    for engine in (src, dst):
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, nombre VARCHAR(20))"))
    with src.begin() as conn:
        conn.execute(text("INSERT INTO t VALUES (2, 'origen')"))
    with dst.begin() as conn:
        conn.execute(text("INSERT INTO t VALUES (1, 'previa')"))

    result = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path)).run()

    assert [r.status for r in result.table_results] == ["success"]
    with dst.connect() as conn:
        rows = conn.execute(text("SELECT id, nombre FROM t ORDER BY id")).all()
    assert [tuple(r) for r in rows] == [(1, "previa"), (2, "origen")]
