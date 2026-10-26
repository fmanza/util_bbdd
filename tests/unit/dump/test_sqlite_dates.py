"""U-V5 (G33 de util_bbdd_web): fechas en texto ISO de un origen SQLite se convierten al leer."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Column, Date, DateTime, Integer, MetaData, String, Table, Time, create_engine, select, text

from util_bbdd.dump import DumpConfig, DumpOrchestrator
from util_bbdd.dump._source_reader import _parse_temporal_text, _sqlite_temporal_parsers

pytestmark = pytest.mark.unit


def _target_table() -> Table:
    return Table(
        "eventos",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("dia", Date),
        Column("momento", DateTime),
        Column("sello", DateTime),
        Column("hora", Time),
    )


def _engines(tmp_path: Path, rows: list[str]) -> tuple[Any, Any, Table]:
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    with src.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE eventos (id INTEGER PRIMARY KEY, dia DATE, momento DATETIME, sello TIMESTAMP, hora TIME)"
            )
        )
        for row in rows:
            conn.execute(text(f"INSERT INTO eventos VALUES {row}"))
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    table = _target_table()
    table.create(dst)
    return src, dst, table


def test_sqlite_to_sqlite_with_text_dates(tmp_path: Path) -> None:
    src, dst, table = _engines(
        tmp_path,
        [
            "(1, '2024-02-29', '2024-02-29 13:45:10.250000', '2024-03-01T08:00:00', '07:30:00')",
            "(2, NULL, NULL, NULL, NULL)",
        ],
    )

    result = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, truncate_target=True)).run()

    assert [(r.status, r.error_msg) for r in result.table_results] == [("success", "")]
    with dst.connect() as conn:
        rows = conn.execute(select(table).order_by(table.c.id)).all()
    assert [tuple(r) for r in rows] == [
        (1, date(2024, 2, 29), datetime(2024, 2, 29, 13, 45, 10, 250000), datetime(2024, 3, 1, 8), time(7, 30)),
        (2, None, None, None, None),
    ]


def test_non_iso_text_is_left_for_the_target(tmp_path: Path) -> None:
    """Un valor que no es ISO llega como texto, como antes de 4.4.0: el destino SQLite lo rechaza y la tabla falla."""
    src, dst, _ = _engines(
        tmp_path,
        ["(1, '2024-01-01', NULL, NULL, NULL)", "(2, '01/02/2024', NULL, NULL, NULL)"],
    )

    result = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, truncate_target=True)).run()

    (table,) = result.table_results
    assert table.status == "error"
    assert "Date type only accepts Python date objects" in table.error_msg


def test_parsers_by_declared_type() -> None:
    columns = [
        {"name": "d", "type": Date()},
        {"name": "dt", "type": DateTime()},
        {"name": "t", "type": Time()},
        {"name": "n", "type": Integer()},
    ]
    targets = [{"name": "D", "type": Date()}, {"name": "dt", "type": DateTime()}, {"name": "t", "type": Time()}]
    assert _sqlite_temporal_parsers(columns, targets) == {
        "d": date.fromisoformat,
        "dt": datetime.fromisoformat,
        "t": time.fromisoformat,
    }


def test_parsers_depend_on_the_target_type() -> None:
    """Hacia texto, o TIME hacia el DATE de Oracle (sin TIME), el valor sigue llegando como texto."""
    columns = [{"name": "d", "type": Date()}, {"name": "t", "type": Time()}, {"name": "x", "type": DateTime()}]
    targets = [{"name": "d", "type": String(10)}, {"name": "t", "type": DateTime()}]
    assert _sqlite_temporal_parsers(columns, targets) == {}


def test_parse_keeps_object_dtype_and_other_values() -> None:
    chunk = pd.DataFrame(
        [["2024-01-02 10:00:00", "x"], [None, "y"], ["no-iso", "z"], [datetime(2020, 1, 1), "w"]],
        columns=["f", "otra"],
        dtype=object,
    )

    (out,) = _parse_temporal_text(iter([chunk]), {"f": datetime.fromisoformat, "ausente": date.fromisoformat})

    assert out["f"].dtype == object  # no datetime64: llegan objetos datetime, como con cualquier driver
    assert out["f"].tolist() == [datetime(2024, 1, 2, 10), None, "no-iso", datetime(2020, 1, 1)]
    assert out["otra"].tolist() == ["x", "y", "z", "w"]


def test_other_sources_are_not_touched(tmp_path: Path) -> None:
    src, dst, _ = _engines(tmp_path, [])
    orchestrator = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, truncate_target=True))
    tables = {"eventos": "eventos"}
    assert orchestrator._sqlite_temporal_columns(tables, ["eventos"]) == {
        "eventos": {
            "dia": date.fromisoformat,
            "momento": datetime.fromisoformat,
            "sello": datetime.fromisoformat,
            "hora": time.fromisoformat,
        }
    }
    orchestrator._cfg.source_engine = MagicMock(**{"dialect.name": "postgresql"})
    assert orchestrator._sqlite_temporal_columns(tables, ["eventos"]) == {}
