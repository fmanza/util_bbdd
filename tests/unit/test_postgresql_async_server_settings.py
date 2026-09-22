"""Tests de regresión para schema/options/application_name en PostgreSQL async [CNX-04].

Antes de este fix, `async_connection_postgresql.py`/`async_pool_connection_postgresql.py`
descartaban silenciosamente `schema`/`options`/`application_name` porque
`asyncpg.connect()`/`asyncpg.create_pool()` no los aceptan como kwargs directos
(a diferencia de psycopg3, que sí los aplica vía `options=`/`application_name=`
libpq). La versión sync ya los aplicaba correctamente.
"""

from __future__ import annotations

import asyncio
import types

import pytest

from util_bbdd.connection.postgresql._server_settings import build_server_settings, parse_libpq_options
from util_bbdd.connection.postgresql.async_connection_postgresql import AsyncPostgreSQLConnection
from util_bbdd.connection.postgresql.async_pool_connection_postgresql import AsyncPostgreSQLPool


class TestParseLibpqOptions:
    def test_single_option(self) -> None:
        assert parse_libpq_options("-c search_path=myschema") == {"search_path": "myschema"}

    def test_multiple_options(self) -> None:
        result = parse_libpq_options("-c search_path=myschema -c statement_timeout=5000")
        assert result == {"search_path": "myschema", "statement_timeout": "5000"}

    def test_empty_string_returns_empty_dict(self) -> None:
        assert parse_libpq_options("") == {}

    def test_malformed_fragment_ignored(self) -> None:
        assert parse_libpq_options("-c no_equals_sign") == {}


class TestBuildServerSettings:
    def test_schema_and_options_already_merged_by_sync_config(self) -> None:
        """PostgreSQLConnectionConfig.to_driver_kwargs() ya combina schema+options
        en un único string 'options'; build_server_settings solo lo parsea."""
        conn_params = {"options": "-c search_path=myschema -c statement_timeout=5000"}
        assert build_server_settings(conn_params) == {
            "search_path": "myschema",
            "statement_timeout": "5000",
        }

    def test_application_name_included(self) -> None:
        conn_params = {"application_name": "my_app"}
        assert build_server_settings(conn_params) == {"application_name": "my_app"}

    def test_no_relevant_params_returns_empty_dict(self) -> None:
        assert build_server_settings({"host": "localhost", "user": "u"}) == {}

    def test_options_and_application_name_combined(self) -> None:
        conn_params = {"options": "-c search_path=myschema", "application_name": "my_app"}
        assert build_server_settings(conn_params) == {
            "search_path": "myschema",
            "application_name": "my_app",
        }


def _install_fake_asyncpg(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    async def fake_connect(**kwargs):
        await asyncio.sleep(0)
        captured["connect_kwargs"] = kwargs
        return types.SimpleNamespace()

    async def fake_create_pool(**kwargs):
        await asyncio.sleep(0)
        captured["create_pool_kwargs"] = kwargs
        return types.SimpleNamespace()

    fake_module = types.SimpleNamespace(connect=fake_connect, create_pool=fake_create_pool)
    monkeypatch.setitem(__import__("sys").modules, "asyncpg", fake_module)


class TestAsyncConnectionAppliesServerSettings:
    def test_schema_reaches_asyncpg_as_search_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict = {}
        _install_fake_asyncpg(monkeypatch, captured)

        async def _run() -> None:
            await AsyncPostgreSQLConnection.connect(
                {
                    "host": "localhost",
                    "port": 5432,
                    "user": "postgres",
                    "password": "pwd",
                    "database": "db",
                    "schema": "myschema",
                }
            )

        asyncio.run(_run())

        assert captured["connect_kwargs"]["server_settings"] == {"search_path": "myschema"}

    def test_application_name_reaches_asyncpg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict = {}
        _install_fake_asyncpg(monkeypatch, captured)

        async def _run() -> None:
            await AsyncPostgreSQLConnection.connect(
                {
                    "host": "localhost",
                    "port": 5432,
                    "user": "postgres",
                    "password": "pwd",
                    "database": "db",
                    "application_name": "my_app",
                }
            )

        asyncio.run(_run())

        assert captured["connect_kwargs"]["server_settings"]["application_name"] == "my_app"

    def test_no_schema_or_application_name_omits_server_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict = {}
        _install_fake_asyncpg(monkeypatch, captured)

        async def _run() -> None:
            await AsyncPostgreSQLConnection.connect(
                {
                    "host": "localhost",
                    "port": 5432,
                    "user": "postgres",
                    "password": "pwd",
                    "database": "db",
                }
            )

        asyncio.run(_run())

        assert "server_settings" not in captured["connect_kwargs"]


class TestAsyncPoolAppliesServerSettings:
    def test_schema_reaches_asyncpg_pool_as_search_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict = {}
        _install_fake_asyncpg(monkeypatch, captured)

        async def _run() -> None:
            await AsyncPostgreSQLPool.create(
                {
                    "host": "localhost",
                    "port": 5432,
                    "user": "postgres",
                    "password": "pwd",
                    "database": "db",
                    "schema": "myschema",
                }
            )

        asyncio.run(_run())

        assert captured["create_pool_kwargs"]["server_settings"] == {"search_path": "myschema"}
