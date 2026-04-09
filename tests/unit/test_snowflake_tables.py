"""Tests para introspección de schemas y tablas en Snowflake."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.snowflake.tables import fetch_columns_sync, fetch_schemas_sync, fetch_tables_sync


class TestFetchSchemasSync:
    """Tests para fetch_schemas_sync()."""

    def test_fetch_schemas_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("PUBLIC",), ("STAGING",)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn, "MYDB")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_fetch_schemas_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("PUBLIC",), ("STAGING",)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn, "MYDB")
        assert all(isinstance(row, tuple) for row in result)

    def test_fetch_schemas_normalizes_names(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Snowflake returns UPPERCASE identifiers
        mock_cursor.fetchall.return_value = [("PUBLIC",), ("staging",)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn, "MYDB")
        # First one is already uppercase, second gets normalized
        assert result[0][0] == "PUBLIC"
        assert result[1][0] == "STAGING"

    def test_fetch_schemas_excludes_system_schemas(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("INFORMATION_SCHEMA",), ("PUBLIC",), ("SNOWFLAKE",)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn, "MYDB")
        # System schemas should be filtered out
        assert len(result) == 1
        assert result[0][0] == "PUBLIC"

    def test_fetch_schemas_empty_database(self) -> None:
        result = fetch_schemas_sync(MagicMock(), None)
        assert result == []

    def test_fetch_schemas_no_connection(self) -> None:
        result = fetch_schemas_sync(None, "MYDB")
        assert result == []


class TestFetchTablesSync:
    """Tests para fetch_tables_sync()."""

    def test_fetch_tables_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("CUSTOMERS", "BASE TABLE", "Customer records"),
            ("ORDERS", "VIEW", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "MYDB", "PUBLIC")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_fetch_tables_returns_tuples_with_3_elements(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("CUSTOMERS", "BASE TABLE", "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "MYDB", "PUBLIC")
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_fetch_tables_includes_table_type(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("CUSTOMERS", "BASE TABLE", "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "MYDB", "PUBLIC")
        table_name, table_type, comment = result[0]
        assert table_type == "BASE TABLE"

    def test_fetch_tables_includes_comment(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("CUSTOMERS", "BASE TABLE", "Customer table")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, "MYDB", "PUBLIC")
        table_name, table_type, comment = result[0]
        assert comment == "Customer table"

    def test_fetch_tables_empty_schema(self) -> None:
        result = fetch_tables_sync(MagicMock(), "MYDB", None)
        assert result == []

    def test_fetch_tables_no_database(self) -> None:
        result = fetch_tables_sync(MagicMock(), None, "PUBLIC")
        assert result == []

    def test_fetch_tables_system_schema_excluded(self) -> None:
        result = fetch_tables_sync(MagicMock(), "MYDB", "INFORMATION_SCHEMA")
        assert result == []


class TestFetchColumnsSync:
    """Tests para fetch_columns_sync()."""

    def test_fetch_columns_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("ID", "NUMBER", "NO", 1, None, "Primary Key"),
            ("NAME", "VARCHAR", "YES", 2, "'Unknown'", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_fetch_columns_returns_tuples_with_6_elements(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("ID", "INT", "NO", 1, None, "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        assert len(result) == 1
        assert len(result[0]) == 6

    def test_fetch_columns_normalizes_type(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("ID", "NUMBER(10, 0)", "NO", 1, None, "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        col_name, col_type, is_nullable, ordinal, default, comment = result[0]
        # NUMBER should normalize to numeric
        assert col_type == "numeric"

    def test_fetch_columns_is_nullable_yes(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("NAME", "VARCHAR", "YES", 1, None, "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        col_name, col_type, is_nullable, ordinal, default, comment = result[0]
        assert is_nullable is True

    def test_fetch_columns_is_nullable_no(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("ID", "NUMBER", "NO", 1, None, "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        col_name, col_type, is_nullable, ordinal, default, comment = result[0]
        assert is_nullable is False

    def test_fetch_columns_ordinal_position(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("ID", "NUMBER", "NO", 1, None, ""),
            ("NAME", "VARCHAR", "YES", 2, None, ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        # Should be sorted by ordinal position
        assert result[0][3] == 1  # First column ordinal
        assert result[1][3] == 2  # Second column ordinal

    def test_fetch_columns_default_value(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("STATUS", "VARCHAR", "YES", 1, "'ACTIVE'", "")]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        col_name, col_type, is_nullable, ordinal, default, comment = result[0]
        assert default == "'ACTIVE'"

    def test_fetch_columns_empty_table(self) -> None:
        result = fetch_columns_sync(MagicMock(), "MYDB", "PUBLIC", None)
        assert result == []

    def test_fetch_columns_no_database(self) -> None:
        result = fetch_columns_sync(MagicMock(), None, "PUBLIC", "TABLE1")
        assert result == []

    def test_fetch_columns_system_schema_excluded(self) -> None:
        result = fetch_columns_sync(MagicMock(), "MYDB", "INFORMATION_SCHEMA", "TABLES")
        assert result == []

    def test_fetch_columns_semi_structured_types(self) -> None:
        """Test that VARIANT, OBJECT, ARRAY types are normalized."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("DATA", "VARIANT", "YES", 1, None, ""),
            ("TAGS", "ARRAY", "YES", 2, None, ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        assert result[0][1] == "object"  # VARIANT -> object
        assert result[1][1] == "object"  # ARRAY -> object
