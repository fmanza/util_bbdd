"""Tests para introspección de constraints en Snowflake."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from util_bbdd.metadata.snowflake.constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync


class TestFetchPrimaryKeysSync:
    """Tests para fetch_primary_keys_sync()."""

    def test_fetch_primary_keys_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("PK_CUSTOMERS", "ID", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        assert isinstance(result, list)

    def test_fetch_primary_keys_returns_tuples_with_3_elements(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("PK_CUSTOMERS", "ID", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_fetch_primary_keys_multiple_columns(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("PK_ORDERS", "ORDER_ID", 1),
            ("PK_ORDERS", "CUSTOMER_ID", 2),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "MYDB", "PUBLIC", "ORDERS")
        assert len(result) == 2

    def test_fetch_primary_keys_sorted_by_ordinal(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("PK_TEST", "COL2", 2),
            ("PK_TEST", "COL1", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "MYDB", "PUBLIC", "TEST")
        # Should be sorted by ordinal position
        assert result[0][2] == 1
        assert result[1][2] == 2

    def test_fetch_primary_keys_logs_warning(self) -> None:
        """Verify that a warning is logged about advisory constraint."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("PK_TEST", "ID", 1)]
        mock_conn.execute.return_value = mock_cursor

        with patch("util_bbdd.metadata.snowflake.constraints.logger") as mock_logger:
            fetch_primary_keys_sync(mock_conn, "MYDB", "PUBLIC", "TEST")
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "ADVISORY" in call_args

    def test_fetch_primary_keys_empty_database(self) -> None:
        result = fetch_primary_keys_sync(MagicMock(), None, "PUBLIC", "TABLE1")
        assert result == []

    def test_fetch_primary_keys_empty_schema(self) -> None:
        result = fetch_primary_keys_sync(MagicMock(), "MYDB", None, "TABLE1")
        assert result == []

    def test_fetch_primary_keys_empty_table(self) -> None:
        result = fetch_primary_keys_sync(MagicMock(), "MYDB", "PUBLIC", None)
        assert result == []

    def test_fetch_primary_keys_system_schema_excluded(self) -> None:
        result = fetch_primary_keys_sync(MagicMock(), "MYDB", "INFORMATION_SCHEMA", "TABLES")
        assert result == []

    def test_fetch_primary_keys_connection_error_returns_empty(self) -> None:
        """If query fails, should return empty list."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Connection error")

        result = fetch_primary_keys_sync(mock_conn, "MYDB", "PUBLIC", "TABLE1")
        assert result == []


class TestFetchForeignKeysSync:
    """Tests para fetch_foreign_keys_sync()."""

    def test_fetch_foreign_keys_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("FK_ORDERS_CUSTOMER", "CUSTOMER_ID", "CUSTOMERS", "ID", "NO ACTION", "CASCADE", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "MYDB", "PUBLIC", "ORDERS")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_fetch_foreign_keys_returns_tuples_with_7_elements(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("FK_ORDERS_CUSTOMER", "CUSTOMER_ID", "CUSTOMERS", "ID", "NO ACTION", "CASCADE", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "MYDB", "PUBLIC", "ORDERS")
        assert len(result[0]) == 7

    def test_fetch_foreign_keys_includes_referenced_table(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("FK_ORDERS_CUSTOMER", "CUSTOMER_ID", "CUSTOMERS", "ID", "NO ACTION", "CASCADE", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "MYDB", "PUBLIC", "ORDERS")
        constraint_name, col_name, ref_table, ref_col, on_delete, on_update, ordinal = result[0]
        assert ref_table == "CUSTOMERS"
        assert ref_col == "ID"

    def test_fetch_foreign_keys_includes_actions(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("FK_ORDERS_CUSTOMER", "CUSTOMER_ID", "CUSTOMERS", "ID", "SET NULL", "CASCADE", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "MYDB", "PUBLIC", "ORDERS")
        constraint_name, col_name, ref_table, ref_col, on_delete, on_update, ordinal = result[0]
        # Element 4 is on_update_action, element 5 is on_delete_action
        assert on_delete == "CASCADE"  # 5th element (on_delete_action) = rv[5]
        assert on_update == "SET NULL"  # 4th element (on_update_action) = rv[4]

    def test_fetch_foreign_keys_multiple_columns(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("FK_ORDERS_CUSTOMER", "CUSTOMER_ID", "CUSTOMERS", "ID", "NO ACTION", "CASCADE", 1),
            ("FK_ORDERS_PRODUCT", "PRODUCT_ID", "PRODUCTS", "ID", "NO ACTION", "CASCADE", 2),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "MYDB", "PUBLIC", "ORDERS")
        assert len(result) == 2

    def test_fetch_foreign_keys_sorted_by_ordinal(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("FK_TEST", "COL2", "REF_TABLE", "REF_COL", "NO ACTION", "CASCADE", 2),
            ("FK_TEST", "COL1", "REF_TABLE", "REF_COL", "NO ACTION", "CASCADE", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "MYDB", "PUBLIC", "TEST")
        assert result[0][6] == 1  # First ordinal
        assert result[1][6] == 2  # Second ordinal

    def test_fetch_foreign_keys_logs_warning(self) -> None:
        """Verify that a warning is logged about advisory constraint."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        with patch("util_bbdd.metadata.snowflake.constraints.logger") as mock_logger:
            fetch_foreign_keys_sync(mock_conn, "MYDB", "PUBLIC", "TEST")
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "ADVISORY" in call_args

    def test_fetch_foreign_keys_empty_database(self) -> None:
        result = fetch_foreign_keys_sync(MagicMock(), None, "PUBLIC", "TABLE1")
        assert result == []

    def test_fetch_foreign_keys_empty_schema(self) -> None:
        result = fetch_foreign_keys_sync(MagicMock(), "MYDB", None, "TABLE1")
        assert result == []

    def test_fetch_foreign_keys_empty_table(self) -> None:
        result = fetch_foreign_keys_sync(MagicMock(), "MYDB", "PUBLIC", None)
        assert result == []

    def test_fetch_foreign_keys_system_schema_excluded(self) -> None:
        result = fetch_foreign_keys_sync(MagicMock(), "MYDB", "SNOWFLAKE", "OBJECTS")
        assert result == []

    def test_fetch_foreign_keys_connection_error_returns_empty(self) -> None:
        """If query fails, should return empty list."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Connection error")

        result = fetch_foreign_keys_sync(mock_conn, "MYDB", "PUBLIC", "TABLE1")
        assert result == []

    def test_fetch_foreign_keys_incomplete_row_skipped(self) -> None:
        """Rows with fewer than 7 elements should be skipped."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("FK_TEST", "COL1", "REF_TABLE", "REF_COL", "NO ACTION"),  # Only 5 elements
            ("FK_TEST", "COL2", "REF_TABLE", "REF_COL", "NO ACTION", "CASCADE", 1),  # 7 elements
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "MYDB", "PUBLIC", "TEST")
        # Only the complete row should be returned
        assert len(result) == 1
