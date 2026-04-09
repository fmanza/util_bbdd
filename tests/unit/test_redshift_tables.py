"""Tests para módulo Redshift: schemas y tablas."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.redshift.tables import fetch_columns_sync, fetch_schemas_sync, fetch_tables_sync


class TestFetchSchemasSync:
    """Tests para fetch_schemas_sync()."""

    def test_fetch_schemas_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn)
        assert isinstance(result, list)

    def test_fetch_schemas_filters_system_schemas(self) -> None:
        """Debe filtrar schemas del sistema (pg_*, information_schema)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("myschema",),
            ("pg_catalog",),
            ("information_schema",),
            ("public",),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn)
        # Filtrar aquellos que comienzan con pg_
        schema_names = [s[0] for s in result]
        assert "pg_catalog" not in schema_names
        assert "information_schema" not in schema_names

    def test_fetch_schemas_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("schema1",), ("schema2",)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn)
        assert all(isinstance(r, tuple) for r in result)

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

    def test_fetch_tables_rejects_system_schema(self) -> None:
        """Debe rechazar schemas del sistema."""
        mock_conn = MagicMock()

        result = fetch_tables_sync(mock_conn, "pg_catalog")
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
        mock_cursor.fetchall.return_value = [
            ("users", "TABLE", "User table"),
            ("posts", "TABLE", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "myschema")
        assert all(isinstance(r, tuple) for r in result)
        assert len(result) == 2

    def test_fetch_tables_extracts_table_name(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("users", "TABLE", "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "myschema")
        assert result[0][0] == "users"

    def test_fetch_tables_handles_empty_comment(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("users", "TABLE", None)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "myschema")
        assert result[0][2] == ""

    def test_fetch_tables_handles_various_table_types(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("users", "TABLE", ""),
            ("views_summary", "VIEW", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "myschema")
        assert len(result) == 2


class TestFetchColumnsSync:
    """Tests para fetch_columns_sync()."""

    def test_fetch_columns_requires_schema_and_table(self) -> None:
        mock_conn = MagicMock()

        result = fetch_columns_sync(mock_conn, None, None)
        assert result == []

        result = fetch_columns_sync(mock_conn, "myschema", None)
        assert result == []

        result = fetch_columns_sync(mock_conn, None, "users")
        assert result == []

    def test_fetch_columns_rejects_system_schema(self) -> None:
        """Debe rechazar schemas del sistema."""
        mock_conn = MagicMock()

        result = fetch_columns_sync(mock_conn, "pg_catalog", "users")
        assert result == []

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
            ("id", "integer", "NO", 1, None, ""),
            ("name", "varchar", "YES", 2, None, ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert all(isinstance(r, tuple) for r in result)
        assert len(result) == 2

    def test_fetch_columns_normalizes_type(self) -> None:
        """Debe normalizar tipos Redshift a tipos genéricos."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("id", "integer", "NO", 1, None, ""),
            ("created_at", "timestamp", "YES", 2, None, ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert result[0][1] == "integer"
        assert result[1][1] == "timestamp"

    def test_fetch_columns_handles_nullable(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("id", "integer", "NO", 1, None, ""),
            ("description", "text", "YES", 2, None, ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert result[0][2] == 0  # NOT NULL
        assert result[1][2] == 1  # NULLABLE

    def test_fetch_columns_handles_default_values(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("id", "integer", "NO", 1, None, ""),
            ("created_at", "timestamp", "NO", 2, "CURRENT_TIMESTAMP", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert result[0][4] is None
        assert result[1][4] == "CURRENT_TIMESTAMP"

    def test_fetch_columns_ordered_by_position(self) -> None:
        """Las columnas deben estar ordenadas por ordinal_position."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("name", "varchar", "YES", 2, None, ""),
            ("id", "integer", "NO", 1, None, ""),
            ("email", "varchar", "YES", 3, None, ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "myschema", "users")
        assert result[0][0] == "id"  # ordinal_position=1
        assert result[1][0] == "name"  # ordinal_position=2
        assert result[2][0] == "email"  # ordinal_position=3
