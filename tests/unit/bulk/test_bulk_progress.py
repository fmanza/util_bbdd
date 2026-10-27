"""U-B4 (G1 de util_bbdd_web): progreso por lote y cancelación cooperativa entre lotes en ``BulkCrud``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution import parallel_planner
from util_bbdd.bulk.options import AuditOptions, BatchOptions, ParallelOptions
from util_bbdd.exceptions import OperationCancelledError
from util_bbdd.progress import CancellationToken, ProgressEvent

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}", connect_args={"timeout": 30})
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, v TEXT)"))
    yield engine
    engine.dispose()


@pytest.fixture
def several_writers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deja que el planificador use varios hilos con SQLite (como ``test_crud_parallel``)."""
    monkeypatch.setattr(parallel_planner, "SINGLE_WRITER_DIALECTS", frozenset())


def _items(ids: range | list[int], value: str = "x") -> pd.DataFrame:
    return pd.DataFrame({"id": list(ids), "v": [f"{value}{i}" for i in ids]})


def _crud(engine: Engine, **extra: Any) -> BulkCrud:
    every = extra.pop("every", None)
    return BulkCrud(
        engine,
        batch=BatchOptions(chunk_size=2, commit_every_n_chunks=every),
        audit=AuditOptions(warn_if_disabled=False),
        **extra,
    )


def _ids(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        return list(conn.execute(text("SELECT id FROM items ORDER BY id")).scalars())


def _summary(events: list[ProgressEvent]) -> list[tuple[int, int | None]]:
    assert {(e.operation, e.phase, e.message) for e in events} <= {("bulk", "rows", "items")}
    return [(e.current, e.total) for e in events]


def _cancel_at(token: CancellationToken, current: int) -> Any:
    def on_progress(event: ProgressEvent) -> None:
        if event.current == current:
            token.cancel()

    return on_progress


# ----------------------------------------------------------------------------------------------------------- eventos


@pytest.mark.parametrize("method", ["bulk_insert_from_df", "bulk_update_from_df", "bulk_delete_from_df"])
def test_one_event_per_batch(engine: Engine, method: str) -> None:
    if method != "bulk_insert_from_df":
        _crud(engine).bulk_insert_from_df(_items(range(1, 6)), "items", generar_sql=False)
    events: list[ProgressEvent] = []

    getattr(_crud(engine), method)(_items(range(1, 6), "u"), "items", generar_sql=False, on_progress=events.append)

    assert _summary(events) == [(0, 5), (2, 5), (4, 5), (5, 5)]


def test_chunks_have_no_total(engine: Engine) -> None:
    events: list[ProgressEvent] = []
    crud = _crud(engine)

    crud.bulk_insert_from_chunks([_items(range(1, 4)), _items(range(4, 6))], "items", on_progress=events.append)
    assert _summary(events) == [(0, None), (2, None), (3, None), (5, None)]

    events.clear()
    crud.bulk_update_from_chunks([_items([1, 2, 3], "u")], "items", on_progress=events.append)
    crud.bulk_delete_from_chunks([_items([4, 5])], "items", on_progress=events.append)
    assert _summary(events) == [(0, None), (2, None), (3, None), (0, None), (2, None)]


def test_sql_generation_has_no_events_and_ignores_the_token(engine: Engine, tmp_path: Path) -> None:
    token = CancellationToken()
    token.cancel()
    events: list[ProgressEvent] = []

    _crud(engine).bulk_insert_from_df(
        _items(range(1, 4)), "items", dry_run=True, path_sql=tmp_path, on_progress=events.append, cancel_token=token
    )

    assert events == []
    assert len(list(tmp_path.glob("*.sql"))) == 1


def test_failing_callback_does_not_stop_the_load(engine: Engine) -> None:
    def broken(_event: ProgressEvent) -> None:
        raise RuntimeError("callback roto")

    _crud(engine).bulk_insert_from_df(_items(range(1, 6)), "items", generar_sql=False, on_progress=broken)

    assert _ids(engine) == [1, 2, 3, 4, 5]


# ------------------------------------------------------------------------------------------------------- cancelación


def test_cancel_before_start_touches_nothing(engine: Engine) -> None:
    token = CancellationToken()
    token.cancel()
    events: list[ProgressEvent] = []

    with pytest.raises(OperationCancelledError):
        _crud(engine).bulk_insert_from_df(
            _items(range(1, 6)), "items", generar_sql=False, on_progress=events.append, cancel_token=token
        )

    assert events == []
    assert _ids(engine) == []


@pytest.mark.parametrize("method", ["bulk_insert_from_df", "bulk_delete_from_df"])
def test_cancel_in_one_transaction_undoes_the_whole_operation(engine: Engine, method: str) -> None:
    if method == "bulk_delete_from_df":
        _crud(engine).bulk_insert_from_df(_items(range(1, 6)), "items", generar_sql=False)
    before = _ids(engine)
    token = CancellationToken()
    crud = _crud(engine)

    with pytest.raises(OperationCancelledError) as caught:
        getattr(crud, method)(
            _items(range(1, 6)), "items", generar_sql=False, on_progress=_cancel_at(token, 2), cancel_token=token
        )

    assert (caught.value.cancelled_operation, caught.value.phase) == ("bulk", "rows")
    assert not any("falló el lote" in note for note in getattr(caught.value, "__notes__", ()))
    assert _ids(engine) == before  # el primer lote, ya ejecutado, se deshace con la transacción
    assert (crud.rows_committed, crud.last_operation_rows_committed) == (0, 0)


def test_cancel_with_periodic_commits_keeps_the_committed_batches(engine: Engine) -> None:
    token = CancellationToken()
    crud = _crud(engine, every=1)

    with pytest.raises(OperationCancelledError):
        crud.bulk_insert_from_df(
            _items(range(1, 6)), "items", generar_sql=False, on_progress=_cancel_at(token, 4), cancel_token=token
        )

    assert _ids(engine) == [1, 2, 3, 4]
    assert crud.last_operation_rows_committed == 4  # se reanuda con df.iloc[4:]


def test_cancel_inside_a_session_undoes_the_session(engine: Engine) -> None:
    token = CancellationToken()
    crud = _crud(engine)

    with pytest.raises(OperationCancelledError), crud.bulk_session():
        crud.bulk_insert_from_df(_items([10, 11]), "items", generar_sql=False)
        crud.bulk_insert_from_df(
            _items(range(1, 6)), "items", generar_sql=False, on_progress=_cancel_at(token, 2), cancel_token=token
        )

    assert _ids(engine) == []


def test_cancel_a_stream(engine: Engine) -> None:
    token = CancellationToken()
    crud = _crud(engine)

    with pytest.raises(OperationCancelledError):
        crud.bulk_insert_from_chunks(
            [_items(range(1, 4)), _items(range(4, 7))], "items", on_progress=_cancel_at(token, 3), cancel_token=token
        )

    assert _ids(engine) == []


# --------------------------------------------------------------------------------------------------------- paralelo


@pytest.mark.usefixtures("several_writers")
def test_parallel_events_add_up_every_partition(engine: Engine) -> None:
    events: list[ProgressEvent] = []
    crud = _crud(engine, parallel=ParallelOptions(max_workers=2))

    crud.bulk_insert_from_df(_items(range(1, 11)), "items", generar_sql=False, on_progress=events.append)

    assert crud.last_parallel_result is not None
    currents = [e.current for e in events]
    assert currents[0] == 0 and currents[-1] == 10
    assert currents == sorted(currents)
    assert {e.total for e in events} == {10}


@pytest.mark.usefixtures("several_writers")
def test_parallel_cancel_raises_and_keeps_the_confirmed_partitions(engine: Engine) -> None:
    token = CancellationToken()
    crud = _crud(engine, parallel=ParallelOptions(max_workers=2))

    with pytest.raises(OperationCancelledError):
        crud.bulk_insert_from_df(
            _items(range(1, 21)), "items", generar_sql=False, on_progress=_cancel_at(token, 2), cancel_token=token
        )

    result = crud.last_parallel_result
    assert result is not None and result.partition_errors
    assert all("Operación cancelada" in error for error in result.partition_errors)
    assert len(_ids(engine)) == crud.rows_committed == result.total_rows
