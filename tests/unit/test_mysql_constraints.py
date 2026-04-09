"""Tests para módulo MySQL: constraints."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.mysql.constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync


class TestFetchPrimaryKeysSync:
    """Tests para fetch_primary_keys_sync()."""

    def test_fetch_pk_requires_schema_and_table(self) -> None:
        mock_conn = MagicMock()

        assert fetch_primary_keys_sync(mock_conn, None, None) == []
        assert fetch_primary_keys_sync(mock_conn, "schema", None) == []

    def test_fetch_pk_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "myschema", "users")
        assert isinstance(result, list)

    def test_fetch_pk_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("PRIMARY", "id", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "myschema", "users")
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_pk_extracts_constraint_info(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("PRIMARY", "id", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "myschema", "users")
        assert result[0][0] == "PRIMARY"
        assert result[0][1] == "id"
        assert result[0][2] == 1

    def test_fetch_pk_composite_sorted_by_ordinal(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("PRIMARY", "id2", 2), ("PRIMARY", "id1", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "myschema", "users")
        assert result[0][2] == 1  # First by ordinal
        assert result[1][2] == 2  # Second by ordinal


class TestFetchForeignKeysSync:
    """Tests para fetch_foreign_keys_sync()."""

    def test_fetch_fk_requires_schema_and_table(self) -> None:
        mock_conn = MagicMock()

        assert fetch_foreign_keys_sync(mock_conn, None, None) == []
        assert fetch_foreign_keys_sync(mock_conn, "schema", None) == []

    def test_fetch_fk_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        assert isinstance(result, list)

    def test_fetch_fk_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("fk_user", "user_id", "users", "id", "RESTRICT", "CASCADE", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        assert all(isinstance(r, tuple) for r in result)
        assert len(result) == 1

    def test_fetch_fk_extracts_full_info(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("fk_user", "user_id", "users", "id", "DELETE_RESTRICT", "UPDATE_CASCADE", 1)
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        row = result[0]
        assert row[0] == "fk_user"
        assert row[1] == "user_id"
        assert row[2] == "users"
        assert row[3] == "id"

    def test_fetch_fk_decodes_cascade_actions(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("fk_user", "user_id", "users", "id", "CASCADE", "RESTRICT", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        row = result[0]
        # Should decode actions
        assert row[4] in ("CASCADE", "RESTRICT", "SET NULL", "NO ACTION")
        assert row[5] in ("CASCADE", "RESTRICT", "SET NULL", "NO ACTION")

    def test_fetch_fk_handles_set_null_action(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Position 4 is UPDATE_RULE, position 5 is DELETE_RULE
        # We want DELETE_RULE to be SET NULL (position 5)
        mock_cursor.fetchall.return_value = [("fk_user", "user_id", "users", "id", "RESTRICT", "SET NULL", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        assert result[0][4] == "SET NULL"  # on_delete_action

    def test_fetch_fk_handles_null_actions(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("fk_user", "user_id", "users", "id", None, None, 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        row = result[0]
        # Should default to RESTRICT
        assert row[4] == "RESTRICT"
        assert row[5] == "RESTRICT"

    def test_fetch_fk_composite_keys(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("fk_comp", "col1", "ref_table", "ref_col1", "CASCADE", "CASCADE", 1),
            ("fk_comp", "col2", "ref_table", "ref_col2", "CASCADE", "CASCADE", 2),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        assert len(result) == 2
        assert result[0][0] == result[1][0] == "fk_comp"
