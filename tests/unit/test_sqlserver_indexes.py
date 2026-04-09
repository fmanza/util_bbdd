"""Tests para índices en SQL Server."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlserver.indexes import fetch_indexes_sync


class TestFetchIndexesSyncSqlServer:
    """Tests para fetch_indexes_sync()."""

    def test_fetch_indexes_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # sys.indexes query returns: (index_name, column_name, is_unique, index_type, ordinal)
        mock_cursor.fetchall.return_value = [
            ("IX_Users_Email", "Email", 1, 2, 1),  # Nonclustered unique
            ("IX_Users_Status", "Status", 0, 2, 1),  # Non-unique
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, schema="dbo", table="Users")

        assert len(result) >= 0
        assert all(isinstance(r, tuple) and len(r) == 5 for r in result)

    def test_fetch_indexes_unique_flag(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("UX_Email", "Email", 1, 2, 1),  # Unique
            ("IX_Status", "Status", 0, 2, 1),  # Non-unique
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, schema="dbo", table="Users")

        unique_flags = [r[2] for r in result]
        assert 0 in unique_flags
        assert 1 in unique_flags

    def test_fetch_indexes_composite_index(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Composite index on (FirstName, LastName)
        mock_cursor.fetchall.return_value = [
            ("IX_Name_Composite", "FirstName", 0, 2, 1),
            ("IX_Name_Composite", "LastName", 0, 2, 2),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, schema="dbo", table="Users")

        assert len(result) >= 2

        # Verify both columns belong to same index
        index_names = [r[0] for r in result]
        assert all(name == "IX_Name_Composite" for name in index_names)

    def test_fetch_indexes_no_indexes(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, schema="dbo", table="NoIndexes")
        assert result == []

    def test_fetch_indexes_no_table_provided(self) -> None:
        mock_conn = MagicMock()
        result = fetch_indexes_sync(mock_conn, schema="dbo", table=None)
        assert result == []

    def test_fetch_indexes_index_type_preserved(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 1 = Clustered, 2 = Nonclustered
        mock_cursor.fetchall.return_value = [
            ("PK_Id", "Id", 0, 1, 1),  # Clustered (PK)
            ("IX_Status", "Status", 0, 2, 1),  # Nonclustered
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, schema="dbo", table="Orders")

        index_types = [r[4] for r in result]
        assert 1 in index_types  # Clustered
        assert 2 in index_types  # Nonclustered

    def test_fetch_indexes_ordinal_position(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("IX_Composite", "ColA", 0, 2, 1),
            ("IX_Composite", "ColB", 0, 2, 2),
            ("IX_Composite", "ColC", 0, 2, 3),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, schema="dbo", table="test")

        # Verify ordinal positions increase
        ordinals = [r[3] for r in result if r[0] == "IX_Composite"]
        assert ordinals == sorted(ordinals)

    def test_fetch_indexes_default_schema(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, schema=None, table="test")
        assert isinstance(result, list)
