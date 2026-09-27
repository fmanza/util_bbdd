"""Caracterización de la cadencia de commit (``commit_every_n_chunks``) antes de encapsularla (R14, sesión 2026-09-26ze).

Fijan la secuencia exacta de sentencias y commits que hoy produce el código, para que el refactor de ``SessionScope`` no
la cambie (F-1 y F-2 del AUDIT_PLAN):

- El contador de lotes del INSERT/UPDATE se arrastra entre llamadas dentro de una ``bulk_session``; el del DELETE se
  reinicia en cada llamada y el DELETE no suma a ``rows_committed``.
- Fuera de sesión, cada llamada del ejecutor empieza con el contador a 0 y confirma al final.
- Al abrir una ``bulk_session`` el contador de lotes vuelve a 0, aunque una sesión anterior fallara a mitad.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Engine, MetaData, create_engine, event, insert, text

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.executors import BatchStatementExecutor, DeleteBatchExecutor

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = create_engine(f"sqlite:///{tmp_path / 'cadence.db'}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
        conn.execute(text("INSERT INTO t VALUES (100, 'x'), (101, 'x'), (102, 'x'), (103, 'x')"))
    yield eng
    eng.dispose()


def _record(engine: Engine) -> list[str]:
    """Secuencia de INSERT/DELETE ejecutados y COMMIT de ``engine`` desde este momento."""
    log: list[str] = []

    def _stmt(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        verb = statement.lstrip().split(None, 1)[0].upper()
        if verb in ("INSERT", "DELETE"):
            log.append(verb)

    event.listen(engine, "before_cursor_execute", _stmt)
    event.listen(engine, "commit", lambda _conn: log.append("COMMIT"))
    return log


def _crud(engine: Engine) -> BulkCrud:
    return BulkCrud(engine, chunk_size=1, commit_every_n_chunks=2, warn_if_audit_disabled=False)


def _insert(crud: BulkCrud, *ids: int) -> None:
    crud.bulk_insert_from_df(pd.DataFrame({"id": list(ids), "v": ["a"] * len(ids)}), "t", generar_sql=False)


def _delete(crud: BulkCrud, *ids: int) -> None:
    crud.bulk_delete_from_df(pd.DataFrame({"id": list(ids)}), "t", generar_sql=False)


def test_in_session_insert_counter_carries_over_and_delete_counter_restarts(engine: Engine) -> None:
    crud = _crud(engine)
    crud.reflect_table("t")
    log = _record(engine)

    with crud.bulk_session():
        _insert(crud, 1)  # contador INSERT 1
        _delete(crud, 100)  # contador DELETE local 1: sin commit (con un contador compartido serían 2 y confirmaría)
        _insert(crud, 2)  # contador INSERT 2: commit periódico
        _delete(crud, 101, 102)  # contador DELETE local 1, 2: commit periódico
        _insert(crud, 3)  # contador INSERT 1

    assert log == ["INSERT", "DELETE", "INSERT", "COMMIT", "DELETE", "DELETE", "COMMIT", "INSERT", "COMMIT"]
    assert crud.rows_committed == 6  # 3 INSERT + 3 DELETE (hasta v0.17.x los DELETE no sumaban: 3)


def test_outside_session_each_executor_call_starts_at_zero_and_commits_at_the_end(engine: Engine) -> None:
    table = MetaData()
    table.reflect(engine, only=["t"])
    t = table.tables["t"]
    inserter = BatchStatementExecutor(engine=engine, chunk_size=1, commit_every_n_chunks=2)
    deleter = DeleteBatchExecutor(engine=engine, chunk_size=1, commit_every_n_chunks=2)
    log = _record(engine)

    inserter.execute(records=[{"id": 1, "v": "a"}], stmt=insert(t))
    inserter.execute(records=[{"id": 2, "v": "a"}], stmt=insert(t))
    deleter.execute(table=t, df=pd.DataFrame({"id": [100, 101, 102]}), pk_cols=["id"])

    assert log == ["INSERT", "COMMIT", "INSERT", "COMMIT", "DELETE", "DELETE", "COMMIT", "DELETE", "COMMIT"]
    assert inserter.rows_committed == 2


def test_opening_a_session_resets_the_batch_counter_after_a_failed_session(engine: Engine) -> None:
    crud = _crud(engine)
    crud.reflect_table("t")
    with pytest.raises(RuntimeError), crud.bulk_session():
        _insert(crud, 1)  # contador 1, sin commit
        raise RuntimeError("fallo a mitad de sesión")
    log = _record(engine)

    with crud.bulk_session():
        _insert(crud, 2)  # contador 1 otra vez (sin reiniciar serían 2: commit periódico aquí)
        _insert(crud, 3)  # contador 2: commit periódico

    assert log == ["INSERT", "INSERT", "COMMIT"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT id FROM t WHERE id < 100 ORDER BY id")).scalars().all() == [2, 3]


def test_error_in_maintenance_scope_discards_the_pending_rows(engine: Engine) -> None:
    # Con cadencia, el error dentro de maintenance_scope deshace lo pendiente y restaura; las filas deshechas no deben
    # contarse después como confirmadas.
    crud = _crud(engine)
    crud.reflect_table("t")
    with pytest.raises(RuntimeError), crud.bulk_session(), crud.maintenance_scope("t"):
        _insert(crud, 1)  # 1 fila pendiente, sin commit
        raise RuntimeError("fallo dentro de maintenance_scope")

    with crud.bulk_session():
        _insert(crud, 2)

    assert crud.rows_committed == 1


def test_atomic_session_commits_once_at_the_end(engine: Engine) -> None:
    crud = BulkCrud(engine, chunk_size=1, warn_if_audit_disabled=False)
    crud.reflect_table("t")
    log = _record(engine)

    with crud.bulk_session():
        _insert(crud, 1, 2, 3)
        _delete(crud, 100, 101)

    assert log == ["INSERT", "INSERT", "INSERT", "DELETE", "DELETE", "COMMIT"]
    assert crud.rows_committed == 0  # sin cadencia no avanza (BLK-08)
