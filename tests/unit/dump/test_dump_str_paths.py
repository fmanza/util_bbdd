"""Rutas ``str`` en ``DumpConfig`` (v1.1.0).

Hasta v1.0.0, ``DumpConfig(output_dir="out")`` cargaba los datos y después fallaba con ``TypeError`` al escribir el
informe, sin devolver el ``DumpResult``; ``bulk_audit_path`` como ``str`` fallaba con ``AttributeError`` antes de cargar.
"""

from __future__ import annotations

import dataclasses

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.dump import DumpConfig, DumpOrchestrator

pytestmark = pytest.mark.unit

_DDL = "CREATE TABLE items (id INTEGER PRIMARY KEY, v TEXT)"


@pytest.fixture
def engines(tmp_path: Path) -> Iterator[tuple[Engine, Engine]]:
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    for eng in (src, dst):
        with eng.begin() as conn:
            conn.exec_driver_sql(_DDL)
    with src.begin() as conn:
        conn.exec_driver_sql("INSERT INTO items VALUES (1, 'a'), (2, 'b')")
    yield src, dst
    src.dispose()
    dst.dispose()


def _mock_engine() -> MagicMock:
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    return engine


class TestDumpConfig:
    def test_str_paths_are_stored_as_path(self) -> None:
        cfg = DumpConfig(
            source_engine=_mock_engine(),
            target_engine=_mock_engine(),
            output_dir="out",
            bulk_audit_path="audit.csv",
            on_error="isolate",
            rejects_csv_path="rejects.csv",
        )

        assert cfg.output_dir == Path("out")
        assert cfg.bulk_audit_path == Path("audit.csv")
        assert cfg.rejects_csv_path == Path("rejects.csv")
        assert all(isinstance(p, Path) for p in (cfg.output_dir, cfg.bulk_audit_path, cfg.rejects_csv_path))

    def test_default_output_dir_is_still_the_working_directory(self) -> None:
        assert DumpConfig(source_engine=_mock_engine(), target_engine=_mock_engine()).output_dir == Path()

    @pytest.mark.parametrize("parameter", ["output_dir", "bulk_audit_path", "rejects_csv_path"])
    def test_other_types_raise_value_error_at_construction(self, parameter: str) -> None:
        with pytest.raises(ValueError, match=rf"{parameter} debe ser una ruta"):
            DumpConfig(source_engine=_mock_engine(), target_engine=_mock_engine(), **{parameter: 123})  # type: ignore[arg-type]

    def test_reassigning_an_invalid_type_raises_at_once(self) -> None:
        # T-09: las rutas son descriptores; antes una reasignación inválida solo fallaba en run().
        cfg = DumpConfig(source_engine=_mock_engine(), target_engine=_mock_engine())

        with pytest.raises(ValueError, match=r"output_dir debe ser una ruta"):
            cfg.output_dir = 123  # type: ignore[assignment]
        assert cfg.output_dir == Path()

    def test_replace_and_repr_keep_paths(self) -> None:
        cfg = DumpConfig(source_engine=_mock_engine(), target_engine=_mock_engine(), bulk_audit_path="a.csv")

        replaced = dataclasses.replace(cfg, output_dir="otra")

        assert replaced.output_dir == Path("otra")
        assert replaced.bulk_audit_path == Path("a.csv")
        assert replaced.rejects_csv_path is None
        assert "output_dir=" in repr(replaced)


class TestDumpRun:
    def test_output_dir_str_returns_the_result_and_writes_the_report(
        self, engines: tuple[Engine, Engine], tmp_path: Path
    ) -> None:
        src, dst = engines
        out = tmp_path / "out"

        result = DumpOrchestrator(DumpConfig(source_engine=src, target_engine=dst, output_dir=str(out))).run()

        assert result.report.parent == out
        assert result.report.suffix == ".xlsx"
        assert result.report.is_file()
        with dst.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one() == 2

    def test_bulk_audit_path_str_audits_the_load(self, engines: tuple[Engine, Engine], tmp_path: Path) -> None:
        src, dst = engines
        audit = tmp_path / "audit.csv"

        result = DumpOrchestrator(
            DumpConfig(source_engine=src, target_engine=dst, output_dir=tmp_path, bulk_audit_path=str(audit))
        ).run()

        assert audit.is_file()
        assert result.audit_summary is not None

    def test_path_reassigned_as_str_after_construction_still_works(
        self, engines: tuple[Engine, Engine], tmp_path: Path
    ) -> None:
        src, dst = engines
        cfg = DumpConfig(source_engine=src, target_engine=dst)
        cfg.output_dir = str(tmp_path / "late")

        result = DumpOrchestrator(cfg).run()

        assert result.report.parent == tmp_path / "late"
