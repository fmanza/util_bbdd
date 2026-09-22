"""Tests para cumplimiento de protocolos y paridad MariaDB.

MEO-03 (AUDIT_CODE 2026-09-22): MariaDBSyncAdapter/MariaDBAsyncAdapter tenían firmas reducidas
(``fetch_tables_sync(self)``, ``fetch_columns_sync(self, table)``, sin ``schema``) frente al
Protocol y a los otros 8 motores (``fetch_columns_sync(self, schema, table)``). No existía
ningún ``test_mariadb_adapter_parity.py`` (sí existían los de mysql y oracle) — este archivo
cierra ese hueco.
"""

from __future__ import annotations

import asyncio
import inspect

from unittest.mock import MagicMock

import pytest

from util_bbdd.metadata.mariadb.async_adapter import MariaDBAsyncAdapter
from util_bbdd.metadata.mariadb.sync_adapter import MariaDBSyncAdapter


def _make_sync_manager(rows: list[tuple] | None = None) -> MagicMock:
    manager = MagicMock()
    manager.get_tables.return_value = rows or []
    manager.get_columns.return_value = rows or []
    manager.get_primary_keys.return_value = rows or []
    manager.get_foreign_keys.return_value = rows or []
    manager.get_indices.return_value = rows or []
    return manager


class TestMariaDBSyncAdapterProtocolSignatures:
    """SourceAdapterSync exige (schema, table) para columns/pk/fk/indexes, y
    (schema: str | None = None) para tables. Antes de MEO-03, MariaDB no aceptaba schema."""

    def test_fetch_tables_sync_accepts_optional_schema(self) -> None:
        sig = inspect.signature(MariaDBSyncAdapter.fetch_tables_sync)
        params = list(sig.parameters)
        assert params == ["self", "schema"]
        assert sig.parameters["schema"].default is None

    @pytest.mark.parametrize(
        "method_name",
        ["fetch_columns_sync", "fetch_primary_keys_sync", "fetch_foreign_keys_sync", "fetch_indexes_sync"],
    )
    def test_table_methods_accept_schema_and_table(self, method_name: str) -> None:
        sig = inspect.signature(getattr(MariaDBSyncAdapter, method_name))
        params = list(sig.parameters)
        assert params == ["self", "schema", "table"], f"{method_name} firma inesperada: {params}"

    def test_fetch_tables_sync_callable_with_schema_argument(self) -> None:
        manager = _make_sync_manager([("USERS", "BASE TABLE", "")])
        adapter = MariaDBSyncAdapter(manager)

        result = adapter.fetch_tables_sync("ignored_schema")

        assert result == [("USERS", "BASE TABLE", "")]

    @pytest.mark.parametrize(
        "method_name,manager_attr",
        [
            ("fetch_columns_sync", "get_columns"),
            ("fetch_primary_keys_sync", "get_primary_keys"),
            ("fetch_foreign_keys_sync", "get_foreign_keys"),
            ("fetch_indexes_sync", "get_indices"),
        ],
    )
    def test_table_methods_callable_with_schema_and_table(self, method_name: str, manager_attr: str) -> None:
        manager = _make_sync_manager([("COL1",)])
        adapter = MariaDBSyncAdapter(manager)

        result = getattr(adapter, method_name)("ignored_schema", "USERS")

        assert result == [("COL1",)]
        getattr(manager, manager_attr).assert_called_once_with("USERS")


class TestMariaDBAsyncAdapterProtocolSignatures:
    def test_fetch_tables_async_accepts_optional_schema(self) -> None:
        sig = inspect.signature(MariaDBAsyncAdapter.fetch_tables_async)
        params = list(sig.parameters)
        assert params == ["self", "schema"]
        assert sig.parameters["schema"].default is None

    @pytest.mark.parametrize(
        "method_name",
        ["fetch_columns_async", "fetch_primary_keys_async", "fetch_foreign_keys_async", "fetch_indexes_async"],
    )
    def test_table_methods_accept_schema_and_table(self, method_name: str) -> None:
        sig = inspect.signature(getattr(MariaDBAsyncAdapter, method_name))
        params = list(sig.parameters)
        assert params == ["self", "schema", "table"], f"{method_name} firma inesperada: {params}"

    def test_fetch_columns_async_callable_with_schema_argument(self) -> None:
        async def _run() -> list[tuple]:
            manager = MagicMock()

            async def _get_columns(table: str) -> list[tuple]:
                await asyncio.sleep(0)
                return [("COL1",)]

            manager.get_columns = _get_columns
            adapter = MariaDBAsyncAdapter(manager)
            return await adapter.fetch_columns_async("ignored_schema", "USERS")

        result = asyncio.run(_run())
        assert result == [("COL1",)]
