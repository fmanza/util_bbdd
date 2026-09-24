"""``ParallelBulkLoader`` anota en ``partition_errors`` cualquier error de una partición, como documenta la API.

Antes solo capturaba ``SQLAlchemyError``, ``ValueError`` y ``pandas.errors.DatabaseError``: un error del lector de la
partición (``OSError``, ``KeyError``…) o al crear su ``BulkCrud`` abortaba ``load()`` entero y se perdían los
resultados del resto de particiones.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, text

import util_bbdd.bulk._execution.parallel_loader as pl_mod

from util_bbdd.bulk import ParallelBulkLoader

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'pl.db'}")
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10))).create(eng)
    return eng


def _ids(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT id FROM items ORDER BY id"))]


def _ok(ids: list[int]) -> Any:
    return lambda: [pd.DataFrame({"id": ids, "v": "x"})]


def test_reader_error_is_recorded_and_other_partitions_load(engine: Engine) -> None:
    def _broken_reader() -> list[pd.DataFrame]:
        raise KeyError("columna_inexistente")

    result = ParallelBulkLoader(engine, max_workers=1).load("items", [_ok([1, 2]), _broken_reader, _ok([3])])

    assert result.total_rows == 3
    assert result.partition_errors == ["partición 1: KeyError: 'columna_inexistente'"]
    assert _ids(engine) == [1, 2, 3]


def test_error_while_iterating_reader_rolls_back_that_partition(engine: Engine) -> None:
    def _fails_midway() -> Iterator[pd.DataFrame]:
        yield pd.DataFrame({"id": [10, 11], "v": "x"})
        raise OSError("se perdió el fichero de origen")

    result = ParallelBulkLoader(engine, max_workers=1).load("items", [_fails_midway, _ok([1])])

    assert result.partition_errors == ["partición 0: OSError: se perdió el fichero de origen"]
    assert _ids(engine) == [1]  # la partición fallida no deja filas (modo atómico)


def test_error_creating_bulkcrud_is_recorded(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    def _broken_crud(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("configuración inválida")

    monkeypatch.setattr(pl_mod, "BulkCrud", _broken_crud)

    result = ParallelBulkLoader(engine, max_workers=2).load("items", [_ok([1]), _ok([2])])

    assert result.total_rows == 0
    assert sorted(result.partition_errors) == [
        "partición 0: RuntimeError: configuración inválida",
        "partición 1: RuntimeError: configuración inválida",
    ]


def test_database_errors_keep_their_message_format(engine: Engine) -> None:
    result = ParallelBulkLoader(engine, max_workers=1).load("items", [_ok([1]), _ok([1])])

    assert result.total_rows == 1
    (error,) = result.partition_errors
    assert error.startswith("partición 1: (sqlite3.IntegrityError)")
