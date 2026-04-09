"""Tests para módulo MySQL: índices."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.mysql.indexes import fetch_indexes_sync


class TestFetchIndexesSync:
    """Tests para fetch_indexes_sync()."""

    def test_fetch_indexes_requires_schema_and_table(self) -> None:
        mock_conn = MagicMock()

        assert fetch_indexes_sync(mock_conn, None, None) == []
        assert fetch_indexes_sync(mock_conn, "schema", None) == []

    def test_fetch_indexes_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert isinstance(result, list)

    def test_fetch_indexes_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("idx_email", "email", 1, 0)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_indexes_extracts_index_info(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("idx_email", "email", 1, 0)]  # NON_UNIQUE=0 means unique
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        row = result[0]
        assert row[0] == "idx_email"
        assert row[1] == "email"
        assert row[2] == 1  # seq_in_index
        assert row[3] == 1  # is_unique (NON_UNIQUE=0 -> unique)

    def test_fetch_indexes_unique_index_flag(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # NON_UNIQUE: 0 = unique, 1 = non-unique
        # When NON_UNIQUE=0, is_unique should be 1
        mock_cursor.fetchall.return_value = [("idx_email", "email", 1, 0)]  # unique
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert result[0][3] == 1  # IS unique

    def test_fetch_indexes_composite_index(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("idx_name", "first_name", 1, 1),
            ("idx_name", "last_name", 2, 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert len(result) == 2
        assert result[0][0] == "idx_name"
        assert result[1][0] == "idx_name"

    def test_fetch_indexes_multiple_indexes(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("idx_email", "email", 1, 0),
            ("idx_status", "status", 1, 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert len(result) == 2

    def test_fetch_indexes_handles_empty_result(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert result == []
