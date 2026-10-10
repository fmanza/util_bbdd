"""Filas de driver que no son ``tuple`` en ``ResultNormalizer`` (hotfix de 1.1.0).

``pyodbc.Row`` (SQL Server con ``sql_server_driver="pyodbc"`` en sync y con aioodbc en async) es una secuencia pero no
una ``tuple``. Hasta v1.0.0 ``_as_row`` la envolvía en otra tupla: ``execute_custom_one`` devolvía ``((1, 'a'),)`` y
``execute_custom_many`` una sola «fila» con todas las filas dentro (``[(('a',), ('b',))]``).
"""

from __future__ import annotations

import sqlite3

from contextlib import closing
from typing import Any

import pytest

from util_bbdd.results import ResultNormalizer


class FakePyodbcRow:
    """Como ``pyodbc.Row``: ``__len__`` y ``__getitem__`` sin ``__iter__`` (se itera por índice), no ``tuple``."""

    cursor_description = (("x", int, None, None, None, None, True),)

    def __init__(self, *values: Any) -> None:
        self._values = values

    def __len__(self) -> int:
        return len(self._values)

    def __getitem__(self, index: int) -> Any:
        return self._values[index]

    def __repr__(self) -> str:
        return repr(self._values)


def test_driver_row_is_converted_to_a_tuple() -> None:
    assert ResultNormalizer.normalize_one(FakePyodbcRow(1, "a")) == (1, "a")


def test_list_of_driver_rows_keeps_one_tuple_per_row() -> None:
    rows = [FakePyodbcRow("a"), FakePyodbcRow("b")]

    assert ResultNormalizer.normalize_many(rows) == [("a",), ("b",)]


def test_sqlite3_row_factory_rows_are_tuples() -> None:
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT 1 AS x, 'a' AS y UNION ALL SELECT 2, 'b'").fetchall()

    assert ResultNormalizer.normalize_one(rows[0]) == (1, "a")
    assert ResultNormalizer.normalize_many(rows) == [(1, "a"), (2, "b")]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ((1, 2), (1, 2)),
        ([1, 2], (1, 2)),
        ("texto", ("texto",)),
        (b"bytes", (b"bytes",)),
        ({"x": 1}, ({"x": 1},)),
        (7, (7,)),
    ],
)
def test_scalars_strings_bytes_and_mappings_are_still_a_single_value(value: Any, expected: tuple[Any, ...]) -> None:
    assert ResultNormalizer.normalize_one(value) == expected


def test_flat_collection_of_scalars_is_still_one_row() -> None:
    assert ResultNormalizer.normalize_many([1, 2, 3]) == [(1, 2, 3)]
    assert ResultNormalizer.normalize_many(["a", "b"]) == [("a", "b")]
