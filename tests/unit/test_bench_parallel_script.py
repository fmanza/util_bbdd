"""Tests del banco ``scripts/bench_parallel.py``: funciones puras y una ejecución en proceso contra SQLite."""

from __future__ import annotations

import importlib.util
import logging
import sys

from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    script = SCRIPTS / "bench_parallel.py"
    if not script.exists():
        pytest.skip("scripts/bench_parallel.py no está en el árbol (¿tests ejecutados sin scripts/?)")
    spec = importlib.util.spec_from_file_location("bench_parallel", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_parallel"] = module  # dataclasses resuelve las anotaciones vía sys.modules
    spec.loader.exec_module(module)
    return module


def test_pyodbc_url_keeps_host_and_adds_the_driver(bench: ModuleType) -> None:
    url = bench.to_pyodbc_url("mssql+pymssql://sa:secret@127.0.0.1:51833/bench")
    assert url.startswith("mssql+pyodbc://sa:secret@127.0.0.1:51833/bench?")
    assert "driver=ODBC+Driver+18+for+SQL+Server" in url
    assert "TrustServerCertificate=yes" in url


def test_schedule_alternates_the_order(bench: ModuleType) -> None:
    assert bench.schedule([1, 2, 4], 3) == [[1, 2, 4], [4, 2, 1], [1, 2, 4]]


def test_stats_of_one_and_several_times(bench: ModuleType) -> None:
    assert bench.Stats.of([2.0]) == bench.Stats(2.0, 2.0, 2.0, 1)
    stats = bench.Stats.of([1.0, 2.0, 3.0, 4.0, 5.0])
    assert (stats.median, stats.p25, stats.p75, stats.n) == (3.0, 2.0, 4.0, 5)


@pytest.mark.parametrize(
    ("serial", "parallel", "wins"),
    [
        ([10.0, 10.5, 11.0], [5.0, 5.2, 5.4], True),  # 2× y sin solape
        ([10.0, 10.5, 11.0], [7.5, 7.6, 7.7], False),  # 1,38×: no llega a 1,5×
        ([6.0, 10.0, 20.0], [5.0, 6.0, 12.0], False),  # 1,67× pero los rangos se solapan (inestable)
    ],
)
def test_verdict_uses_the_planner_criterion(
    bench: ModuleType, serial: list[float], parallel: list[float], wins: bool
) -> None:
    _, result = bench.verdict(bench.Stats.of(serial), bench.Stats.of(parallel))
    assert result is wins


def test_runs_against_sqlite(
    bench: ModuleType, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("UTIL_BBDD_BENCH_SQLITE_URL", raising=False)
    monkeypatch.delenv("UTIL_BBDD_TEST_SQLITE_URL", raising=False)
    # main() silencia el logger util_bbdd: se restaura para no afectar a los tests con caplog que vengan después.
    library_logger = logging.getLogger("util_bbdd")
    monkeypatch.setattr(library_logger, "level", library_logger.level)
    table = tmp_path / "logs" / "bench.md"
    argv = [
        "--engines",
        "sqlite",
        "--rows",
        "50",
        "--workers",
        "2",
        "--repeat",
        "1",
        "--warmup",
        "0",
        "--out",
        str(table),
    ]
    code = bench.main(argv)
    out = capsys.readouterr().out
    assert code == 0
    rows = [line for line in out.splitlines() if line.startswith("| sqlite |")]
    assert [line.split("|")[3].strip() for line in rows] == ["insert", "update", "delete"]
    written = table.read_text(encoding="utf-8").splitlines()
    assert written[0].startswith("| Motor |")
    assert written[2:] == rows
