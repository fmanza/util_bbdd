"""``DumpConfig(parallel_pk_ranges="auto")`` (v3.0.0): los rangos de cada tabla los decide ``ParallelPlanner``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from util_bbdd.bulk import ParallelLoadResult
from util_bbdd.dump import DumpConfig, DumpOrchestrator


def _engine(dialect: str, pool_size: object = "x") -> MagicMock:
    engine = MagicMock()
    engine.dialect.name = dialect
    engine.dialect.identifier_preparer.quote.side_effect = lambda n: n
    engine.pool.size = pool_size  # "x": capacidad no determinable
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    engine.connect.return_value = conn
    engine.begin.return_value = conn
    return engine


def _orch(target: str = "mssql", **cfg: object) -> DumpOrchestrator:
    orch = DumpOrchestrator.__new__(DumpOrchestrator)
    orch._cfg = DumpConfig(
        source_engine=_engine("postgresql"),
        target_engine=_engine(target),
        parallel_pk_ranges="auto",
        **cfg,  # type: ignore[arg-type]
    )
    orch._reset_audit_tracking()
    return orch


class TestConfig:
    def test_auto_is_accepted(self) -> None:
        assert _orch()._cfg.parallel_pk_ranges == "auto"

    @pytest.mark.parametrize("value", ["4", "fast", 2.0, True])
    def test_other_values_are_rejected(self, value: object) -> None:
        with pytest.raises(ValueError, match="parallel_pk_ranges debe ser un entero o 'auto'"):
            DumpConfig(source_engine=MagicMock(), target_engine=MagicMock(), parallel_pk_ranges=value)  # type: ignore[arg-type]

    def test_auto_reads_the_primary_keys(self) -> None:
        assert _orch()._pk_ranges_requested() is True


class TestRangeCount:
    def test_ceiling_is_the_measured_default(self) -> None:
        orch = _orch()
        assert orch._resolve_range_count("auto", 1) == 4
        assert orch._auto_pk_ranges is True

    def test_ceiling_shares_the_pool_between_tables(self) -> None:
        orch = _orch()
        with patch.object(DumpOrchestrator, "_pool_capacity", return_value=6):
            assert orch._resolve_range_count("auto", 3) == 2

    def test_sqlite_target_is_one(self) -> None:
        assert _orch("sqlite")._resolve_range_count("auto", 1) == 1

    def test_integer_request_is_not_auto(self) -> None:
        orch = _orch()
        orch._resolve_range_count(4, 1)
        assert orch._auto_pk_ranges is False


class TestLoadInPkRanges:
    def _run(
        self, orch: DumpOrchestrator, lo: int, hi: int, rows_hint: int | None = None
    ) -> tuple[MagicMock, MagicMock]:
        orch._resolve_range_count("auto", 1)
        orch._cfg.source_engine.connect.return_value.execute.return_value.one.return_value = (lo, hi)
        crud = MagicMock()
        crud.rows_rejected = 0
        with patch("util_bbdd.dump.orchestrator.ParallelBulkLoader") as loader_cls:
            loader_cls.return_value.load.return_value = ParallelLoadResult()
            orch._load_in_pk_ranges("t", ["id"], {"id": "id"}, "id", "t", 4, crud=crud, rows_hint=rows_hint)
        return loader_cls, crud

    def test_large_sql_server_table_is_split(self) -> None:
        loader_cls, crud = self._run(_orch("mssql"), 1, 4_000_000)
        assert loader_cls.call_args.kwargs["parallel"].max_workers == 4
        crud.bulk_insert_from_chunks.assert_not_called()

    def test_row_count_below_the_threshold_wins_over_a_sparse_range(self) -> None:
        """Deuda D4: PK con huecos (rango de 4M, 1.000 filas): con el COUNT(*) del origen, la tabla va entera."""
        loader_cls, crud = self._run(_orch("mssql"), 1, 4_000_000, rows_hint=1_000)
        loader_cls.assert_not_called()
        crud.bulk_insert_from_chunks.assert_called_once()

    @pytest.mark.parametrize("rows_hint", [None, -1])
    def test_without_row_count_the_range_is_the_estimate(self, rows_hint: int | None) -> None:
        loader_cls, _ = self._run(_orch("mssql"), 1, 4_000_000, rows_hint=rows_hint)
        assert loader_cls.call_args.kwargs["parallel"].max_workers == 4

    def test_row_count_never_raises_the_range_estimate(self) -> None:
        loader_cls, crud = self._run(_orch("mssql"), 1, 1_000, rows_hint=10_000_000)
        loader_cls.assert_not_called()
        crud.bulk_insert_from_chunks.assert_called_once()

    def test_small_table_is_loaded_whole(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("INFO", logger="util_bbdd.dump.orchestrator"):
            loader_cls, crud = self._run(_orch("mssql"), 1, 1_000)
        loader_cls.assert_not_called()
        crud.bulk_insert_from_chunks.assert_called_once()
        assert "menor volumen medido" in caplog.text

    @pytest.mark.parametrize("target", ["mysql", "postgresql", "oracle"])
    def test_targets_that_do_not_gain_are_loaded_whole(self, target: str) -> None:
        loader_cls, crud = self._run(_orch(target), 1, 10_000_000)
        loader_cls.assert_not_called()
        crud.bulk_insert_from_chunks.assert_called_once()


@pytest.mark.parametrize("target", ["mysql", "mariadb", "postgresql", "oracle", "hsqldb"])
def test_targets_without_gain_skip_the_ranges_once(target: str, caplog: pytest.LogCaptureFixture) -> None:
    """AUDIT_CODE: sin regla que gane, ni MIN/MAX por tabla: 1 rango para todo el volcado y un INFO."""
    with caplog.at_level("INFO", logger="util_bbdd.dump.orchestrator"):
        assert _orch(target)._resolve_range_count("auto", 1) == 1
    assert caplog.text.count("sin rangos de PK") == 1
