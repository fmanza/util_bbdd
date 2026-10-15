"""EngineReadinessAdvisor.engine_report: el resultado de report_once guardado por engine (hojas de bulk y dump)."""

from __future__ import annotations

import logging
import threading
import time

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import OperationalError

from util_bbdd.connection import EngineReadinessReport
from util_bbdd.connection.performance_advisor import EngineReadinessAdvisor

_LOGGER = "util_bbdd.connection.performance_advisor"
_HEADER = "ENGINE READINESS REPORT"
_DUMMY_PASSWORD = "no-es-una-clave"  # valor ficticio para comprobar que no se filtra


def _engine(tmp_path: Path, name: str = "db.sqlite") -> Engine:
    return create_engine(f"sqlite:///{tmp_path / name}")


def test_reuses_the_report_once_result_without_a_new_connection(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    checkouts: list[object] = []
    event.listen(engine, "checkout", lambda *args: checkouts.append(args))

    assert EngineReadinessAdvisor().report_once(engine) is True
    report = EngineReadinessAdvisor().engine_report(engine)

    assert len(checkouts) == 1
    assert isinstance(report, EngineReadinessReport)
    assert (report.db_type, report.supported, report.dynamic, report.error) == ("sqlite", True, True, None)
    assert {f.param for f in report.findings} >= {"journal_mode", "timeout"}
    assert report.checked_at.tzinfo is not None
    engine.dispose()


def test_verifies_and_logs_once_an_engine_not_yet_verified(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    engine = _engine(tmp_path)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        first = EngineReadinessAdvisor().engine_report(engine)
        second = EngineReadinessAdvisor().engine_report(engine)

    assert first is second
    assert sum(1 for r in caplog.records if _HEADER in r.getMessage()) == 1
    assert EngineReadinessAdvisor().report_once(engine) is False
    engine.dispose()


def test_without_connection_keeps_static_checks_and_only_the_error_type(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with patch.object(Engine, "connect", side_effect=OperationalError("SELECT 1", {}, Exception("u:secreto@h"))):
        report = EngineReadinessAdvisor().engine_report(engine)

    assert report.dynamic is False
    assert report.error == "Sin conexión para los checks dinámicos (OperationalError)"
    assert "secreto" not in repr(report)
    assert report.findings
    engine.dispose()


def test_waits_for_a_verification_in_progress_in_another_thread(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    started, release = threading.Event(), threading.Event()
    original = EngineReadinessAdvisor._verify_and_store

    def _slow(self: EngineReadinessAdvisor, target: Engine) -> None:
        started.set()
        release.wait(5)
        original(self, target)

    with patch.object(EngineReadinessAdvisor, "_verify_and_store", _slow):
        worker = threading.Thread(target=EngineReadinessAdvisor().report_once, args=(engine,))
        worker.start()
        started.wait(5)
        threading.Timer(0.1, release.set).start()
        report = EngineReadinessAdvisor().engine_report(engine, timeout=5)
        worker.join(5)

    assert report.error is None
    assert report.dynamic is True
    engine.dispose()


def test_timeout_returns_a_report_with_the_reason(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    release = threading.Event()

    def _blocked(self: EngineReadinessAdvisor, target: Engine) -> None:
        release.wait(5)

    with patch.object(EngineReadinessAdvisor, "_verify_and_store", _blocked):
        worker = threading.Thread(target=EngineReadinessAdvisor().report_once, args=(engine,))
        worker.start()
        deadline = time.monotonic() + 5
        while engine not in EngineReadinessAdvisor._report_done and time.monotonic() < deadline:
            time.sleep(0.001)
        report = EngineReadinessAdvisor().engine_report(engine, timeout=0.05)
        release.set()
        worker.join(5)

    assert report.findings == ()
    assert report.error == "La verificación del motor no está disponible (no terminó o falló)"
    engine.dispose()


def test_describe_engine_omits_credentials(tmp_path: Path) -> None:
    fake = SimpleNamespace(  # engine falso: no requiere el driver de PostgreSQL
        url=URL.create("postgresql", username="usr", password=_DUMMY_PASSWORD, host="db", port=5432, database="app"),
        dialect=SimpleNamespace(name="postgresql"),
    )

    assert EngineReadinessAdvisor.describe_engine(fake) == "postgresql · db:5432/app"  # type: ignore[arg-type]
    assert EngineReadinessAdvisor.describe_engine(_engine(tmp_path)) == f"sqlite · {tmp_path / 'db.sqlite'}"
