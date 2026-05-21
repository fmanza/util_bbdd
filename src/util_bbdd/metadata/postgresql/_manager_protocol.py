"""Protocolos internos que describen los contratos del manager usados por los adaptadores PostgreSQL."""

from __future__ import annotations

from typing import Any, Protocol

from ...metadata.adapters.shared._base_manager_protocol import BaseAsyncManagerProtocol, BaseSyncManagerProtocol
from ...results import RowOrNone, Rows


class PostgreSQLSyncManagerProtocol(BaseSyncManagerProtocol, Protocol):
    """Contrato mínimo que PostgreSQLSyncAdapter espera del SyncDatabaseManager."""

    def execute_custom_many(self, sql: str, params: dict[str, Any] | None = None) -> Rows: ...

    def execute_custom_one(self, sql: str, params: dict[str, Any] | None = None) -> RowOrNone: ...


class PostgreSQLAsyncManagerProtocol(BaseAsyncManagerProtocol, Protocol):
    """Contrato mínimo que PostgreSQLAsyncAdapter espera del AsyncDatabaseManager."""

    async def execute_custom_many(self, sql: str, params: dict[str, Any] | None = None) -> Rows: ...

    async def execute_custom_one(self, sql: str, params: dict[str, Any] | None = None) -> RowOrNone: ...


__all__: list[str] = ["PostgreSQLAsyncManagerProtocol", "PostgreSQLSyncManagerProtocol"]
