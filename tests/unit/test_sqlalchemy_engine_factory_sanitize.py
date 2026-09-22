"""Tests de regresión SVC-01 (AUDIT_CODE 2026-09-22).

`SQLAlchemyEngineFactory.create_engine()` logueaba `conn_str[:50]` sin redactar la contraseña
(`logger.debug(f"Connection string construido: {conn_str[:50]}...")`), mientras que
`AsyncSQLAlchemyEngineFactory` sí redactaba vía `_sanitize_conn_str()`. Se porta el mismo helper
al factory sync. No existía ningún test dedicado para ninguno de los dos factories antes de este
fix (ni siquiera para `_sanitize_conn_str` en el async).
"""

from __future__ import annotations

import pytest

from util_bbdd.factory.async_sqlalchemy_engine_factory import AsyncSQLAlchemyEngineFactory
from util_bbdd.factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory


@pytest.mark.parametrize("factory", [SQLAlchemyEngineFactory, AsyncSQLAlchemyEngineFactory])
class TestSanitizeConnStr:
    def test_redacts_password(self, factory) -> None:
        conn_str = "mariadb+mariadbconnector://admin:S3cr3tP4ss@db.internal:3306/prod"

        sanitized = factory._sanitize_conn_str(conn_str)

        assert "S3cr3tP4ss" not in sanitized
        assert "admin" in sanitized
        assert "db.internal" in sanitized
        assert ":***@" in sanitized

    def test_no_credentials_returned_unchanged(self, factory) -> None:
        conn_str = "sqlite:///path/to/db.sqlite3"

        assert factory._sanitize_conn_str(conn_str) == conn_str

    def test_not_a_url_returned_unchanged(self, factory) -> None:
        assert factory._sanitize_conn_str("not-a-url") == "not-a-url"

    def test_username_without_password_returned_unchanged(self, factory) -> None:
        conn_str = "postgresql://admin@db.internal:5432/prod"

        assert factory._sanitize_conn_str(conn_str) == conn_str
