"""Tests de regresión MSS-03: PRAGMA con identificadores no triviales sobre conexión real.

A diferencia del resto de la suite SQLite (que mockea `cursor.fetchall`), estos tests ejecutan
las queries generadas contra `sqlite3.connect(":memory:")` real, para detectar que la
interpolación cruda con corchetes (`[nombre]`) no escapa un `]` embebido en el propio
identificador.
"""

from __future__ import annotations

import sqlite3

from collections.abc import Iterator

import pytest

from util_bbdd.metadata.sqlite.constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync
from util_bbdd.metadata.sqlite.indexes import fetch_indexes_sync
from util_bbdd.metadata.sqlite.routines import fetch_triggers_sync
from util_bbdd.metadata.sqlite.tables import fetch_columns_sync, fetch_tables_sync


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    try:
        yield connection
    finally:
        connection.close()


class TestFetchTablesRealConnection:
    def test_fetch_tables_with_bracket_in_table_name(self, conn: sqlite3.Connection) -> None:
        conn.execute('CREATE TABLE "weird]table" (id INTEGER PRIMARY KEY)')

        result = fetch_tables_sync(conn, schema="main")

        assert any(r[0] == "weird]table" for r in result)


class TestFetchColumnsRealConnection:
    def test_fetch_columns_with_bracket_in_table_and_column_name(self, conn: sqlite3.Connection) -> None:
        conn.execute('CREATE TABLE "weird]table" (id INTEGER PRIMARY KEY, "col]x" TEXT)')

        result = fetch_columns_sync(conn, schema="main", table="weird]table")

        col_names = [r[0] for r in result]
        assert "col]x" in col_names
        assert "id" in col_names


class TestFetchPrimaryKeysRealConnection:
    def test_fetch_primary_keys_with_bracket_in_table_name(self, conn: sqlite3.Connection) -> None:
        conn.execute('CREATE TABLE "pk]table" (id INTEGER PRIMARY KEY)')

        result = fetch_primary_keys_sync(conn, schema="main", table="pk]table")

        assert result
        assert result[0][1] == "id"


class TestFetchForeignKeysRealConnection:
    def test_fetch_foreign_keys_with_bracket_in_table_name(self, conn: sqlite3.Connection) -> None:
        conn.execute('CREATE TABLE "parent]t" (id INTEGER PRIMARY KEY)')
        conn.execute(
            'CREATE TABLE "child]t" ('
            "id INTEGER PRIMARY KEY, parent_id INTEGER, "
            'FOREIGN KEY(parent_id) REFERENCES "parent]t"(id))'
        )

        result = fetch_foreign_keys_sync(conn, schema="main", table="child]t")

        assert result
        assert result[0][2] == "parent]t"


class TestFetchIndexesRealConnection:
    def test_fetch_indexes_with_bracket_in_table_name(self, conn: sqlite3.Connection) -> None:
        conn.execute('CREATE TABLE "idx]table" (id INTEGER, val TEXT)')
        conn.execute('CREATE INDEX "idx]table_val" ON "idx]table" (val)')

        result = fetch_indexes_sync(conn, schema="main", table="idx]table")

        assert result
        assert any(r[0] == "idx]table_val" for r in result)


class TestFetchTriggersRealConnection:
    def test_fetch_triggers_with_bracket_in_table_name(self, conn: sqlite3.Connection) -> None:
        conn.execute('CREATE TABLE "trg]table" (id INTEGER)')
        conn.execute('CREATE TRIGGER "trg]table_ai" AFTER INSERT ON "trg]table" BEGIN SELECT 1; END')

        result = fetch_triggers_sync(conn, schema="main", table="trg]table")

        assert result
        assert result[0][1] == "trg]table"
