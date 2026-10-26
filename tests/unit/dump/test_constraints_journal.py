"""U-V3 (G31 de util_bbdd_web): diario de constraints y ``restore_constraints`` tras un volcado interrumpido."""

from __future__ import annotations

import json

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy.exc import SQLAlchemyError

from util_bbdd._core.exceptions import DumpConstraintError
from util_bbdd.dump import ConstraintManager, DumpConfig, DumpOrchestrator, restore_constraints
from util_bbdd.dump._constraints import JOURNAL_FILENAME

pytestmark = pytest.mark.unit


def _engine(dialect: str, executed: list[str], *, fail: str | None = None) -> MagicMock:
    """Engine simulado que registra cada sentencia; ``fail`` hace fallar las que lo contienen."""
    engine = MagicMock()
    engine.dialect.name = dialect
    engine.dialect.identifier_preparer.quote.side_effect = lambda name: name
    engine.dialect.normalize_name.side_effect = lambda name: name
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    def execute(statement: Any, *_args: Any) -> MagicMock:
        sql = str(statement)
        executed.append(sql)
        if fail is not None and fail in sql:
            raise SQLAlchemyError(f"fallo en {sql}")
        return MagicMock()

    conn.execute.side_effect = execute
    engine.connect.return_value = conn
    engine.begin.return_value = conn
    return engine


def _oracle_snapshot() -> Any:
    named = lambda *names: [SimpleNamespace(name=n) for n in names]  # noqa: E731
    return SimpleNamespace(
        foreign_keys=lambda table: named(f"fk_{table}"),
        checks=lambda table: named("SYS_C001", f"ck_{table}"),
        uniques=lambda table: named(),
    )


def _journal(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("dialect", ["mssql", "postgresql"])
def test_journal_is_written_before_disabling_and_restore_reenables(tmp_path: Path, dialect: str) -> None:
    journal = tmp_path / "out" / JOURNAL_FILENAME
    executed: list[str] = []
    engine = _engine(dialect, executed)
    seen_journal: list[bool] = []
    original = engine.connect.return_value.execute.side_effect

    def spy(statement: Any, *args: Any) -> Any:
        seen_journal.append(journal.exists())
        return original(statement, *args)

    engine.connect.return_value.execute.side_effect = spy

    ConstraintManager(engine, "dbo", journal_path=journal).disable_all(["padre", "hija"])  # y el proceso «muere»

    assert seen_journal and all(seen_journal)  # el diario existía antes de la primera sentencia
    data = _journal(journal)
    assert (data["dialect"], data["schema"], data["tables"]) == (dialect, "dbo", ["padre", "hija"])

    executed.clear()
    with patch.object(ConstraintManager, "_snapshot", return_value=None):
        results = restore_constraints(_engine(dialect, executed), journal)

    keyword = "CHECK CONSTRAINT ALL" if dialect == "mssql" else "ENABLE TRIGGER ALL"
    assert [s for s in executed if keyword in s] == [s for s in executed if "padre" in s or "hija" in s]
    assert sum(keyword in s for s in executed) == 2
    assert all(r.status == "enabled" for r in results)
    assert not journal.exists()
    assert restore_constraints(_engine(dialect, []), journal) == []  # idempotente: ya restaurado


def test_oracle_journal_lists_each_constraint(tmp_path: Path) -> None:
    journal = tmp_path / JOURNAL_FILENAME
    executed: list[str] = []
    with patch.object(ConstraintManager, "_snapshot", return_value=_oracle_snapshot()):
        ConstraintManager(_engine("oracle", executed), journal_path=journal).disable_all(["padre"])

    assert _journal(journal)["constraints"] == [["padre", "fk_padre"], ["padre", "ck_padre"]]
    assert [s for s in executed if "DISABLE" in s] == [
        "ALTER TABLE padre DISABLE CONSTRAINT fk_padre",
        "ALTER TABLE padre DISABLE CONSTRAINT ck_padre",
    ]

    executed.clear()
    results = restore_constraints(_engine("oracle", executed), str(journal))

    assert executed == [
        "ALTER TABLE padre ENABLE VALIDATE CONSTRAINT fk_padre",
        "ALTER TABLE padre ENABLE VALIDATE CONSTRAINT ck_padre",
    ]
    assert [(r.constraint_name, r.status) for r in results] == [("fk_padre", "enabled"), ("ck_padre", "enabled")]
    assert not journal.exists()


def test_normal_exit_removes_the_journal(tmp_path: Path) -> None:
    journal = tmp_path / JOURNAL_FILENAME
    with ConstraintManager(_engine("mssql", []), journal_path=journal) as manager:
        manager.disable_all(["t"])
        assert journal.exists()
    assert not journal.exists()
    assert [r.status for r in manager.constraint_results] == ["enabled"]


def test_a_failed_reactivation_keeps_the_journal(tmp_path: Path) -> None:
    journal = tmp_path / JOURNAL_FILENAME
    engine = _engine("mssql", [], fail="WITH CHECK")
    with ConstraintManager(engine, journal_path=journal) as manager:
        manager.disable_all(["t"])

    assert [r.status for r in manager.constraint_results] == ["failed"]
    assert journal.exists()  # para reintentar con restore_constraints tras corregir los datos


def test_session_level_dialects_have_no_journal(tmp_path: Path) -> None:
    journal = tmp_path / JOURNAL_FILENAME
    engine = _engine("mysql", [])
    with patch("util_bbdd.dump._constraints.event"):
        ConstraintManager(engine, journal_path=journal, validate_fks_after=False).disable_all(["t"])
    assert not journal.exists()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("no es json", "JSON no válido"),
        ('{"format": "otro"}', "format"),
        ('{"format": "util_bbdd.dump_constraints_journal", "format_version": 9}', "format_version"),
        (
            '{"format": "util_bbdd.dump_constraints_journal", "format_version": 1, "dialect": "mysql"}',
            "sin diario",
        ),
        (
            '{"format": "util_bbdd.dump_constraints_journal", "format_version": 1, "dialect": "oracle", '
            '"constraints": [["t"]]}',
            "constraints",
        ),
    ],
)
def test_invalid_journal(tmp_path: Path, content: str, message: str) -> None:
    journal = tmp_path / JOURNAL_FILENAME
    journal.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        restore_constraints(_engine("oracle", []), journal)
    assert journal.exists()


def test_journal_of_another_engine(tmp_path: Path) -> None:
    journal = tmp_path / JOURNAL_FILENAME
    ConstraintManager(_engine("mssql", []), journal_path=journal).disable_all(["t"])
    with pytest.raises(ValueError, match="es de mssql"):
        restore_constraints(_engine("postgresql", []), journal)


def test_unwritable_journal_stops_before_disabling(tmp_path: Path) -> None:
    blocker = tmp_path / "fichero"
    blocker.write_text("x", encoding="utf-8")
    executed: list[str] = []
    with pytest.raises(DumpConstraintError, match="diario"):
        ConstraintManager(_engine("mssql", executed), journal_path=blocker / JOURNAL_FILENAME).disable_all(["t"])
    assert executed == []


def _orchestrator(dialect: str, output_dir: Path) -> DumpOrchestrator:
    orchestrator = DumpOrchestrator.__new__(DumpOrchestrator)
    engine = _engine(dialect, [])
    orchestrator._cfg = DumpConfig(engine, engine, output_dir=output_dir, truncate_target=True)
    return orchestrator


def test_dump_refuses_to_start_with_a_pending_journal(tmp_path: Path) -> None:
    orchestrator = _orchestrator("oracle", tmp_path)
    assert orchestrator._constraints_journal_path() == tmp_path / JOURNAL_FILENAME
    (tmp_path / JOURNAL_FILENAME).write_text("{}", encoding="utf-8")
    with pytest.raises(DumpConstraintError, match="restore_constraints"):
        orchestrator._constraints_journal_path()


def test_dump_without_journal_for_other_engines(tmp_path: Path) -> None:
    assert _orchestrator("sqlite", tmp_path)._constraints_journal_path() is None
    assert _orchestrator("mariadb", tmp_path)._constraints_journal_path() is None
