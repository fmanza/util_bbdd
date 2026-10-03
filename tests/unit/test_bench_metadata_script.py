"""Tests del banco ``scripts/bench_metadata.py`` (partes sin base de datos)."""

from __future__ import annotations

import importlib.util
import json
import sys

from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "bench_metadata.py"


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    if not SCRIPT.exists():
        pytest.skip("scripts/bench_metadata.py no está en el árbol (¿tests ejecutados sin scripts/?)")
    spec = importlib.util.spec_from_file_location("bench_metadata", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_metadata"] = module
    spec.loader.exec_module(module)
    return module


def test_admin_url_requires_bench_password(bench: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UTIL_BBDD_BENCH_PASSWORD", raising=False)
    with pytest.raises(SystemExit, match="UTIL_BBDD_BENCH_PASSWORD"):
        bench.admin_url("postgresql")


@pytest.mark.parametrize(
    ("engine", "fragment"),
    [
        ("postgresql", "@127.0.0.1:55432/bench"),
        ("mysql", "@127.0.0.1:53306/bench"),
        ("mariadb", "@127.0.0.1:53307/bench"),
        ("sqlserver", "sa:"),
        ("oracle", "service_name=FREEPDB1"),
    ],
)
def test_admin_url_points_to_the_bench_containers(
    bench: ModuleType, monkeypatch: pytest.MonkeyPatch, engine: str, fragment: str
) -> None:
    monkeypatch.setenv("UTIL_BBDD_BENCH_PASSWORD", "p%40ss")  # codificada para URL: se decodifica una vez
    url = bench.admin_url(engine)
    assert fragment in url
    assert "127.0.0.1" in url
    assert "p%40ss" in url  # render_as_string vuelve a codificar la @


def test_port_can_be_overridden(bench: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTIL_BBDD_BENCH_PASSWORD", "x")
    monkeypatch.setenv("UTIL_BBDD_BENCH_POSTGRES_PORT", "6543")
    assert ":6543/" in bench.admin_url("postgresql")


def test_schema_names_are_isolated_per_volume(bench: ModuleType) -> None:
    assert bench.schema_name("postgresql", 50) == "zz_md_50"
    assert bench.schema_name("mysql", 500) == "zz_util_bbdd_md_500"
    assert bench.schema_name("oracle", 5000) == "ZZ_MD_5000"
    assert bench.schema_name("sqlite", 50) == "main"


def test_catalog_classifier(bench: ModuleType) -> None:
    assert bench.CATALOG_RE.search("SELECT * FROM information_schema.columns")
    assert bench.CATALOG_RE.search("PRAGMA main.table_xinfo('t')")
    assert bench.CATALOG_RE.search("SELECT name FROM sys.tables")
    assert not bench.CATALOG_RE.search("INSERT INTO t00001 (id) VALUES (1)")


def test_report_renders_one_table_per_flow(
    bench: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = {
        "flow": "manager_scan",
        "engine": "postgresql",
        "volume": 50,
        "limit": None,
        "median_seconds": 6.96,
        "median_catalog_seconds": 6.83,
        "queries_catalog": 253,
        "info": {},
        "error": None,
    }
    (tmp_path / "postgresql_50_manager_scan.json").write_text(json.dumps(result), encoding="utf-8")
    bench.report(tmp_path)
    out = capsys.readouterr().out
    assert "#### `manager_scan`" in out
    assert "| postgresql | 253 · 6.83 / 6.96 s | — | — |" in out
