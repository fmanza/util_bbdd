"""Tests del streaming bulk_insert_from_chunks (carga de gran volumen)."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from sqlalchemy import Engine, create_engine

import util_bbdd.bulk.crud as crud_mod

from util_bbdd.bulk.crud import BulkCrud


def _make_sqlite_engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    return engine


def _count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.exec_driver_sql("SELECT COUNT(*) FROM items").scalar() or 0)


class TestBulkInsertFromChunks:
    def test_inserts_all_rows_from_multiple_chunks(self) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, chunk_size=2)
        chunks = [
            pd.DataFrame({"id": [1, 2], "name": ["a", "b"]}),
            pd.DataFrame({"id": [3, 4], "name": ["c", "d"]}),
            pd.DataFrame({"id": [5], "name": ["e"]}),
        ]

        total = crud.bulk_insert_from_chunks(iter(chunks), "items")

        assert total == 5
        assert _count(engine) == 5

    def test_returns_zero_for_no_chunks(self) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine)
        assert crud.bulk_insert_from_chunks(iter([]), "items") == 0
        assert _count(engine) == 0

    def test_skips_empty_chunks(self) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine)
        chunks = [
            pd.DataFrame({"id": [], "name": []}),
            pd.DataFrame({"id": [1], "name": ["a"]}),
        ]
        total = crud.bulk_insert_from_chunks(iter(chunks), "items")
        assert total == 1
        assert _count(engine) == 1

    def test_resolves_insert_columns_once_across_chunks(self) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, chunk_size=10)
        chunks = [pd.DataFrame({"id": [i], "name": [f"n{i}"]}) for i in range(1, 5)]

        with patch.object(crud_mod, "get_insert_columns", wraps=crud_mod.get_insert_columns) as spy:
            crud.bulk_insert_from_chunks(iter(chunks), "items")

        # Resolución de columnas una sola vez pese a 4 chunks
        assert spy.call_count == 1

    def test_respects_commit_cadence(self) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, chunk_size=1, commit_every_n_chunks=2)
        chunks = [pd.DataFrame({"id": [i], "name": [f"n{i}"]}) for i in range(1, 6)]

        total = crud.bulk_insert_from_chunks(iter(chunks), "items")

        assert total == 5
        assert _count(engine) == 5
        assert crud._batch_statement_executor._chunks_since_commit == 0

    def test_exclude_autoincrement_pk(self) -> None:
        # PK INTEGER autoincremental en SQLite: excluida del INSERT → la asigna el motor
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
        crud = BulkCrud(engine, chunk_size=5)
        chunks = [pd.DataFrame({"name": ["a", "b"]}), pd.DataFrame({"name": ["c"]})]

        total = crud.bulk_insert_from_chunks(iter(chunks), "items", exclude_autoincrement_pk=True)

        assert total == 3
        with engine.connect() as conn:
            ids = [r[0] for r in conn.exec_driver_sql("SELECT id FROM items ORDER BY id").fetchall()]
        assert ids == [1, 2, 3]  # autoincrement asignó las PKs
