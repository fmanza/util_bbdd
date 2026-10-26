"""Progreso y cancelación cooperativa de ``DatabaseDocumentation.generate()`` (util_bbdd_web G1, 4.1.0)."""

from __future__ import annotations

import sqlite3

from pathlib import Path

import pytest

from util_bbdd import SyncDatabaseManager
from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.exceptions import OperationCancelledError
from util_bbdd.progress import CancellationToken, ProgressEvent

pytestmark = pytest.mark.unit

IMPRIMIR = {"tablas": {"imprimir_tablas": True, "columnas": True}}


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    path = tmp_path / "demo.db"
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE a (id INTEGER PRIMARY KEY); CREATE TABLE b (id INTEGER PRIMARY KEY);")
    con.close()
    return path


def _documentation(
    manager: SyncDatabaseManager, tmp_path: Path, events: list[ProgressEvent], token: CancellationToken | None = None
) -> DatabaseDocumentation:
    return DatabaseDocumentation(
        manager,
        directorio_salida=tmp_path / "out",
        fichero_salida=Path("demo"),
        imprimir=IMPRIMIR,
        formatos=["word", "excel", "html"],
        on_progress=events.append,
        cancel_token=token,
    )


def test_events_cover_metadata_and_every_table_of_every_format(sqlite_db: Path, tmp_path: Path) -> None:
    events: list[ProgressEvent] = []
    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        _documentation(manager, tmp_path, events).generate()

    assert {event.operation for event in events} == {"documentation"}
    assert [(e.phase, e.current, e.total) for e in events] == [
        ("metadata", 0, 1),
        ("metadata", 1, 1),
        *[(fmt, step, 2) for fmt in ("word", "excel", "html") for step in (0, 1, 2)],
    ]
    assert [e.message for e in events if e.phase == "word" and e.current] == ["a", "b"]


def test_cancel_between_tables_stops_with_the_phase(sqlite_db: Path, tmp_path: Path) -> None:
    token = CancellationToken()
    events: list[ProgressEvent] = []

    def cancel_after_first_word_table(event: ProgressEvent) -> None:
        events.append(event)
        if (event.phase, event.current) == ("word", 1):
            token.cancel()

    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        documentation = DatabaseDocumentation(
            manager,
            directorio_salida=tmp_path / "out",
            fichero_salida=Path("demo"),
            imprimir=IMPRIMIR,
            formatos=["word", "excel"],
            on_progress=cancel_after_first_word_table,
            cancel_token=token,
        )
        with pytest.raises(OperationCancelledError) as raised:
            documentation.generate()

    assert (raised.value.cancelled_operation, raised.value.phase) == ("documentation", "word")
    assert not any(event.phase == "excel" for event in events)
    assert not list((tmp_path / "out").rglob("*.xlsx"))


def test_cancelled_before_starting_reads_nothing(sqlite_db: Path, tmp_path: Path) -> None:
    token = CancellationToken()
    token.cancel()
    events: list[ProgressEvent] = []
    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        with pytest.raises(OperationCancelledError, match="documentation"):
            _documentation(manager, tmp_path, events, token).generate()

    assert events == []


def test_a_failing_callback_does_not_break_the_documentation(sqlite_db: Path, tmp_path: Path) -> None:
    def broken(event: ProgressEvent) -> None:
        raise RuntimeError("receptor roto")

    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager, directorio_salida=tmp_path / "out", imprimir=IMPRIMIR, formatos=["excel"], on_progress=broken
        ).generate()

    assert result.outputs["excel"].is_file()
