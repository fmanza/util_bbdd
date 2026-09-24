"""Preparación y ejecución por bloques (hallazgo P-07 del performance-audit de bulk).

Antes se convertía todo el DataFrame a registros (y, con ``generar_sql``, todas las líneas y el texto unido) antes del
primer lote. Ahora cada bloque de ``chunk_size`` filas se convierte, se ejecuta o se escribe y se descarta. Se mantiene:
una sola transacción (atómica, o commit-as-you-go con ``commit_every_n_chunks``), la conexión de ``bulk_session`` y el
contenido exacto del fichero SQL.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import IntegrityError

import util_bbdd.bulk.crud as crud_module

from util_bbdd.bulk import BulkCrud

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'blocks.db'}")
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(20))).create(eng)
    return eng


def _ids(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT id FROM items ORDER BY id"))]


def _frame(ids: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"id": ids, "v": [f"v{i}'%" for i in ids]})


@pytest.mark.parametrize("operation", ["insert", "update"])
def test_records_are_converted_block_by_block(engine: Engine, monkeypatch: pytest.MonkeyPatch, operation: str) -> None:
    sizes: list[int] = []
    original = crud_module.dataframe_to_sql_records

    def _spy(df: pd.DataFrame) -> list[dict[str, Any]]:
        sizes.append(len(df))
        return original(df)

    crud = BulkCrud(engine, chunk_size=3)
    crud.bulk_insert_from_df(_frame(list(range(1, 9))), "items", False)
    monkeypatch.setattr(crud_module, "dataframe_to_sql_records", _spy)

    if operation == "insert":
        crud.bulk_insert_from_df(_frame(list(range(11, 19))), "items", False)
    else:
        crud.bulk_update_from_df(_frame(list(range(1, 9))).assign(v="x"), "items", False)

    assert sizes == [3, 3, 2]


def test_failure_in_a_later_block_rolls_back_everything(engine: Engine) -> None:
    crud = BulkCrud(engine, chunk_size=2)

    with pytest.raises(IntegrityError):
        crud.bulk_insert_from_df(_frame([1, 2, 3, 4, 1]), "items", False)  # el tercer bloque repite la PK 1

    assert _ids(engine) == []


def test_commit_every_n_chunks_keeps_committed_blocks(engine: Engine) -> None:
    crud = BulkCrud(engine, chunk_size=2, commit_every_n_chunks=1)

    with pytest.raises(IntegrityError):
        crud.bulk_insert_from_df(_frame([1, 2, 3, 4, 1]), "items", False)

    assert _ids(engine) == [1, 2, 3, 4]
    assert crud.rows_committed == 4


def test_blocks_use_the_bulk_session_transaction(engine: Engine) -> None:
    crud = BulkCrud(engine, chunk_size=2)

    with pytest.raises(RuntimeError), crud.bulk_session():
        crud.bulk_insert_from_df(_frame([1, 2, 3, 4, 5]), "items", False)
        crud.bulk_update_from_df(_frame([1, 2, 3]).assign(v="x"), "items", False)
        raise RuntimeError("fallo posterior")

    assert _ids(engine) == []


@pytest.mark.parametrize("operation", ["insert", "update", "delete"])
def test_generated_file_is_identical_for_any_chunk_size(engine: Engine, tmp_path: Path, operation: str) -> None:
    df = _frame(list(range(1, 8)))
    contents: list[bytes] = []
    for chunk_size in (2, 5000):
        out = tmp_path / str(chunk_size)
        crud = BulkCrud(engine, chunk_size=chunk_size)
        getattr(crud, f"bulk_{operation}_from_df")(df, "items", True, path_sql=out)
        (sql_file,) = out.glob("*.sql")
        contents.append(sql_file.read_bytes())

    assert contents[0] == contents[1]
    assert contents[0].count(b";") == len(df)
    assert not contents[0].endswith(b"\n")


def test_failed_generation_leaves_no_file(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    original = crud_module.generate_insert_sql

    def _fail_on_second_block(*args: Any, **kwargs: Any) -> list[str]:
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("fallo en el segundo bloque")
        return original(*args, **kwargs)

    monkeypatch.setattr(crud_module, "generate_insert_sql", _fail_on_second_block)
    out = tmp_path / "sql"

    with pytest.raises(ValueError, match="segundo bloque"):
        BulkCrud(engine, chunk_size=2).bulk_insert_from_df(_frame([1, 2, 3, 4]), "items", True, path_sql=out)

    assert list(out.glob("*")) == []
