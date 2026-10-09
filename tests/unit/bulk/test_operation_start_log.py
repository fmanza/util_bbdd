"""v0.40.1 (H3): cada operación de ``bulk`` registra su inicio (DEBUG), no solo el final.

Sin ese log, el tiempo de una operación larga se atribuía en el log a la línea anterior: con un INSERT de 1M filas, el
informe de ``EngineReadinessAdvisor`` parecía tardar 83 s (auditoría de un log de ``pruebas_util``, 2026-10-09).
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk import BulkCrud

pytestmark = pytest.mark.unit

_DATAFRAMES: dict[str, pd.DataFrame] = {
    "insert": pd.DataFrame({"id": [10, 11], "name": ["x", "y"]}),
    "update": pd.DataFrame({"id": [1, 2], "name": ["z", "w"]}),
    "delete": pd.DataFrame({"id": [1, 2]}),
}


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'start_log.db'}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO items VALUES (1, 'a'), (2, 'b')"))
    return eng


@pytest.mark.parametrize("generar_sql", [True, False])
@pytest.mark.parametrize("operation", ["insert", "update", "delete"])
def test_operation_logs_its_start_before_its_end(
    engine: Engine, tmp_path: Path, caplog: pytest.LogCaptureFixture, operation: str, generar_sql: bool
) -> None:
    crud = BulkCrud(engine)
    method: Any = getattr(crud, f"bulk_{operation}_from_df")

    with caplog.at_level(logging.DEBUG, logger="util_bbdd.bulk.crud"):
        method(_DATAFRAMES[operation], "items", generar_sql=generar_sql, path_sql=tmp_path if generar_sql else None)

    records = [r for r in caplog.records if r.name == "util_bbdd.bulk.crud"]
    start = next(i for i, r in enumerate(records) if f"bulk {operation.upper()} iniciado" in r.getMessage())
    end = next(i for i, r in enumerate(records) if "finalizado" in r.getMessage())
    assert start < end
    assert records[start].levelno == logging.DEBUG
    assert "2 filas → items" in records[start].getMessage()
    assert ("solo SQL" if generar_sql else "en BD") in records[start].getMessage()
