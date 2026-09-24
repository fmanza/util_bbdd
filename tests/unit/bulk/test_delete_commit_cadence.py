"""``bulk_delete_from_df`` y ``commit_every_n_chunks`` (auditoría de ``bulk`` del 2026-09-24, hallazgo 7).

INSERT y UPDATE confirman cada N lotes con ``commit_every_n_chunks``; el DELETE lo ignoraba fuera de ``bulk_session``:
todo el borrado iba en una sola transacción. Ahora confirma igual, dentro y fuera de la sesión. Un trigger de SQLite
hace fallar el tercer lote para comprobar qué queda confirmado.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.bulk import BulkCrud

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'del.db'}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
        conn.execute(text("INSERT INTO t VALUES (1,'a'), (2,'b'), (3,'c'), (4,'d'), (5,'e')"))
        conn.execute(
            text("CREATE TRIGGER no_borrar_5 BEFORE DELETE ON t WHEN old.id = 5 BEGIN SELECT RAISE(ABORT, 'no'); END")
        )
    return eng


def _ids(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT id FROM t ORDER BY id"))]


PKS = pd.DataFrame({"id": [1, 2, 3, 4, 5]})  # lotes de 2: [1, 2], [3, 4], [5] (falla)


def test_without_commit_cadence_delete_is_atomic(engine: Engine) -> None:
    with pytest.raises(SQLAlchemyError):
        BulkCrud(engine, chunk_size=2).bulk_delete_from_df(PKS, "t", False)

    assert _ids(engine) == [1, 2, 3, 4, 5]


def test_commit_cadence_keeps_committed_batches(engine: Engine) -> None:
    with pytest.raises(SQLAlchemyError):
        BulkCrud(engine, chunk_size=2, commit_every_n_chunks=1).bulk_delete_from_df(PKS, "t", False)

    assert _ids(engine) == [5]


def test_commit_cadence_inside_bulk_session(engine: Engine) -> None:
    crud = BulkCrud(engine, chunk_size=2, commit_every_n_chunks=2)

    with pytest.raises(SQLAlchemyError), crud.bulk_session():
        crud.bulk_delete_from_df(PKS, "t", False)

    assert _ids(engine) == [5]  # los dos primeros lotes se confirman juntos


def test_commit_cadence_successful_delete(engine: Engine) -> None:
    BulkCrud(engine, chunk_size=2, commit_every_n_chunks=1).bulk_delete_from_df(PKS.iloc[:4], "t", False)

    assert _ids(engine) == [5]
