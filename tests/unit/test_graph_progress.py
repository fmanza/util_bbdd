"""Progreso y cancelación de ``generate_all_tables_graphs_ext`` (util_bbdd_web G1, 4.1.0)."""

from __future__ import annotations

import sqlite3

from pathlib import Path

import pytest

pytest.importorskip("graphviz")

from util_bbdd import SyncDatabaseManager  # noqa: E402
from util_bbdd.analysis.graphviz_ext import GraphvizRelationshipGraphExt  # noqa: E402
from util_bbdd.exceptions import OperationCancelledError  # noqa: E402
from util_bbdd.progress import CancellationToken, ProgressEvent  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    path = tmp_path / "demo.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE a (id INTEGER PRIMARY KEY);
        CREATE TABLE b (id INTEGER PRIMARY KEY, a_id INTEGER REFERENCES a(id));
        CREATE TABLE c (id INTEGER PRIMARY KEY, b_id INTEGER REFERENCES b(id));
        """
    )
    con.close()
    return path


def test_events_per_table(sqlite_db: Path, tmp_path: Path) -> None:
    events: list[ProgressEvent] = []
    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        results = GraphvizRelationshipGraphExt(manager).generate_all_tables_graphs_ext(
            tmp_path / "out", format="svg", on_progress=events.append
        )

    assert [(e.operation, e.phase, e.current, e.total) for e in events] == [
        ("graph", "tables", step, 3) for step in range(4)
    ]
    assert {e.message for e in events if e.current} == set(results) == {"a", "b", "c"}


def test_cancel_stops_between_tables_and_is_not_stored_as_a_table_error(sqlite_db: Path, tmp_path: Path) -> None:
    token = CancellationToken()

    def cancel_after_first(event: ProgressEvent) -> None:
        if event.current == 1:
            token.cancel()

    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        generator = GraphvizRelationshipGraphExt(manager)
        with pytest.raises(OperationCancelledError) as raised:
            generator.generate_all_tables_graphs_ext(
                tmp_path / "out", format="svg", on_progress=cancel_after_first, cancel_token=token
            )

    assert (raised.value.cancelled_operation, raised.value.phase) == ("graph", "tables")
    assert len(list((tmp_path / "out").glob("*.svg"))) >= 1  # lo ya escrito queda
