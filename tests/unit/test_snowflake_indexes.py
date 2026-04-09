"""Tests para introspección de índices en Snowflake (stubs)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from util_bbdd.metadata.snowflake.indexes import fetch_indexes_sync


class TestFetchIndexesSync:
    """Tests para fetch_indexes_sync()."""

    def test_fetch_indexes_returns_empty_list(self) -> None:
        """Snowflake has no native indexes; should always return empty list."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
        assert isinstance(result, list)
        assert result == []

    def test_fetch_indexes_with_no_database(self) -> None:
        result = fetch_indexes_sync(MagicMock(), None, "PUBLIC", "TABLE1")
        assert result == []

    def test_fetch_indexes_with_no_schema(self) -> None:
        result = fetch_indexes_sync(MagicMock(), "MYDB", None, "TABLE1")
        assert result == []

    def test_fetch_indexes_with_no_table(self) -> None:
        result = fetch_indexes_sync(MagicMock(), "MYDB", "PUBLIC", None)
        assert result == []

    def test_fetch_indexes_system_schema_excluded(self) -> None:
        result = fetch_indexes_sync(MagicMock(), "MYDB", "INFORMATION_SCHEMA", "TABLES")
        assert result == []

    def test_fetch_indexes_logs_info_message(self) -> None:
        """Verify that an informational message is logged about using CLUSTERING KEY."""
        mock_conn = MagicMock()

        with patch("util_bbdd.metadata.snowflake.indexes.logger") as mock_logger:
            fetch_indexes_sync(mock_conn, "MYDB", "PUBLIC", "CUSTOMERS")
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "CLUSTERING KEY" in call_args

    def test_fetch_indexes_message_includes_context(self) -> None:
        """Verify that log message includes database, schema, and table."""
        mock_conn = MagicMock()

        with patch("util_bbdd.metadata.snowflake.indexes.logger") as mock_logger:
            fetch_indexes_sync(mock_conn, "TESTDB", "TESTSCHEMA", "TESTTABLE")
            mock_logger.info.assert_called_once()
            args = mock_logger.info.call_args
            # Check that the format includes the context parameters
            assert "TESTDB" in str(args)
            assert "TESTSCHEMA" in str(args)
            assert "TESTTABLE" in str(args)

    def test_fetch_indexes_multiple_calls_return_consistent_empty(self) -> None:
        """Multiple calls should always return empty list."""
        mock_conn = MagicMock()

        result1 = fetch_indexes_sync(mock_conn, "MYDB", "PUBLIC", "TABLE1")
        result2 = fetch_indexes_sync(mock_conn, "MYDB", "PUBLIC", "TABLE2")
        result3 = fetch_indexes_sync(mock_conn, "MYDB", "PUBLIC", "TABLE3")

        assert result1 == []
        assert result2 == []
        assert result3 == []

    def test_fetch_indexes_regardless_of_connection_state(self) -> None:
        """Should return empty list even if connection has issues."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Connection error")

        # Should not raise, but return empty
        result = fetch_indexes_sync(mock_conn, "MYDB", "PUBLIC", "TABLE1")
        assert result == []

    def test_fetch_indexes_design_note(self) -> None:
        """
        Snowflake does not have native indexes.
        For query optimization, use CLUSTERING KEY.
        This stub ensures compatibility with other drivers.
        """
        # This test documents the design decision
        mock_conn = MagicMock()
        result = fetch_indexes_sync(mock_conn, "MYDB", "PUBLIC", "TABLE1")

        # Empty list is the correct behavior
        assert result == []
        assert isinstance(result, list)
