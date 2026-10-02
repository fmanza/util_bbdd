"""Tests del banco de pruebas ``scripts/bench_compare.py`` (partes sin base de datos)."""

from __future__ import annotations

import importlib.util
import sys

from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "bench_compare.py"


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    if not SCRIPT.exists():
        pytest.skip("scripts/bench_compare.py no está en el árbol (¿tests ejecutados sin scripts/?)")
    spec = importlib.util.spec_from_file_location("bench_compare", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_compare"] = module  # dataclasses resuelve las anotaciones vía sys.modules
    spec.loader.exec_module(module)
    return module


class TestMakeUrl:
    def test_requires_bench_password(self, bench: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UTIL_BBDD_BENCH_PASSWORD", raising=False)

        with pytest.raises(SystemExit, match="UTIL_BBDD_BENCH_PASSWORD"):
            bench.make_url("postgresql")

    @pytest.mark.parametrize(
        ("engine_key", "user", "port"),
        [
            ("postgresql", "bench", 55432),
            ("mysql", "root", 53306),
            ("mariadb", "root", 53307),
            ("oracle", "system", 51521),
        ],
    )
    def test_bench_container_defaults(
        self, bench: ModuleType, monkeypatch: pytest.MonkeyPatch, engine_key: str, user: str, port: int
    ) -> None:
        monkeypatch.setenv("UTIL_BBDD_BENCH_PASSWORD", "x")

        url = bench.make_url(engine_key)

        assert (url.host, url.username, url.port) == ("127.0.0.1", user, port)

    def test_port_override(self, bench: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UTIL_BBDD_BENCH_PASSWORD", "x")
        monkeypatch.setenv("UTIL_BBDD_BENCH_POSTGRES_PORT", "60000")

        assert bench.make_url("postgresql").port == 60000

    @pytest.mark.parametrize(("driver", "drivername"), [("pymssql", "mssql+pymssql"), ("pyodbc", "mssql+pyodbc")])
    def test_mssql_driver(
        self, bench: ModuleType, monkeypatch: pytest.MonkeyPatch, driver: str, drivername: str
    ) -> None:
        monkeypatch.setenv("UTIL_BBDD_BENCH_PASSWORD", "x")

        assert bench.make_url("mssql", mssql_driver=driver).drivername == drivername

    def test_unknown_engine(self, bench: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UTIL_BBDD_BENCH_PASSWORD", "x")

        with pytest.raises(SystemExit, match="no soportado"):
            bench.make_url("sqlite")


class TestDdl:
    def test_oracle_schemas_are_uppercase_users(self, bench: ModuleType) -> None:
        assert bench.schemas("oracle") == ("CMP_SRC", "CMP_TGT")
        assert bench.schemas("postgresql") == ("cmp_src", "cmp_tgt")

    @pytest.mark.parametrize("engine_key", ["postgresql", "mysql", "mariadb", "mssql", "oracle"])
    def test_target_differs_in_ten_percent_of_tables_and_twenty_of_views(
        self, bench: ModuleType, engine_key: str
    ) -> None:
        source = bench.ddl(engine_key, "s", tables=50, target=False)
        target = bench.ddl(engine_key, "s", tables=50, target=True)

        tables = [s for s in target if s.startswith("CREATE TABLE")]
        assert len(tables) == 50
        assert sum("extra" in s for s in tables) == 5
        assert sum("CREATE VIEW" in s for s in target) == 5
        assert len(set(source) ^ set(target)) == 2 * (5 + 1 + 1)  # 5 tablas, 1 vista y 1 función distintas

    def test_only_oracle_qualifies_index_name(self, bench: ModuleType) -> None:
        assert "CREATE INDEX s.ix_t0 ON s.t0(name)" in bench.ddl("oracle", "s", tables=1, target=False)
        assert "CREATE INDEX ix_t0 ON s.t0(name)" in bench.ddl("postgresql", "s", tables=1, target=False)


def test_markdown_table(bench: ModuleType) -> None:
    measurement = bench.Measurement("postgresql", 200, True, 0.151, 62, 20, 60, 20, 20)

    table = bench.to_markdown([measurement])

    assert table.splitlines()[-1] == "| postgresql | 200 | sí | 0.15 s | 62 | 20 | 60 | 20 | 20 |"
