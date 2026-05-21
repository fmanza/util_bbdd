"""Protocolos internos que describen los contratos del manager usados por los adaptadores Snowflake."""

from __future__ import annotations

from typing import Protocol

from ...metadata.adapters.shared._base_manager_protocol import BaseAsyncManagerProtocol, BaseSyncManagerProtocol
from ...results import RowOrNone, Rows


class SnowflakeSyncManagerProtocol(BaseSyncManagerProtocol, Protocol):
    """Contrato mínimo que SnowflakeSyncAdapter espera del SyncDatabaseManager."""

    def execute_custom_many(self, sql: str) -> Rows: ...

    def execute_custom_one(self, sql: str) -> RowOrNone: ...


class SnowflakeAsyncManagerProtocol(BaseAsyncManagerProtocol, Protocol):
    """Contrato mínimo que SnowflakeAsyncAdapter espera del AsyncDatabaseManager."""

    async def execute_custom_many(self, sql: str) -> Rows: ...

    async def execute_custom_one(self, sql: str) -> RowOrNone: ...


__all__: list[str] = ["SnowflakeAsyncManagerProtocol", "SnowflakeSyncManagerProtocol"]
