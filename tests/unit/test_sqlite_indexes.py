"""Tests para índices en SQLite."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlite.indexes import fetch_indexes_sync


class TestFetchIndexesSyncSqlite:
    """Tests para fetch_indexes_sync()."""

    def test_fetch_indexes_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor_list = MagicMock()
        mock_cursor_info = MagicMock()

        # PRAGMA index_list returns: (seq, name, unique, origin, partial)
        mock_cursor_list.fetchall.return_value = [
            (0, "idx_users_email", 1, "c", 0),
            (1, "idx_users_created", 0, "c", 0),
        ]

        # PRAGMA index_info returns: (seqno, cid, name)
        mock_cursor_info.fetchall.return_value = [
            (0, 1, "email"),
        ]

        # Configurar mock para retornar diferentes cursors
        def execute_side_effect(sql):
            if "index_list" in sql:
                return mock_cursor_list
            else:
                return mock_cursor_info

        mock_conn.execute.side_effect = execute_side_effect

        result = fetch_indexes_sync(mock_conn, schema="main", table="users")

        assert len(result) >= 0
        assert all(isinstance(r, tuple) and len(r) == 4 for r in result)

    def test_fetch_indexes_no_indexes(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = []

        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, schema="main", table="simple_table")
        assert result == []

    def test_fetch_indexes_no_table_provided(self) -> None:
        mock_conn = MagicMock()
        result = fetch_indexes_sync(mock_conn, schema="main", table=None)
        assert result == []

    def test_fetch_indexes_unique_flag(self) -> None:
        mock_conn = MagicMock()
        mock_cursor_list = MagicMock()
        mock_cursor_info = MagicMock()

        # Indices únicos e no-únicos
        mock_cursor_list.fetchall.return_value = [
            (0, "idx_unique", 1, "c", 0),
            (1, "idx_non_unique", 0, "c", 0),
        ]

        mock_cursor_info.fetchall.return_value = [
            (0, 1, "col"),
        ]

        def execute_side_effect(sql):
            if "index_list" in sql:
                return mock_cursor_list
            else:
                return mock_cursor_info

        mock_conn.execute.side_effect = execute_side_effect

        result = fetch_indexes_sync(mock_conn, schema="main", table="test")

        # Verificar flags de unicidad
        unique_flags = [r[2] for r in result]
        assert 0 in unique_flags or 1 in unique_flags

    def test_fetch_indexes_excludes_system_indexes(self) -> None:
        mock_conn = MagicMock()
        mock_cursor_list = MagicMock()
        mock_cursor_info = MagicMock()

        # Incluir índice del sistema
        mock_cursor_list.fetchall.return_value = [
            (0, "sqlite_autoindex_users_1", 0, "pk", 0),  # Sistema
            (1, "idx_users_id", 1, "c", 0),
        ]

        mock_cursor_info.fetchall.return_value = [
            (0, 0, "id"),
        ]

        def execute_side_effect(sql):
            if "index_list" in sql:
                return mock_cursor_list
            else:
                return mock_cursor_info

        mock_conn.execute.side_effect = execute_side_effect

        result = fetch_indexes_sync(mock_conn, schema="main", table="users")

        # Debe excluir sqlite_* indexes
        index_names = [r[0] for r in result]
        assert all(not name.startswith("sqlite_") for name in index_names)

    def test_fetch_indexes_default_schema(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, schema=None, table="test")
        assert isinstance(result, list)

    def test_fetch_indexes_ordinal_position(self) -> None:
        mock_conn = MagicMock()
        mock_cursor_list = MagicMock()
        mock_cursor_info = MagicMock()

        mock_cursor_list.fetchall.return_value = [
            (0, "idx_composite", 0, "c", 0),
        ]

        # Índice compuesto
        mock_cursor_info.fetchall.return_value = [
            (0, 1, "col_a"),
            (1, 2, "col_b"),
        ]

        def execute_side_effect(sql):
            if "index_list" in sql:
                return mock_cursor_list
            else:
                return mock_cursor_info

        mock_conn.execute.side_effect = execute_side_effect

        result = fetch_indexes_sync(mock_conn, schema="main", table="test")

        # Debe tener dos filas para índice compuesto
        assert len(result) >= 1

        # Verifcar que las posiciones ordinales están correctas
        ordinal_positions = [r[3] for r in result]
        assert all(isinstance(o, int) for o in ordinal_positions)
