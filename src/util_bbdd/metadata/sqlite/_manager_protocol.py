"""Protocolos internos que describen los contratos del manager usados por los adaptadores SQLite."""

from __future__ import annotations

from typing import Protocol

from ...metadata.adapters.shared._base_manager_protocol import BaseAsyncManagerProtocol, BaseSyncManagerProtocol
from ...results import RowOrNone, Rows


class SQLiteSyncManagerProtocol(BaseSyncManagerProtocol, Protocol):
    """Contrato mínimo que SQLiteSyncAdapter espera del SyncDatabaseManager."""

    def execute_custom_many(self, sql: str) -> Rows: ...

    def execute_custom_one(self, sql: str) -> RowOrNone: ...


class SQLiteAsyncManagerProtocol(BaseAsyncManagerProtocol, Protocol):
    """Contrato mínimo que SQLiteAsyncAdapter espera del AsyncDatabaseManager."""

    async def execute_custom_many(self, sql: str) -> Rows: ...

    async def execute_custom_one(self, sql: str) -> RowOrNone: ...


__all__: list[str] = ["SQLiteAsyncManagerProtocol", "SQLiteSyncManagerProtocol"]
