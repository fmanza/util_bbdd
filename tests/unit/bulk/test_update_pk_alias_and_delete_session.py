"""Hallazgos P-25 y P-26 del performance-audit de bulk (``.ai/sessions/2026-09-23-performance-audit-bulk/``).

- P-25: el alias del parámetro de la PK en el WHERE (``pk_<col>``) coincidía con una columna real de ese nombre, que
  recibía el valor de la PK en el UPDATE sin ningún error.
- P-26: ``bulk_delete_from_df`` abría su propia transacción dentro de ``bulk_session``: no era atómico con la sesión
  y en SQLite fallaba con ``database is locked``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, text

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._support.validation import build_update_plan

pytestmark = pytest.mark.unit


def _rows(engine: Engine, table: str) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text(f"SELECT * FROM {table} ORDER BY id"))]


# --------------------------------------------------------------------------- P-25


def test_pk_alias_is_plain_when_no_column_collides() -> None:
    table = Table("t", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(5)))

    assert build_update_plan(table, ["id", "v"], "t").pk_param_map == {"id": "pk_id"}


def test_pk_alias_skips_existing_column_names() -> None:
    table = Table(
        "t",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("k", Integer, primary_key=True),
        Column("pk_id", Integer),
        Column("pk_id_1", Integer),
        Column("pk_k", Integer),
    )

    plan = build_update_plan(table, ["id", "k", "pk_id", "pk_id_1", "pk_k"], "t")

    assert plan.pk_param_map == {"id": "pk_id_2", "k": "pk_k_1"}
    assert not set(plan.pk_param_map.values()) & {c.name for c in table.columns}


@pytest.fixture
def pk_alias_engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'alias.db'}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, pk_id INTEGER, v TEXT)"))
        conn.execute(text("INSERT INTO t VALUES (1, 100, 'a'), (2, 200, 'b')"))
    return eng


def test_update_keeps_value_of_column_named_like_pk_alias(pk_alias_engine: Engine) -> None:
    df = pd.DataFrame({"id": [1, 2], "pk_id": [111, 222], "v": ["x", "y"]})

    BulkCrud(pk_alias_engine).bulk_update_from_df(df, "t", generar_sql=False)

    assert _rows(pk_alias_engine, "t") == [(1, 111, "x"), (2, 222, "y")]


def test_generated_update_keeps_value_of_column_named_like_pk_alias(pk_alias_engine: Engine, tmp_path: Path) -> None:
    df = pd.DataFrame({"id": [1, 2], "pk_id": [111, 222], "v": ["x", "y"]})

    BulkCrud(pk_alias_engine).bulk_update_from_df(df, "t", generar_sql=True, path_sql=tmp_path / "sql")

    (sql_file,) = (tmp_path / "sql").glob("*.sql")
    with pk_alias_engine.begin() as conn:
        for line in filter(None, (x.strip() for x in sql_file.read_text(encoding="utf-8").splitlines())):
            conn.exec_driver_sql(line.rstrip(";"))
    assert _rows(pk_alias_engine, "t") == [(1, 111, "x"), (2, 222, "y")]


# --------------------------------------------------------------------------- P-26


@pytest.fixture
def session_engine(tmp_path: Path) -> Engine:
    # timeout corto: sin la corrección, el DELETE espera al bloqueo de la propia sesión.
    eng = create_engine(f"sqlite:///{tmp_path / 'session.db'}", connect_args={"timeout": 1})
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10))).create(eng)
    with eng.begin() as conn:
        conn.execute(text("INSERT INTO items VALUES (1, 'a'), (2, 'b'), (3, 'c')"))
    return eng


@pytest.mark.parametrize("commit_every_n_chunks", [None, 1])
def test_delete_after_insert_in_same_session(session_engine: Engine, commit_every_n_chunks: int | None) -> None:
    crud = BulkCrud(session_engine, commit_every_n_chunks=commit_every_n_chunks)

    with crud.bulk_session():
        crud.bulk_insert_from_df(pd.DataFrame({"id": [4], "v": ["d"]}), "items", generar_sql=False)
        crud.bulk_delete_from_df(pd.DataFrame({"id": [1, 4]}), "items", generar_sql=False)

    assert _rows(session_engine, "items") == [(2, "b"), (3, "c")]


def test_delete_rolls_back_with_session(session_engine: Engine) -> None:
    crud = BulkCrud(session_engine)

    with pytest.raises(RuntimeError), crud.bulk_session():
        crud.bulk_delete_from_df(pd.DataFrame({"id": [1, 2]}), "items", generar_sql=False)
        raise RuntimeError("fallo posterior al DELETE")

    assert _rows(session_engine, "items") == [(1, "a"), (2, "b"), (3, "c")]


def test_delete_outside_session_uses_own_transaction(session_engine: Engine) -> None:
    crud = BulkCrud(session_engine)
    with crud.bulk_session():
        pass

    crud.bulk_delete_from_df(pd.DataFrame({"id": [3]}), "items", generar_sql=False)

    assert _rows(session_engine, "items") == [(1, "a"), (2, "b")]
