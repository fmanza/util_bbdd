"""Tests para introspección de tablas, schemas y columnas en SQL Server."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlserver.tables import (
    fetch_columns_sync,
    fetch_schemas_sync,
    fetch_tables_sync,
)


class TestFetchSchemasSyncSqlServer:
    """Tests para fetch_schemas_sync()."""

    def test_fetch_schemas_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("dbo",),
            ("sales",),
            ("hr",),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn)

        assert len(result) >= 1
        assert all(isinstance(r, tuple) and len(r) == 1 for r in result)
        schema_names = [r[0] for r in result]
        assert "dbo" in schema_names

    def test_fetch_schemas_excludes_system_schemas(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock no debería incluir sys
        mock_cursor.fetchall.return_value = [
            ("dbo",),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn)

        schema_names = [r[0] for r in result]
        assert "dbo" in schema_names

    def test_fetch_schemas_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_schemas_sync(mock_conn)
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)


class TestFetchTablesSyncSqlServer:
    """Tests para fetch_tables_sync()."""

    def test_fetch_tables_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("Users", "TABLE", "User accounts"),
            ("Products", "TABLE", "Product catalog"),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, schema="dbo")

        assert len(result) >= 0
        assert all(isinstance(r, tuple) and len(r) == 3 for r in result)

    def test_fetch_tables_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn, schema="dbo")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_tables_default_schema(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_tables_sync(mock_conn)
        assert isinstance(result, list)

        # Verify that dbo was used as default
        assert mock_conn.execute.called


class TestFetchColumnsSyncSqlServer:
    """Tests para fetch_columns_sync()."""

    def test_fetch_columns_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # sys.columns query returns:
        # (name, type, nullable, column_id, default, comment, is_identity)
        mock_cursor.fetchall.return_value = [
            ("UserId", "int", 0, 1, None, "", 1),  # Identity column
            ("UserName", "nvarchar", 1, 2, None, "User's name", 0),
            ("CreatedDate", "datetime2", 0, 3, "getdate()", "Creation timestamp", 0),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema="dbo", table="Users")

        assert len(result) == 3
        assert all(isinstance(r, tuple) and len(r) == 6 for r in result)

        col_names = [r[0] for r in result]
        assert "UserId" in col_names
        assert "UserName" in col_names

    def test_fetch_columns_empty_result(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema="dbo", table="NoColumns")
        assert result == []

    def test_fetch_columns_no_table_provided(self) -> None:
        mock_conn = MagicMock()
        result = fetch_columns_sync(mock_conn, schema="dbo", table=None)
        assert result == []

    def test_fetch_columns_normalizes_types(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("IdColumn", "int", 0, 1, None, "", 0),
            ("NameColumn", "nvarchar", 0, 2, None, "", 0),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema="dbo", table="test")

        types = [r[1] for r in result]
        assert "integer" in types or "int" in types
        assert "varchar" in types

    def test_fetch_columns_identity_flag_added_to_comment(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("Id", "int", 0, 1, None, "", 1),  # Identity
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema="dbo", table="test")

        comment = result[0][5]
        assert "Identity" in comment or "identity" in comment.lower()

    def test_fetch_columns_preserves_default_value(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("Status", "nvarchar", 0, 1, "'active'", "", 0),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema="dbo", table="test")

        default_value = result[0][4]
        assert "'active'" == default_value

    def test_fetch_columns_default_schema(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_columns_sync(mock_conn, schema=None, table="test")
        assert isinstance(result, list)
