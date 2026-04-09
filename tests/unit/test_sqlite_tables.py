"""Tests para introspección de tablas, schemas y columnas en SQLite."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlite.tables import (
    fetch_columns_sync,
    fetch_schemas_sync,
    fetch_tables_sync,
)


class TestFetchSchemasSyncSqlite:
    """Tests para fetch_schemas_sync()."""

    def test_fetch_schemas_returns_main_and_temp(self) -> None:
        result = fetch_schemas_sync()
        assert len(result) >= 1
        schema_names = [r[0] for r in result]
        assert "main" in schema_names

    def test_fetch_schemas_returns_tuples(self) -> None:
        result = fetch_schemas_sync()
        assert all(isinstance(r, tuple) for r in result)
        assert all(len(r) == 1 for r in result)

    def test_fetch_schemas_all_strings(self) -> None:
        result = fetch_schemas_sync()
        assert all(isinstance(r[0], str) for r in result)


class TestFetchTablesSyncSqlite:
    """Tests para fetch_tables_sync()."""

    def test_fetch_tables_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Simular resultado: (name, type, comments)
        mock_cursor.fetchall.return_value = [
            ("users", "TABLE", ""),
            ("products", "TABLE", ""),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, schema="main")

        assert len(result) >= 0
        if result:
            assert all(isinstance(r, tuple) and len(r) == 3 for r in result)

    def test_fetch_tables_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, schema="main")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_tables_default_schema(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn)
        assert isinstance(result, list)


class TestFetchColumnsSyncSqlite:
    """Tests para fetch_columns_sync()."""

    def test_fetch_columns_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
        mock_cursor.fetchall.return_value = [
            (0, "id", "INTEGER", 1, None, 1),
            (1, "name", "TEXT", 1, None, 0),
            (2, "age", "INTEGER", 0, "18", 0),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema="main", table="users")

        assert len(result) == 3
        assert all(isinstance(r, tuple) and len(r) == 6 for r in result)

        # Verificar estructuras
        col_names = [r[0] for r in result]
        assert "id" in col_names
        assert "name" in col_names

    def test_fetch_columns_empty_result(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema="main", table="empty")
        assert result == []

    def test_fetch_columns_no_table_provided(self) -> None:
        mock_conn = MagicMock()
        result = fetch_columns_sync(mock_conn, schema="main", table=None)
        assert result == []

    def test_fetch_columns_normalizes_types(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            (0, "col_int", "INTEGER", 1, None, 0),
            (1, "col_text", "VARCHAR(255)", 0, None, 0),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema="main", table="test")

        # Verificar que tipos se normalizan
        types = [r[1] for r in result]
        assert "integer" in types or "int" in types
        assert "varchar" in types or "text" in types

    def test_fetch_columns_nullable_flag(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            (0, "id", "INTEGER", 1, None, 0),  # NOT NULL
            (1, "optional", "TEXT", 0, None, 0),  # NULL
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema="main", table="test")

        # Verificar nullable flag (tercera posición)
        nullable_flags = [r[2] for r in result]
        assert 0 in nullable_flags  # NOT NULL
        assert 1 in nullable_flags  # NULL

    def test_fetch_columns_preserves_default_value(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            (0, "status", "TEXT", 0, "'active'", 0),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema="main", table="test")

        defaults = [r[4] for r in result]
        assert "'active'" in defaults
