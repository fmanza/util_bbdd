"""Unit tests para EngineReadinessAdvisor.report_once: una verificación por engine en el proceso."""

from __future__ import annotations

import gc
import logging
import threading
import weakref

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from util_bbdd.connection.performance_advisor import EngineReadinessAdvisor

_LOGGER = "util_bbdd.connection.performance_advisor"
_HEADER = "ENGINE READINESS REPORT"
_DUMMY_PASSWORD = "no-es-una-clave"  # valor ficticio para comprobar que no se filtra


def _file_engine(tmp_path: Path, name: str = "db.sqlite", **kwargs: object) -> Engine:
    return create_engine(f"sqlite:///{tmp_path / name}", **kwargs)


def _reports(caplog: pytest.LogCaptureFixture) -> int:
    return sum(1 for r in caplog.records if _HEADER in r.getMessage())


class TestReportOnce:
    def test_first_call_true_then_false(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path)
        advisor = EngineReadinessAdvisor()
        assert advisor.report_once(engine) is True
        assert advisor.report_once(engine) is False
        # Otra instancia del advisor comparte el registro
        assert EngineReadinessAdvisor().report_once(engine) is False
        engine.dispose()

    def test_single_report_in_log(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        engine = _file_engine(tmp_path)
        with caplog.at_level(logging.INFO, logger=_LOGGER):
            for _ in range(5):
                EngineReadinessAdvisor().report_once(engine)
        assert _reports(caplog) == 1
        engine.dispose()

    def test_distinct_engines_reported_separately(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        # Mismo fichero, dos engines: la clave es el objeto Engine, no la URL
        engine_a = _file_engine(tmp_path)
        engine_b = _file_engine(tmp_path)
        with caplog.at_level(logging.INFO, logger=_LOGGER):
            assert EngineReadinessAdvisor().report_once(engine_a) is True
            assert EngineReadinessAdvisor().report_once(engine_b) is True
        assert _reports(caplog) == 2
        engine_a.dispose()
        engine_b.dispose()

    def test_second_call_no_checkout_no_log(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        engine = _file_engine(tmp_path)
        checkouts: list[object] = []
        event.listen(engine, "checkout", lambda *args: checkouts.append(args))

        EngineReadinessAdvisor().report_once(engine)
        assert len(checkouts) == 1

        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            assert EngineReadinessAdvisor().report_once(engine) is False
        assert len(checkouts) == 1
        assert caplog.records == []
        engine.dispose()

    def test_dispose_does_not_trigger_new_report(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path)
        assert EngineReadinessAdvisor().report_once(engine) is True
        engine.dispose()
        assert EngineReadinessAdvisor().report_once(engine) is False

    def test_released_engine_leaves_registry(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path)
        EngineReadinessAdvisor().report_once(engine)
        assert engine in EngineReadinessAdvisor._reported_engines
        engine_ref = weakref.ref(engine)
        engine.dispose()
        del engine
        gc.collect()
        # El registro no retiene el engine: sin otras referencias, se libera
        assert engine_ref() is None

    def test_concurrent_threads_single_report(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        engine = _file_engine(tmp_path)
        n_threads = 8
        barrier = threading.Barrier(n_threads)

        def _worker() -> bool:
            barrier.wait()
            return EngineReadinessAdvisor().report_once(engine)

        with caplog.at_level(logging.INFO, logger=_LOGGER):
            with ThreadPoolExecutor(max_workers=n_threads) as pool:
                results = list(pool.map(lambda _: _worker(), range(n_threads)))

        assert results.count(True) == 1
        assert _reports(caplog) == 1
        engine.dispose()

    def test_connection_failure_falls_back_to_static(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path)
        with (
            patch.object(Engine, "connect", side_effect=OperationalError("SELECT 1", {}, Exception("down"))),
            patch.object(EngineReadinessAdvisor, "report") as report,
        ):
            assert EngineReadinessAdvisor().report_once(engine) is True

        report.assert_called_once()
        assert "connection" not in report.call_args.kwargs
        engine.dispose()

    def test_close_failure_after_report_does_not_report_twice(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path)
        conn_cm = MagicMock()
        conn_cm.__exit__.side_effect = OperationalError("close", {}, Exception("reset"))
        with (
            patch.object(Engine, "connect", return_value=conn_cm),
            patch.object(EngineReadinessAdvisor, "report") as report,
        ):
            assert EngineReadinessAdvisor().report_once(engine) is True

        report.assert_called_once()
        assert "connection" in report.call_args.kwargs
        engine.dispose()

    def test_report_failure_never_raises(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path)
        with patch.object(EngineReadinessAdvisor, "report", side_effect=RuntimeError("boom")):
            assert EngineReadinessAdvisor().report_once(engine) is True
        engine.dispose()

    def test_explicit_report_not_limited(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        engine = _file_engine(tmp_path)
        EngineReadinessAdvisor().report_once(engine)
        caplog.clear()
        with caplog.at_level(logging.INFO, logger=_LOGGER):
            EngineReadinessAdvisor().report("sqlite", {"database": str(tmp_path / "db.sqlite")})
        assert _reports(caplog) == 1
        engine.dispose()


class TestConnParamsFromEngine:
    def test_sqlite_file_queue_pool(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path, pool_size=3, max_overflow=7, pool_timeout=12)
        params = EngineReadinessAdvisor._conn_params_from_engine(engine)
        assert params == {
            "database": str(tmp_path / "db.sqlite"),
            "pool_size": 3,
            "max_overflow": 7,
            "pool_timeout": 12,
        }
        engine.dispose()

    def test_pool_without_size_or_private_attrs(self, tmp_path: Path) -> None:
        engine = _file_engine(tmp_path, poolclass=NullPool)
        params = EngineReadinessAdvisor._conn_params_from_engine(engine)
        assert params == {"database": str(tmp_path / "db.sqlite")}
        engine.dispose()

    @pytest.mark.parametrize(
        ("url", "driver"),
        [
            ("mssql+pyodbc://u:p@srv:1433/ventas", "pyodbc"),
            ("mssql+pymssql://u:p@srv:1433/ventas", "pymssql"),
            ("mssql://u:p@srv:1433/ventas", "pymssql"),
        ],
    )
    def test_sqlserver_host_port_and_driver(self, url: str, driver: str) -> None:
        # Engine falso: no requiere pyodbc/pymssql instalados
        fake = SimpleNamespace(url=make_url(url), pool=SimpleNamespace(), dialect=SimpleNamespace(name="mssql"))
        params = EngineReadinessAdvisor._conn_params_from_engine(fake)  # type: ignore[arg-type]
        assert params == {"host": "srv", "port": 1433, "database": "ventas", "sql_server_driver": driver}

    def test_credentials_not_included(self) -> None:
        fake = SimpleNamespace(
            url=URL.create(
                "postgresql", username="usr", password=_DUMMY_PASSWORD, host="db", port=5432, database="app"
            ),
            pool=SimpleNamespace(),
            dialect=SimpleNamespace(name="postgresql"),
        )
        params = EngineReadinessAdvisor._conn_params_from_engine(fake)  # type: ignore[arg-type]
        assert _DUMMY_PASSWORD not in repr(params)
        assert "usr" not in repr(params)
