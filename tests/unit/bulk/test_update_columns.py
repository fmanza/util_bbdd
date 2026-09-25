"""Columnas que prepara ``BulkCrud`` y DataFrame del llamador (P-09 y P-07 parcial del performance-audit de bulk).

- P-09: el UPDATE solo convierte la PK y las columnas actualizables; las columnas del DataFrame que no están en la
  tabla no se procesan.
- P-07 (parcial): el DataFrame de trabajo es una copia superficial; el renombrado de columnas por dialecto no debe
  alterar el DataFrame del llamador.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, text

import util_bbdd.bulk.crud as crud_module

from util_bbdd.bulk import BulkCrud

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'upd.db'}")
    Table(
        "items", MetaData(), Column("id", Integer, primary_key=True), Column("name", String(20)), Column("qty", Integer)
    ).create(eng)
    with eng.begin() as conn:
        conn.execute(text("INSERT INTO items (id, name, qty) VALUES (1, 'a', 10), (2, 'b', 20)"))
    return eng


def _rows(engine: Engine) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text("SELECT id, name, qty FROM items ORDER BY id"))]


def test_update_converts_only_pk_and_updatable_columns(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    original = crud_module.dataframe_to_sql_records

    def _spy(df: pd.DataFrame, **kwargs: Any) -> list[dict[str, Any]]:
        seen.append(list(df.columns))
        return original(df, **kwargs)

    monkeypatch.setattr(crud_module, "dataframe_to_sql_records", _spy)
    df = pd.DataFrame({"extra": [object(), object()], "name": ["x", "y"], "id": [1, 2], "otra": [1.5, 2.5]})

    BulkCrud(engine).bulk_update_from_df(df, "items", generar_sql=False)

    assert seen == [["id", "name"]]
    assert _rows(engine) == [(1, "x", 10), (2, "y", 20)]


def test_update_ignores_extra_columns_in_generated_sql(engine: Engine, tmp_path: Path) -> None:
    df = pd.DataFrame({"id": [2], "qty": [99], "extra": ["no"]})

    BulkCrud(engine).bulk_update_from_df(df, "items", generar_sql=True, path_sql=tmp_path)

    (sql_file,) = tmp_path.glob("*.sql")
    sql = sql_file.read_text(encoding="utf-8")
    assert "extra" not in sql
    with engine.begin() as conn:
        conn.exec_driver_sql(sql.strip().rstrip(";"))
    assert _rows(engine) == [(1, "a", 10), (2, "b", 99)]


def test_caller_dataframe_is_not_modified(engine: Engine) -> None:
    df = pd.DataFrame({"ID": [3, 4], "NAME": ["c", "d"], "QTY": [30, 40]})
    snapshot = df.copy()

    crud = BulkCrud(engine)
    crud.bulk_insert_from_df(df, "items", generar_sql=False)
    crud.bulk_update_from_df(df.assign(QTY=[31, 41]), "items", generar_sql=False)
    crud.bulk_insert_from_chunks([pd.DataFrame({"ID": [5], "NAME": ["e"], "QTY": [50]})], "items")

    pd.testing.assert_frame_equal(df, snapshot)
    assert list(df.columns) == ["ID", "NAME", "QTY"]
    assert _rows(engine)[2:] == [(3, "c", 31), (4, "d", 41), (5, "e", 50)]
