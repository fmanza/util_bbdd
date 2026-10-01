"""Tests del banco de pruebas ``scripts/bench_bulk.py`` (ejecución en proceso contra SQLite)."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys

from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "bench_bulk.py"


@pytest.fixture(scope="module")
def bench() -> ModuleType:
    if not SCRIPT.exists():
        pytest.skip("scripts/bench_bulk.py no está en el árbol (¿tests ejecutados sin scripts/?)")
    spec = importlib.util.spec_from_file_location("bench_bulk", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_bulk"] = module  # dataclasses resuelve las anotaciones vía sys.modules
    spec.loader.exec_module(module)
    return module


class TestResolveEngineUrl:
    def test_bench_var_has_priority_over_test_var(self, bench: ModuleType) -> None:
        env = {"UTIL_BBDD_BENCH_MYSQL_URL": "mysql+pymysql://b", "UTIL_BBDD_TEST_MYSQL_URL": "mysql+pymysql://t"}
        assert bench.resolve_engine_url("mysql", env) == "mysql+pymysql://b"

    @pytest.mark.parametrize(
        ("engine_key", "url", "warns"),
        [
            ("postgresql", "postgresql+psycopg://bench:x@127.0.0.1:55432/bench", False),
            ("postgresql", "postgresql+psycopg://admin:x@localhost:5432/testdb", True),
            ("postgresql", "postgresql+psycopg://admin:x@localhost/testdb", True),  # sin puerto: el estándar
            ("mysql", "mysql+pymysql://bench:x@127.0.0.1:53306/bench", False),
            ("mariadb", "mariadb+pymysql://u:x@db:3306/app", True),
            ("mssql", "mssql+pymssql://sa:x@127.0.0.1:1433/bench", True),
            ("oracle", "oracle+oracledb://bench:x@127.0.0.1:51521/?service_name=FREEPDB1", False),
            ("sqlite", "sqlite:///bench.db", False),
        ],
    )
    def test_warns_when_url_uses_standard_port(
        self, bench: ModuleType, caplog: pytest.LogCaptureFixture, engine_key: str, url: str, warns: bool
    ) -> None:
        with caplog.at_level("WARNING", logger="bench_bulk"):
            assert bench.resolve_engine_url(engine_key, {f"UTIL_BBDD_BENCH_{engine_key.upper()}_URL": url}) == url

        assert any("puerto estándar" in r.getMessage() for r in caplog.records) is warns

    def test_falls_back_to_integration_test_var(self, bench: ModuleType) -> None:
        env = {"UTIL_BBDD_TEST_MARIADB_URL": "mariadb+pymysql://t"}
        assert bench.resolve_engine_url("mariadb", env) == "mariadb+pymysql://t"

    def test_mariadb_connector_reuses_the_mariadb_url_with_the_original_driver(self, bench: ModuleType) -> None:
        env = {"UTIL_BBDD_TEST_MARIADB_URL": "mariadb+pymysql://bench:x@127.0.0.1:53307/bench"}
        assert (
            bench.resolve_engine_url("mariadb_connector", env)
            == "mariadb+mariadbconnector://bench:x@127.0.0.1:53307/bench"
        )
        own = {**env, "UTIL_BBDD_BENCH_MARIADB_CONNECTOR_URL": "mariadb+mariadbconnector://o:x@127.0.0.1:53307/b"}
        assert bench.resolve_engine_url("mariadb_connector", own) == "mariadb+mariadbconnector://o:x@127.0.0.1:53307/b"
        assert bench.resolve_engine_url("mariadb_connector", {}) is None

    def test_missing_server_engine_returns_none(self, bench: ModuleType) -> None:
        assert bench.resolve_engine_url("oracle", {}) is None

    def test_sqlite_without_url_uses_temporary_file(self, bench: ModuleType) -> None:
        url = bench.resolve_engine_url("sqlite", {})
        assert url is not None and url.startswith("sqlite:///") and url.endswith("bench.db")


class TestNamingAndVariants:
    @pytest.mark.parametrize(
        ("dialect", "expected"),
        [("mssql", "ZZ_UTIL_BBDD_BENCH"), ("postgresql", "zz_util_bbdd_bench"), ("mysql", "zz_util_bbdd_bench")],
    )
    def test_physical_name_follows_bulkcrud_convention(self, bench: ModuleType, dialect: str, expected: str) -> None:
        assert bench.physical_name("zz_util_bbdd_bench", dialect) == expected

    def test_build_table_uses_explicit_pk_without_autoincrement(self, bench: ModuleType) -> None:
        # Tabla en MAYÚSCULAS (convención de BulkCrud); columnas en minúsculas en SQL Server para ejercitar PD-01.
        table = bench.build_table("mssql")
        assert table.name == "ZZ_UTIL_BBDD_BENCH"
        assert [c.name for c in table.primary_key.columns] == ["id"]
        assert table.c["id"].autoincrement is False

    @pytest.mark.parametrize(
        ("dialect", "expected"), [("mssql", "a"), ("postgresql", "a"), ("oracle", "a"), ("mysql", "a")]
    )
    def test_physical_column_is_lowercase_on_sql_server(self, bench: ModuleType, dialect: str, expected: str) -> None:
        assert bench.physical_column("a", dialect) == expected

    def test_reset_table_refuses_other_tables(self, bench: ModuleType) -> None:
        from sqlalchemy import Column, Integer, MetaData, Table, create_engine

        other = Table("clientes", MetaData(), Column("id", Integer, primary_key=True))
        with pytest.raises(ValueError, match="Tabla inesperada"):
            bench.reset_table(create_engine("sqlite://"), other)

    @pytest.mark.parametrize(
        ("variant", "dialect", "driver", "expected"),
        [
            ("baseline", "oracle", "oracle+oracledb", True),
            ("mysql-multirow-legacy", "mariadb", "mariadb+pymysql", True),
            ("mysql-multirow-legacy", "postgresql", "postgresql+psycopg", False),
            ("p01-mssql-engine-fast-executemany", "mssql", "mssql+pyodbc", True),
            ("p01-mssql-engine-fast-executemany", "mssql", "mssql+pymssql", False),
        ],
    )
    def test_variant_applies_to(
        self, bench: ModuleType, variant: str, dialect: str, driver: str, expected: bool
    ) -> None:
        assert bench.VARIANTS[variant].applies_to(dialect, driver) is expected

    def test_legacy_variant_injects_multirow_strategy_for_mysql(self, bench: ModuleType) -> None:
        from util_bbdd.bulk._execution.batch import MySQLMultiRowInsertStrategy

        resolver = bench.VARIANTS["mysql-multirow-legacy"].crud_kwargs()["insert_resolver"]
        assert isinstance(resolver.resolve("mysql", "mysql+pymysql"), MySQLMultiRowInsertStrategy)


class TestMeasureStep:
    def _base(self, bench: ModuleType):
        return bench.Measurement("sqlite", "pysqlite", "baseline", "delete", 10, 1, None, None, False)

    def test_exception_is_recorded_not_raised(self, bench: ModuleType) -> None:
        def boom() -> None:
            raise RuntimeError("The incoming request has too many parameters")

        m = bench._measure_step((boom, lambda: True), self._base(bench), memory=False)
        assert m.ok is False
        assert m.seconds is None
        assert "RuntimeError" in m.error and "too many parameters" in m.error

    def test_failed_verification_marks_measurement_not_ok(self, bench: ModuleType) -> None:
        m = bench._measure_step((lambda: None, lambda: False), self._base(bench), memory=False)
        assert m.ok is False
        assert m.seconds is not None
        assert "verificación SQL fallida" in m.error

    def test_memory_mode_records_peak(self, bench: ModuleType) -> None:
        m = bench._measure_step((lambda: [0] * 100_000 and None, lambda: True), self._base(bench), memory=True)
        assert m.ok is True
        assert m.peak_mb is not None and m.peak_mb > 0


class TestRunBenchmarkSqlite:
    def test_full_cycle_writes_verified_results(self, bench: ModuleType, tmp_path: Path) -> None:
        env = {"UTIL_BBDD_BENCH_SQLITE_URL": f"sqlite:///{tmp_path / 'b.db'}"}
        measurements = bench.run_benchmark(
            engines=["sqlite", "mysql"],
            sizes=[50],
            ops=list(bench.OPS),
            variants=list(bench.VARIANTS),
            repeat=1,
            chunk_size=20,
            out_dir=tmp_path / "out",
            environ=env,
        )

        # Solo baseline aplica a SQLite; mysql no tiene URL y se salta.
        assert [(m.engine, m.variant, m.op, m.ok) for m in measurements] == [
            ("sqlite", "baseline", "insert", True),
            ("sqlite", "baseline", "update", True),
            ("sqlite", "baseline", "delete", True),
        ]
        environment = json.loads((tmp_path / "out" / "environment.json").read_text(encoding="utf-8"))
        assert environment["engines"]["mysql"] == {"status": "skipped"}
        assert environment["engines"]["sqlite"]["status"] == "ok"
        with (tmp_path / "out" / "results.csv").open(encoding="utf-8") as handle:
            assert len(list(csv.DictReader(handle))) == 3
        # La auditoría integrada registra cada operación medida.
        audit_lines = (tmp_path / "out" / "audit.csv").read_text(encoding="utf-8").splitlines()
        assert len(audit_lines) == 1 + 3
        summary = (tmp_path / "out" / "summary.md").read_text(encoding="utf-8")
        assert "| sqlite | insert | 50 | baseline |" in summary

    def test_only_update_seeds_data_without_measuring_insert(self, bench: ModuleType, tmp_path: Path) -> None:
        env = {"UTIL_BBDD_BENCH_SQLITE_URL": f"sqlite:///{tmp_path / 'b.db'}"}
        measurements = bench.run_benchmark(
            engines=["sqlite"],
            sizes=[30],
            ops=["update"],
            variants=["baseline"],
            repeat=2,
            chunk_size=10,
            out_dir=tmp_path / "out",
            environ=env,
        )
        assert [(m.op, m.repeat, m.ok) for m in measurements] == [("update", 1, True), ("update", 2, True)]

    def test_unreachable_engine_is_recorded_and_skipped(self, bench: ModuleType, tmp_path: Path) -> None:
        env = {"UTIL_BBDD_BENCH_SQLITE_URL": f"sqlite:///{tmp_path / 'no_existe' / 'x' / 'b.db'}"}
        measurements = bench.run_benchmark(
            engines=["sqlite"],
            sizes=[10],
            ops=["insert"],
            variants=["baseline"],
            repeat=1,
            chunk_size=10,
            out_dir=tmp_path / "out",
            environ=env,
        )
        assert measurements == []
        environment = json.loads((tmp_path / "out" / "environment.json").read_text(encoding="utf-8"))
        assert environment["engines"]["sqlite"]["status"] == "error"


class TestSummary:
    def test_median_and_speedup_against_baseline(self, bench: ModuleType) -> None:
        M = bench.Measurement
        ms = [
            M("mysql", "pymysql", "baseline", "insert", 100, 1, 2.0, 50.0, True),
            M("mysql", "pymysql", "baseline", "insert", 100, 2, 4.0, 25.0, True),
            M("mysql", "pymysql", "baseline", "insert", 100, 3, 3.0, 33.3, True),
            M("mysql", "pymysql", "mysql-multirow-legacy", "insert", 100, 1, 1.5, 66.7, True),
            M("mysql", "pymysql", "baseline", "delete", 100, 1, None, None, False, "DBAPIError: boom"),
        ]
        rows = {(r["variant"], r["op"]): r for r in bench.summarize(ms)}
        assert rows[("baseline", "insert")]["median_s"] == 3.0
        assert rows[("baseline", "delete")]["runs_error"] == 1
        env = {"timestamp": "t", "python": "3", "pandas": "3", "sqlalchemy": "2", "chunk_size": 1, "repeat": 3}
        env["engines"] = {"mysql": {"status": "ok", "server_version": "8.4", "driver": "mysql+pymysql"}}
        text = bench.render_summary(ms, env)
        assert "| 2.00× |" in text
        assert "DBAPIError: boom" in text


class TestCli:
    def test_list_variants(self, bench: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        assert bench.main(["--list-variants"]) == 0
        assert "mysql-multirow-legacy" in capsys.readouterr().out

    def test_unknown_engine_is_rejected(self, bench: ModuleType) -> None:
        with pytest.raises(SystemExit) as exc:
            bench.main(["--engines", "db2"])
        assert exc.value.code == 2

    def test_non_positive_values_are_rejected(self, bench: ModuleType) -> None:
        assert bench.main(["--repeat", "0"]) == 2
