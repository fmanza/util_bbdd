"""U-B1 (G37 de util_bbdd_web): ``rows_committed`` y ``last_operation_rows_committed`` cuentan en todos los modos.

Hasta v4.4.x solo avanzaban con ``commit_every_n_chunks``: en modo atómico (el de por defecto) se quedaban en 0, y las
cargas paralelas de ``bulk_*_from_df`` no sumaban. Ahora cuentan las filas de cada transacción confirmada.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution import parallel_planner
from util_bbdd.bulk.options import AuditOptions, BatchOptions, ParallelOptions, RejectOptions
from util_bbdd.exceptions import ParallelLoadError

pytestmark = pytest.mark.unit

Operation = Literal["insert", "update", "delete"]


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


def _count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one())


def _crud(engine: Engine, *, every: int | None = None, workers: int | None = None, **extra: Any) -> BulkCrud:
    return BulkCrud(
        engine,
        batch=BatchOptions(chunk_size=3, commit_every_n_chunks=every),
        audit=AuditOptions(warn_if_disabled=False),
        parallel=None if workers is None else ParallelOptions(max_workers=workers),
        **extra,
    )


def _run(crud: BulkCrud, operation: Operation, df: pd.DataFrame) -> None:
    getattr(crud, f"bulk_{operation}_from_df")(df, "items", generar_sql=False)


@pytest.mark.parametrize("every", [None, 2], ids=["atomico", "cadencia"])
def test_counters_match_the_rows_of_each_operation(engine: Engine, every: int | None) -> None:
    crud = _crud(engine, every=every)

    _run(crud, "insert", _items(range(1, 11)))
    assert (crud.rows_committed, crud.last_operation_rows_committed) == (10, 10)
    assert _count(engine) == 10

    _run(crud, "update", _items(range(1, 8), "u"))
    assert (crud.rows_committed, crud.last_operation_rows_committed) == (17, 7)

    _run(crud, "delete", _items(range(1, 5)))
    assert (crud.rows_committed, crud.last_operation_rows_committed) == (21, 4)
    assert _count(engine) == 6


def test_atomic_failure_counts_nothing(engine: Engine) -> None:
    crud = _crud(engine)
    _run(crud, "insert", _items([5]))

    with pytest.raises(IntegrityError):
        _run(crud, "insert", _items(range(1, 9)))  # el lote de la fila 5 falla: la operación entera se deshace

    assert (crud.rows_committed, crud.last_operation_rows_committed) == (1, 0)
    assert _count(engine) == 1


def test_session_counts_when_it_commits(engine: Engine) -> None:
    crud = _crud(engine)
    with crud.bulk_session():
        _run(crud, "insert", _items(range(1, 5)))
        _run(crud, "delete", _items([1]))
        assert crud.rows_committed == 0  # ejecutadas, pendientes del commit de la sesión

    assert (crud.rows_committed, crud.last_operation_rows_committed) == (5, 1)

    with pytest.raises(RuntimeError), crud.bulk_session():
        _run(crud, "insert", _items(range(10, 13)))
        raise RuntimeError("fallo dentro de la sesión")

    assert crud.rows_committed == 5  # la sesión deshecha no suma
    assert _count(engine) == 3


def test_streaming_counts_the_whole_sequence(engine: Engine) -> None:
    crud = _crud(engine)
    chunks = [_items(range(1, 5)), _items(range(5, 8))]

    assert crud.bulk_insert_from_chunks(chunks, "items") == 7
    assert (crud.rows_committed, crud.last_operation_rows_committed) == (7, 7)

    assert crud.bulk_delete_from_chunks([_items([1, 2]), _items([3])], "items") == 3
    assert (crud.rows_committed, crud.last_operation_rows_committed) == (10, 3)


def test_rejected_rows_keep_counting_as_positions(engine: Engine, tmp_path: Path) -> None:
    _run(_crud(engine), "insert", _items([3]))
    crud = _crud(engine, rejects=RejectOptions(on_error="isolate", csv_path=tmp_path / "rechazos.csv"))

    _run(crud, "insert", _items(range(1, 6)))

    assert crud.rows_rejected == 1
    assert crud.last_operation_rows_committed == 5  # posiciones de la entrada (se puede reanudar en df.iloc[5:])
    assert _count(engine) == 5


def test_sql_generation_counts_nothing(engine: Engine, tmp_path: Path) -> None:
    crud = _crud(engine)
    crud.bulk_insert_from_df(_items(range(1, 4)), "items", generar_sql=True, path_sql=tmp_path)
    assert (crud.rows_committed, crud.last_operation_rows_committed) == (0, 0)


@pytest.mark.usefixtures("several_writers")
@pytest.mark.parametrize("every", [None, 2], ids=["atomico", "cadencia"])
def test_parallel_load_counts_its_partitions(engine: Engine, every: int | None) -> None:
    crud = _crud(engine, every=every, workers=2)

    _run(crud, "insert", _items(range(1, 21)))
    assert crud.last_parallel_result is not None and len(crud.last_parallel_result.partition_results) == 2
    assert (crud.rows_committed, crud.last_operation_rows_committed) == (20, 20)

    _run(crud, "update", _items(range(1, 11), "u"))
    _run(crud, "delete", _items(range(11, 21)))
    assert (crud.rows_committed, crud.last_operation_rows_committed) == (40, 10)
    assert _count(engine) == 10


@pytest.mark.usefixtures("several_writers")
def test_parallel_failure_counts_the_confirmed_partitions(engine: Engine) -> None:
    _run(_crud(engine), "insert", _items([15]))
    crud = _crud(engine, workers=2)

    with pytest.raises(ParallelLoadError) as caught:
        _run(crud, "insert", _items(range(1, 21)))  # la segunda partición (11-20) choca con la fila 15

    assert caught.value.result is crud.last_parallel_result
    assert (crud.rows_committed, crud.last_operation_rows_committed) == (10, 10)
    assert _count(engine) == 11
