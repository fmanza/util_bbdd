"""Regresión: el tiempo de generar el SQL debe llegar a la auditoría (``tiempo_seg``).

Con ``generar_sql=True`` no se ejecuta nada en BD, pero ``__run_bulk_pipeline`` registraba ``elapsed = 0.0`` y todas las
filas ``sql=Sí`` del CSV salían con ``tiempo_seg = 0,000``. ``tiempo_seg`` es la única columna de tiempo: mide la
operación (ejecución en BD si ``sql=No``; generar y escribir el SQL si ``sql=Sí``).
"""

from __future__ import annotations

import importlib

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk import BulkCrud

pytestmark = pytest.mark.unit

_CRUD_MODULE = "util_bbdd.bulk.crud"

_DATAFRAMES: dict[str, pd.DataFrame] = {
    "insert": pd.DataFrame({"id": [10], "name": ["x"]}),
    "update": pd.DataFrame({"id": [1], "name": ["z"]}),
    "delete": pd.DataFrame({"id": [1]}),
}


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'timing.db'}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO items VALUES (1, 'a'), (2, 'b')"))
    return eng


def _run(crud: BulkCrud, operation: str, *, generar_sql: bool, tmp_path: Path) -> None:
    df = _DATAFRAMES[operation]
    method: Any = getattr(crud, f"bulk_{operation}_from_df")
    method(df, "items", generar_sql=generar_sql, path_sql=tmp_path if generar_sql else None)


@pytest.mark.parametrize("generar_sql", [True, False])
@pytest.mark.parametrize("operation", ["insert", "update", "delete"])
def test_audit_receives_measured_time_with_and_without_sql_generation(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str, generar_sql: bool
) -> None:
    ticks = iter([10.0, 12.5])
    monkeypatch.setattr(importlib.import_module(_CRUD_MODULE), "perf_counter", lambda: next(ticks))
    crud = BulkCrud(engine)
    registrar = MagicMock()
    crud.audit_manager.registrar_operacion = registrar

    _run(crud, operation, generar_sql=generar_sql, tmp_path=tmp_path)

    registrar.assert_called_once()
    _tabla, _motor, registered_operation, _rowcount, elapsed, genero_sql = registrar.call_args.args
    assert registered_operation == operation.upper()
    assert genero_sql is generar_sql
    assert elapsed == pytest.approx(2.5)


def test_generated_sql_is_written_and_nothing_is_executed(engine: Engine, tmp_path: Path) -> None:
    crud = BulkCrud(engine)
    crud.audit_manager.registrar_operacion = MagicMock()

    _run(crud, "delete", generar_sql=True, tmp_path=tmp_path)

    assert list(tmp_path.glob("*.sql"))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one() == 2
