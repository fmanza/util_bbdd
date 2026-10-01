"""``chunk_size`` debe ser un entero ≥ 1 (auditoría de ``bulk`` del 2026-09-24, hallazgo 1).

Antes no se validaba: con un valor negativo ``range(0, n, chunk_size)`` no generaba lotes, la carga no escribía nada,
sin error, y la auditoría registraba las filas como insertadas. Con 0 fallaba al ejecutar con
``range() arg 3 must not be zero``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk import BulkCrud, ParallelBulkLoader
from util_bbdd.bulk._execution.batch import BatchStatementExecutor, DeleteBatchExecutor, validate_chunk_size

pytestmark = pytest.mark.unit

INVALID: list[Any] = [0, -1, -5000, 2.5, "100", None, True, False]


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'cs.db'}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
    return eng


@pytest.mark.parametrize("value", [1, 5000, np.int64(7)])
def test_valid_values_are_returned_as_int(value: Any) -> None:
    result = validate_chunk_size(value)

    assert result == int(value)
    assert type(result) is int


@pytest.mark.parametrize("value", INVALID)
def test_invalid_values_raise_value_error(value: Any) -> None:
    with pytest.raises(ValueError, match="chunk_size debe ser un entero"):
        validate_chunk_size(value)


@pytest.mark.parametrize("value", [v for v in INVALID if v is not None])  # None = lote por motor (B-04)
def test_bulkcrud_rejects_invalid_chunk_size(engine: Engine, value: Any) -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        BulkCrud(engine, chunk_size=value)


@pytest.mark.parametrize("value", [0, -1])
def test_executors_and_parallel_loader_reject_invalid_chunk_size(engine: Engine, value: int) -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        BatchStatementExecutor(engine=engine, chunk_size=value)
    with pytest.raises(ValueError, match="chunk_size"):
        DeleteBatchExecutor(engine=engine, chunk_size=value)
    with pytest.raises(ValueError, match="chunk_size"):
        ParallelBulkLoader(engine, chunk_size=value)


def test_negative_chunk_size_no_longer_loses_rows_silently(engine: Engine, tmp_path: Path) -> None:
    audit = tmp_path / "audit.csv"

    with pytest.raises(ValueError, match="chunk_size"):
        BulkCrud(engine, chunk_size=-5, audit_csv_path=audit).bulk_insert_from_df(
            pd.DataFrame({"id": [1, 2, 3], "v": list("abc")}), "t", False
        )

    assert not audit.exists()  # sin fila de auditoría de una carga que no ocurrió
