"""Tests del banco ``scripts/bench_index_modes.py``: DDL por motor y modo, veredicto y una ejecución contra SQLite."""

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
    script = SCRIPTS / "bench_index_modes.py"
    if not script.exists():
        pytest.skip("scripts/bench_index_modes.py no está en el árbol (¿tests ejecutados sin scripts/?)")
    spec = importlib.util.spec_from_file_location("bench_index_modes", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_index_modes"] = module  # dataclasses resuelve las anotaciones vía sys.modules
    spec.loader.exec_module(module)
    return module


def _plan(bench: ModuleType, dialect: str, mode: str, profile: str = "sec2u", storage: str = "innodb") -> object:
    return bench.plan_ddl(
        dialect,
        mode,
        bench.index_specs(bench.PROFILES[profile]),
        table_sql="T",
        quote=lambda name: f"<{name}>",
        column=lambda col: col,
        storage=storage,
    )


def test_none_touches_nothing(bench: ModuleType) -> None:
    plan = _plan(bench, "postgresql", "none")
    assert (plan.disable, plan.restore, plan.touched, plan.skipped) == ([], [], [], [])


def test_secondary_never_touches_pk_or_unique(bench: ModuleType) -> None:
    for dialect in ("mssql", "oracle", "postgresql", "mysql", "mariadb", "sqlite"):
        plan = _plan(bench, dialect, "secondary")
        assert plan.touched == ["ix_zz_bench_ix_a", "ix_zz_bench_ix_b"], dialect


def test_mssql_all_keeps_the_clustered_pk(bench: ModuleType) -> None:
    plan = _plan(bench, "mssql", "all")
    assert plan.touched == ["uq_zz_bench_ix_s1", "ix_zz_bench_ix_a", "ix_zz_bench_ix_b"]
    assert plan.skipped == [("pk_zz_bench_ix", "PK clustered (es la tabla)")]
    assert plan.disable[0] == "ALTER INDEX <uq_zz_bench_ix_s1> ON T DISABLE"
    assert plan.restore[0] == "ALTER INDEX <uq_zz_bench_ix_s1> ON T REBUILD"


def test_oracle_all_disables_constraints_and_rebuilds_pk_first(bench: ModuleType) -> None:
    plan = _plan(bench, "oracle", "all")
    assert plan.restore == [
        "ALTER TABLE T ENABLE VALIDATE CONSTRAINT <pk_zz_bench_ix>",
        "ALTER TABLE T ENABLE VALIDATE CONSTRAINT <uq_zz_bench_ix_s1>",
        "ALTER INDEX <ix_zz_bench_ix_a> REBUILD",
        "ALTER INDEX <ix_zz_bench_ix_b> REBUILD",
    ]
    assert plan.disable[2] == "ALTER INDEX <ix_zz_bench_ix_a> UNUSABLE"


def test_postgresql_all_drops_and_recreates_constraints(bench: ModuleType) -> None:
    plan = _plan(bench, "postgresql", "all")
    assert plan.disable[:2] == [
        "ALTER TABLE T DROP CONSTRAINT <pk_zz_bench_ix>",
        "ALTER TABLE T DROP CONSTRAINT <uq_zz_bench_ix_s1>",
    ]
    assert plan.restore[:3] == [
        "ALTER TABLE T ADD CONSTRAINT <pk_zz_bench_ix> PRIMARY KEY (id)",
        "ALTER TABLE T ADD CONSTRAINT <uq_zz_bench_ix_s1> UNIQUE (s1)",
        "CREATE INDEX <ix_zz_bench_ix_a> ON T (a)",
    ]


def test_innodb_uses_one_alter_and_skips_pk_and_fk_indexes(bench: ModuleType) -> None:
    plan = _plan(bench, "mysql", "all", profile="fk1")
    assert plan.disable == ["ALTER TABLE T DROP INDEX <ix_zz_bench_ix_b>"]
    assert plan.restore == ["ALTER TABLE T ADD INDEX <ix_zz_bench_ix_b> (b)"]
    assert plan.skipped == [
        ("pk_zz_bench_ix", "PK (clustered en InnoDB)"),
        ("ix_zz_bench_ix_a", "requerido por una FK"),
    ]
    unique = _plan(bench, "mariadb", "all")
    assert unique.restore == [
        "ALTER TABLE T ADD UNIQUE INDEX <uq_zz_bench_ix_s1> (s1), ADD INDEX <ix_zz_bench_ix_a> (a), "
        "ADD INDEX <ix_zz_bench_ix_b> (b)"
    ]


def test_myisam_secondary_uses_disable_keys(bench: ModuleType) -> None:
    plan = _plan(bench, "mariadb", "secondary", storage="myisam")
    assert (plan.disable, plan.restore) == (["ALTER TABLE T DISABLE KEYS"], ["ALTER TABLE T ENABLE KEYS"])


def test_unknown_dialect_is_rejected(bench: ModuleType) -> None:
    with pytest.raises(ValueError, match="no soportado"):
        _plan(bench, "hsqldb", "secondary")


@pytest.mark.parametrize(
    ("base", "mode", "expected"),
    [
        ([10.0, 10.2, 10.4], [9.0, 9.1, 9.2], True),  # −11 % sin solape
        ([10.0, 10.2, 10.4], [9.8, 9.9, 10.0], False),  # −3 %: no llega al 5 %
        ([8.0, 10.0, 12.0], [7.0, 9.0, 11.0], False),  # −10 % pero los rangos se solapan
    ],
)
def test_wins_uses_the_d3_criterion(bench: ModuleType, base: list[float], mode: list[float], expected: bool) -> None:
    stats = bench.bench_parallel.Stats.of
    assert bench.wins(stats(base), stats(mode)) is expected


def test_gain_pct_is_positive_when_faster(bench: ModuleType) -> None:
    assert bench.gain_pct(10.0, 9.0) == pytest.approx(10.0)
    assert bench.gain_pct(0.0, 1.0) == 0.0


def test_runs_against_sqlite(
    bench: ModuleType, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("UTIL_BBDD_BENCH_SQLITE_URL", raising=False)
    monkeypatch.delenv("UTIL_BBDD_TEST_SQLITE_URL", raising=False)
    # main() silencia el logger util_bbdd: se restaura para no afectar a los tests con caplog que vengan después.
    library_logger = logging.getLogger("util_bbdd")
    monkeypatch.setattr(library_logger, "level", library_logger.level)
    out_md, out_csv = tmp_path / "logs" / "bench.md", tmp_path / "logs" / "bench.csv"
    argv = ["--engines", "sqlite", "--rows", "50", "--profiles", "sec2u", "--repeat", "1", "--warmup", "0"]
    code = bench.main([*argv, "--out", str(out_md), "--csv", str(out_csv)])
    rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith("| sqlite |")]
    assert code == 0
    assert [line.split("|")[8].strip() for line in rows] == ["none", "secondary", "all"]
    assert all(line.split("|")[15].strip() == "sí" for line in rows)  # índices restaurados
    assert out_md.read_text(encoding="utf-8").splitlines()[2:] == rows
    assert len(out_csv.read_text(encoding="utf-8").splitlines()) == 4  # cabecera + 3 tandas


@pytest.mark.parametrize(
    ("dialect", "prefix", "suffix"),
    [
        ("mssql", "SELECT TOP 1 1 ", ""),
        ("oracle", "SELECT 1 ", " FETCH FIRST 1 ROWS ONLY"),
        ("postgresql", "SELECT 1 ", " LIMIT 1"),
    ],
)
def test_orphan_check_sql(bench: ModuleType, dialect: str, prefix: str, suffix: str) -> None:
    assert bench.orphan_check_sql(dialect, "c", "p", "a", "id") == (
        f"{prefix}FROM c c WHERE c.a IS NOT NULL AND NOT EXISTS (SELECT 1 FROM p p WHERE p.id = c.a){suffix}"
    )


def test_fk_validation_runs_against_sqlite(
    bench: ModuleType, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("UTIL_BBDD_BENCH_SQLITE_URL", raising=False)
    monkeypatch.delenv("UTIL_BBDD_TEST_SQLITE_URL", raising=False)
    library_logger = logging.getLogger("util_bbdd")
    monkeypatch.setattr(library_logger, "level", library_logger.level)
    code = bench.main(["--engines", "sqlite", "--fk-validation", "--rows", "50", "--repeat", "1"])
    rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith("| sqlite |")]
    assert code == 0
    assert [line.split("|")[3].strip() for line in rows] == ["comprobar huérfanos (2 FK, NOT EXISTS)"]
