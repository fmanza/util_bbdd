"""PD-05 (performance-audit de dump 2026-09-25): el volcado copia los valores sin alterarlos.

Antes, ``pd.read_sql`` pasaba a ``float64`` los enteros de columnas con algún NULL (BIGINT > 2^53 perdía precisión) y
``Decimal`` a ``float``; y ``bulk`` quitaba los espacios de los extremos de las cadenas. Ahora ``dump`` lee los chunks
con ``dtype=object`` y crea sus ``BulkCrud`` con ``strip_strings=False``.
"""

from __future__ import annotations

import datetime

from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from sqlalchemy import create_engine, text

from util_bbdd.bulk.normalize import _normalize_values, dataframe_to_sql_records
from util_bbdd.dump import DumpConfig, DumpOrchestrator
from util_bbdd.dump.orchestrator import _execute_read, _read_chunks

pytestmark = pytest.mark.unit

BIG = 9_007_199_254_740_993  # 2^53 + 1: no representable en float64


class TestNormalizeStripStrings:
    def test_default_strips_strings(self):
        df = pd.DataFrame({"s": ["  a  ", None]})
        assert dataframe_to_sql_records(df) == [{"s": "a"}, {"s": None}]

    def test_strip_strings_false_keeps_spaces_in_text_columns(self):
        df = pd.DataFrame({"s": ["  a  ", None, ""]})
        assert dataframe_to_sql_records(df, strip_strings=False) == [{"s": "  a  "}, {"s": None}, {"s": ""}]

    def test_strip_strings_false_keeps_spaces_in_mixed_columns(self):
        df = pd.DataFrame({"m": pd.Series(["  a  ", 1, None], dtype=object)})
        assert dataframe_to_sql_records(df, strip_strings=False) == [{"m": "  a  "}, {"m": 1}, {"m": None}]


class TestPassthroughFastPath:
    """La vía rápida de columnas object devuelve exactamente lo mismo que el camino general, celda a celda."""

    @pytest.mark.parametrize(
        "values",
        [
            [1, None, BIG],
            [True, False, None],
            [Decimal("12345678901234567.8912345678"), None],
            [0.5, None],
            [datetime.datetime(2024, 1, 2, 3, 4, 5), None],
            [datetime.date(2024, 1, 2), datetime.time(3, 4), datetime.timedelta(seconds=5)],
            # Fuera de la vía rápida (caen al camino general):
            [Decimal("NaN"), 1],
            [float("nan"), 1.0],
            [pd.Timestamp("2024-01-02"), None],
            [pd.NA, 1],
            [b"abc", 1],
        ],
    )
    def test_same_output_as_general_path(self, values):
        df = pd.DataFrame({"c": pd.Series(values, dtype=object)})
        got = [r["c"] for r in dataframe_to_sql_records(df)]
        expected = _normalize_values(list(values), box=True)
        assert got == expected
        assert [type(v) for v in got] == [type(v) for v in expected]


class TestReadChunks:
    def test_keeps_python_values_and_chunks(self, tmp_path: Path):
        eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
        with eng.begin() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER, big BIGINT, s TEXT)"))
            conn.execute(text(f"INSERT INTO t VALUES (1, {BIG}, '  a  '), (2, NULL, NULL), (3, 7, 'b')"))
        with eng.connect() as conn:
            chunks = list(_read_chunks(conn, "SELECT id, big, s FROM t WHERE id >= :lo ORDER BY id", 2, {"lo": 1}))
        assert [len(c) for c in chunks] == [2, 1]
        assert list(chunks[0].columns) == ["id", "big", "s"]
        assert chunks[0]["big"].tolist() == [BIG, None]
        assert type(chunks[0]["big"].iloc[0]) is int
        assert chunks[0]["s"].iloc[0] == "  a  "
        eng.dispose()


def test_dump_copies_values_exactly(tmp_path: Path):
    """E2E con SQLite: BIGINT > 2^53 en una columna con NULL y cadenas con espacios en los extremos."""
    ddl = "CREATE TABLE t (id INTEGER PRIMARY KEY, big BIGINT, s VARCHAR(20))"
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    with src.begin() as conn:
        conn.execute(text(ddl))
        conn.execute(text(f"INSERT INTO t VALUES (1, {BIG}, '  padded  '), (2, NULL, NULL), (3, -{BIG}, ' x')"))
    with dst.begin() as conn:
        conn.execute(text(ddl))

    result = DumpOrchestrator(DumpConfig(source_engine=src, target_engine=dst, output_dir=tmp_path)).run()

    assert [r.status for r in result.table_results] == ["success"]
    with dst.connect() as conn:
        rows = [tuple(r) for r in conn.execute(text("SELECT id, big, s FROM t ORDER BY id"))]
    assert rows == [(1, BIG, "  padded  "), (2, None, None), (3, -BIG, " x")]
    src.dispose()
    dst.dispose()


class TestOracleArraysize:
    """Q1: en Oracle, el cursor de lectura del volcado pide ``chunk_size`` filas por ida y vuelta (por defecto, 100)."""

    @staticmethod
    def _conn(dialect: str):
        from unittest.mock import MagicMock

        conn = MagicMock()
        conn.dialect.name = dialect
        return conn

    def test_oracle_raises_arraysize_only_while_executing(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        conn = self._conn("oracle")
        captured = {}
        with patch("util_bbdd.dump.orchestrator.event") as ev:
            ev.listen.side_effect = lambda target, name, fn: captured.setdefault("fn", fn)
            _execute_read(conn, "SELECT 1", 5000, None)
            assert ev.listen.call_args.args[:2] == (conn, "before_cursor_execute")
            ev.remove.assert_called_once_with(conn, "before_cursor_execute", captured["fn"])

        low = SimpleNamespace(arraysize=100, prefetchrows=2)
        captured["fn"](conn, low, "SELECT 1", {}, None, False)
        assert (low.arraysize, low.prefetchrows) == (5000, 5000)

        high = SimpleNamespace(arraysize=10000, prefetchrows=2)  # el engine ya pide más: no se baja
        captured["fn"](conn, high, "SELECT 1", {}, None, False)
        assert (high.arraysize, high.prefetchrows) == (10000, 2)

    def test_listener_is_removed_if_execute_fails(self):
        from unittest.mock import patch

        conn = self._conn("oracle")
        conn.execute.side_effect = RuntimeError("fallo")
        with patch("util_bbdd.dump.orchestrator.event") as ev, pytest.raises(RuntimeError):
            _execute_read(conn, "SELECT 1", 5000, None)
        ev.remove.assert_called_once()

    def test_other_dialects_do_not_register_listener(self):
        from unittest.mock import patch

        conn = self._conn("postgresql")
        with patch("util_bbdd.dump.orchestrator.event") as ev:
            _execute_read(conn, "SELECT 1", 5000, None)
        ev.listen.assert_not_called()
        conn.execute.assert_called_once()


class TestServerSideCursor:
    """Q2: en PostgreSQL, MySQL y MariaDB la lectura usa cursor de servidor (sin descargar la tabla entera)."""

    @pytest.mark.parametrize("dialect", ["postgresql", "mysql", "mariadb"])
    def test_client_cursor_dialects_stream_results(self, dialect):
        from unittest.mock import MagicMock

        conn = MagicMock()
        conn.dialect.name = dialect
        _execute_read(conn, "SELECT 1", 5000, {"lo": 1})

        stmt, params = conn.execute.call_args.args
        opts = stmt.get_execution_options()
        assert opts["stream_results"] is True
        assert opts["max_row_buffer"] == 5000
        assert params == {"lo": 1}

    def test_other_dialects_do_not_stream(self):
        from unittest.mock import MagicMock

        conn = MagicMock()
        conn.dialect.name = "mssql"
        _execute_read(conn, "SELECT 1", 5000, None)

        stmt = conn.execute.call_args.args[0]
        assert "stream_results" not in stmt.get_execution_options()
