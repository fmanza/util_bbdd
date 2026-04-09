"""Tests para módulo Redshift: índices.

Redshift tiene soporte limitado para índices;
se consultan via pg_catalog.pg_indexes.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.redshift.indexes import fetch_indexes_sync


class TestFetchIndexesSync:
    """Tests para fetch_indexes_sync()."""

    def test_fetch_indexes_requires_schema_and_table(self) -> None:
        mock_conn = MagicMock()

        result = fetch_indexes_sync(mock_conn, None, None)
        assert result == []

        result = fetch_indexes_sync(mock_conn, "myschema", None)
        assert result == []

        result = fetch_indexes_sync(mock_conn, None, "users")
        assert result == []

    def test_fetch_indexes_rejects_system_schema(self) -> None:
        """Debe rechazar schemas del sistema."""
        mock_conn = MagicMock()

        result = fetch_indexes_sync(mock_conn, "pg_catalog", "users")
        assert result == []

    def test_fetch_indexes_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert isinstance(result, list)

    def test_fetch_indexes_returns_empty_for_no_indexes(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert result == []

    def test_fetch_indexes_returns_tuples(self) -> None:
        """Redshift devuelve índices con información limitada."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("idx_users_email", "INDEX", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_indexes_index_name_repeated(self) -> None:
        """Redshift pg_indexes no expone column info y uniqueness."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("idx_users_email", "INDEX", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        # Formato esperado: (index_name, column_name, seq_in_index, is_unique)
        assert result[0][0] == "idx_users_email"  # index_name
        assert result[0][1] == "idx_users_email"  # column_name (repetido, limitación)
        assert result[0][2] == 1  # seq_in_index
        assert result[0][3] == 0  # is_unique (asumimos no-unique por limitación)

    def test_fetch_indexes_assumes_non_unique(self) -> None:
        """Redshift no expone información de uniqueness."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("idx_users_email", "INDEX", ""),
            ("idx_users_created", "INDEX", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert len(result) == 2
        # Todos asumen non-unique
        assert all(r[3] == 0 for r in result)

    def test_fetch_indexes_handles_multiple_indexes(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("idx_users_email", "INDEX", ""),
            ("idx_users_status", "INDEX", ""),
            ("idx_users_created", "INDEX", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert len(result) == 3
        index_names = {r[0] for r in result}
        assert "idx_users_email" in index_names
        assert "idx_users_status" in index_names


class TestFetchIndexesSyncEdgeCases:
    """Tests de casos límite para fetch_indexes_sync()."""

    def test_fetch_indexes_handles_empty_rows(self) -> None:
        """Filas vacías deben ignorarse."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("idx_users_email", "INDEX", ""),
            (),  # empty row
            ("idx_users_created", "INDEX", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert len(result) == 2

    def test_fetch_indexes_special_characters_in_name(self) -> None:
        """Nombres con caracteres especiales."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('idx_users_"special"', "INDEX", ""),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_indexes_sync(mock_conn, "myschema", "users")
        assert result[0][0] == 'idx_users_"special"'
