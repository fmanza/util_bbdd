"""Tests para módulo Redshift: constraints (PK/FK como advisory).

CRÍTICO: Redshift constraints son ADVISORY, no enforced.
Los tests verifican que se registran warnings apropiados.
"""

from __future__ import annotations

import logging

from unittest.mock import MagicMock

from util_bbdd.metadata.redshift.constraints import (
    fetch_foreign_keys_sync,
    fetch_primary_keys_sync,
    normalize_redshift_action,
)


class TestFetchPrimaryKeysSync:
    """Tests para fetch_primary_keys_sync()."""

    def test_fetch_pk_requires_schema_and_table(self) -> None:
        mock_conn = MagicMock()

        result = fetch_primary_keys_sync(mock_conn, None, None)
        assert result == []

        result = fetch_primary_keys_sync(mock_conn, "myschema", None)
        assert result == []

    def test_fetch_pk_rejects_system_schema(self) -> None:
        """Debe rechazar schemas del sistema."""
        mock_conn = MagicMock()

        result = fetch_primary_keys_sync(mock_conn, "pg_catalog", "users")
        assert result == []

    def test_fetch_pk_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "myschema", "users")
        assert isinstance(result, list)

    def test_fetch_pk_logs_advisory_warning(self, caplog) -> None:
        """CRÍTICO: Redshift PK son advisory - debe loguear warning."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("pk_users", "id", 1)]
        mock_conn.execute.return_value = mock_cursor

        with caplog.at_level(logging.WARNING):
            result = fetch_primary_keys_sync(mock_conn, "myschema", "users")

        assert len(result) > 0
        log_text = caplog.text
        assert "advisory" in log_text.lower()

    def test_fetch_pk_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("pk_users", "id", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "myschema", "users")
        assert all(isinstance(r, tuple) for r in result)
        assert len(result) == 1

    def test_fetch_pk_extracts_fields(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("pk_users", "id", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "myschema", "users")
        assert result[0][0] == "pk_users"  # constraint_name
        assert result[0][1] == "id"  # column_name
        assert result[0][2] == 1  # ordinal_position

    def test_fetch_pk_multiple_columns(self) -> None:
        """Composite PK."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("pk_orders", "tenant_id", 1),
            ("pk_orders", "order_id", 2),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_primary_keys_sync(mock_conn, "myschema", "orders")
        assert len(result) == 2
        assert result[0][2] == 1
        assert result[1][2] == 2


class TestFetchForeignKeysSync:
    """Tests para fetch_foreign_keys_sync()."""

    def test_fetch_fk_requires_schema_and_table(self) -> None:
        mock_conn = MagicMock()

        result = fetch_foreign_keys_sync(mock_conn, None, None)
        assert result == []

        result = fetch_foreign_keys_sync(mock_conn, "myschema", None)
        assert result == []

    def test_fetch_fk_rejects_system_schema(self) -> None:
        """Debe rechazar schemas del sistema."""
        mock_conn = MagicMock()

        result = fetch_foreign_keys_sync(mock_conn, "pg_catalog", "users")
        assert result == []

    def test_fetch_fk_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        assert isinstance(result, list)

    def test_fetch_fk_logs_advisory_warning(self, caplog) -> None:
        """CRÍTICO: Redshift FK son advisory - debe loguear warning."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("fk_posts_user", "user_id", "users", "id", "NO ACTION", "RESTRICT", 1)]
        mock_conn.execute.return_value = mock_cursor

        with caplog.at_level(logging.WARNING):
            result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")

        assert len(result) > 0
        log_text = caplog.text
        assert "advisory" in log_text.lower()

    def test_fetch_fk_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("fk_posts_user", "user_id", "users", "id", "NO ACTION", "RESTRICT", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_fk_extracts_fields(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("fk_posts_user", "user_id", "users", "id", "NO ACTION", "NO ACTION", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        assert result[0][0] == "fk_posts_user"  # constraint_name
        assert result[0][1] == "user_id"  # column_name
        assert result[0][2] == "users"  # ref_table
        assert result[0][3] == "id"  # ref_column

    def test_fetch_fk_normalizes_actions(self) -> None:
        """Debe normalizar acciones CASCADE/RESTRICT/etc."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("fk_posts_user", "user_id", "users", "id", "CASCADE", "RESTRICT", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        assert result[0][4] == "RESTRICT"  # on_delete_action (normalized)
        assert result[0][5] == "CASCADE"  # on_update_action (normalized)

    def test_fetch_fk_handles_null_referenced_columns(self) -> None:
        """Debe manejar FK incompletos (sin ref_table/ref_column)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Simular una fila incompleta
        mock_cursor.fetchall.return_value = [("fk_posts_user", "user_id", None, None, "NO ACTION", "NO ACTION", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_foreign_keys_sync(mock_conn, "myschema", "posts")
        assert result[0][2] == ""  # ref_table
        assert result[0][3] == ""  # ref_column


class TestNormalizeRedshiftAction:
    """Tests para normalize_redshift_action()."""

    def test_normalize_no_action(self) -> None:
        assert normalize_redshift_action("NO ACTION") == "NO ACTION"

    def test_normalize_restrict(self) -> None:
        assert normalize_redshift_action("RESTRICT") == "RESTRICT"

    def test_normalize_cascade(self) -> None:
        assert normalize_redshift_action("CASCADE") == "CASCADE"

    def test_normalize_set_null(self) -> None:
        assert normalize_redshift_action("SET NULL") == "SET NULL"

    def test_normalize_set_default(self) -> None:
        assert normalize_redshift_action("SET DEFAULT") == "SET DEFAULT"

    def test_normalize_unknown_action_defaults_to_restrict(self) -> None:
        assert normalize_redshift_action("UNKNOWN") == "RESTRICT"

    def test_normalize_empty_action_defaults_to_restrict(self) -> None:
        assert normalize_redshift_action("") == "RESTRICT"

    def test_normalize_case_insensitive(self) -> None:
        assert normalize_redshift_action("cascade") == "CASCADE"
        assert normalize_redshift_action("CaScAdE") == "CASCADE"
