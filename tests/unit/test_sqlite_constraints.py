"""Tests para constraints (PK, FK) en SQLite."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlite.constraints import (
    fetch_foreign_keys_sync,
    fetch_primary_keys_sync,
)


class TestFetchPrimaryKeysSyncSqlite:
    """Tests para fetch_primary_keys_sync()."""

    def test_fetch_pk_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
        # pk > 0 indica que la columna es parte de PK
        mock_cursor.fetchall.return_value = [
            (0, "id", "INTEGER", 1, None, 1),  # PK
            (1, "name", "TEXT", 1, None, 0),
            (2, "org_id", "INTEGER", 0, None, 2),  # Composite PK (second position)
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, schema="main", table="users")

        assert len(result) == 2
        assert all(isinstance(r, tuple) and len(r) == 3 for r in result)

        # Verificar nombre de constraint y columna
        pk_columns = [r[1] for r in result]
        assert "id" in pk_columns

    def test_fetch_pk_no_primary_key(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Sin columnas con pk > 0
        mock_cursor.fetchall.return_value = [
            (0, "name", "TEXT", 0, None, 0),
            (1, "value", "REAL", 0, None, 0),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, schema="main", table="nokey")
        assert result == []

    def test_fetch_pk_no_table_provided(self) -> None:
        mock_conn = MagicMock()
        result = fetch_primary_keys_sync(mock_conn, schema="main", table=None)
        assert result == []

    def test_fetch_pk_returns_sorted_by_position(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            (0, "col_a", "INTEGER", 1, None, 2),
            (1, "col_b", "INTEGER", 1, None, 1),
            (2, "col_c", "TEXT", 0, None, 0),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, schema="main", table="compound_pk")

        # Debe estar ordenado por ordinal position
        positions = [r[2] for r in result]
        assert positions == sorted(positions)


class TestFetchForeignKeysSyncSqlite:
    """Tests para fetch_foreign_keys_sync()."""

    def test_fetch_fk_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # PRAGMA foreign_key_list returns:
        # (id, seq, table, from, to, on_delete, on_update, match)
        mock_cursor.fetchall.return_value = [
            (0, 0, "organizations", "org_id", "id", "CASCADE", "CASCADE", "NONE"),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema="main", table="users")

        assert len(result) == 1
        assert all(isinstance(r, tuple) and len(r) == 7 for r in result)

        # Verificar estructura: (constraint_name, column, ref_table, ref_column, on_delete, on_update, ordinal)
        constraint_name, column, ref_table, ref_column, on_delete, on_update, ordinal = result[0]

        assert "org_id" == column
        assert "organizations" == ref_table
        assert "CASCADE" in [on_delete, on_update]

    def test_fetch_fk_no_foreign_keys(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema="main", table="standalone")
        assert result == []

    def test_fetch_fk_no_table_provided(self) -> None:
        mock_conn = MagicMock()
        result = fetch_foreign_keys_sync(mock_conn, schema="main", table=None)
        assert result == []

    def test_fetch_fk_multiple_foreign_keys(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            (0, 0, "users", "user_id", "id", "CASCADE", "CASCADE", "NONE"),
            (1, 0, "departments", "dept_id", "id", "SET NULL", "NO ACTION", "NONE"),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema="main", table="employees")

        assert len(result) == 2

    def test_fetch_fk_cascade_actions_preserved(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            (0, 0, "ref_table", "ref_col", "parent_id", "RESTRICT", "NO ACTION", "NONE"),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema="main", table="child")

        _, _, _, _, on_delete, on_update, _ = result[0]
        assert on_delete in ["RESTRICT", "NO ACTION"]
        assert on_update in ["RESTRICT", "NO ACTION"]

    def test_fetch_fk_default_schema(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, schema=None, table="test")
        assert isinstance(result, list)
