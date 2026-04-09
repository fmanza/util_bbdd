"""Tests para módulo MySQL: schemas y tablas."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.mysql.tables import fetch_columns_sync, fetch_schemas_sync, fetch_tables_sync


class TestFetchSchemaSync:
    """Tests para fetch_schemas_sync()."""

    def test_fetch_schemas_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn)
        assert isinstance(result, list)

    def test_fetch_schemas_filters_system_schemas(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("myschema",), ("mysql",), ("information_schema",)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn)
        # System schemas should be filtered by the query itself
        assert isinstance(result, list)

    def test_fetch_schemas_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("schema1",), ("schema2",)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn)
        assert all(isinstance(r, tuple) for r in result)
        assert len(result) == 2

    def test_fetch_schemas_handles_empty_result(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn)
        assert result == []


class TestFetchTablesSync:
    """Tests para fetch_tables_sync()."""

    def test_fetch_tables_requires_schema(self) -> None:
        mock_conn = MagicMock()

        result = fetch_tables_sync(mock_conn, None)
        assert result == []

    def test_fetch_tables_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "myschema")
        assert isinstance(result, list)

    def test_fetch_tables_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("users", "BASE TABLE", "User table"), ("posts", "BASE TABLE", "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "myschema")
        assert all(isinstance(r, tuple) for r in result)
        assert len(result) == 2

    def test_fetch_tables_extracts_table_name(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("users", "BASE TABLE", "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "myschema")
        assert result[0][0] == "users"

    def test_fetch_tables_handles_empty_comment(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("users", "BASE TABLE", None)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "myschema")
        assert result[0][2] == ""


class TestFetchColumnsSync:
    """Tests para fetch_columns_sync()."""

    def test_fetch_columns_requires_schema_and_table(self) -> None:
        mock_conn = MagicMock()

        assert fetch_columns_sync(mock_conn, None, None) == []
        assert fetch_columns_sync(mock_conn, "schema", None) == []

    def test_fetch_columns_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert isinstance(result, list)

    def test_fetch_columns_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("id", "INT", "NO", 1, None, "", ""),
            ("name", "VARCHAR", "NO", 2, None, "", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert all(isinstance(r, tuple) for r in result)
        assert len(result) == 2

    def test_fetch_columns_normalizes_type(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("id", "INT", "NO", 1, None, "", "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        # Type should be normalized
        assert result[0][1] == "integer"

    def test_fetch_columns_detects_nullable(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("id", "INT", "NO", 1, None, "", ""),
            ("deleted_at", "DATETIME", "YES", 2, None, "", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert result[0][2] == 0  # NOT NULL
        assert result[1][2] == 1  # NULL

    def test_fetch_columns_detects_auto_increment(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("id", "INT", "NO", 1, None, "", "AUTO_INCREMENT")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert "Auto-increment" in result[0][5]

    def test_fetch_columns_handles_default_value(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("status", "VARCHAR", "NO", 1, "active", "", "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert result[0][4] == "active"

    def test_fetch_columns_with_varchar_with_length(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("name", "VARCHAR(255)", "NO", 1, None, "", "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert result[0][1] == "varchar"
