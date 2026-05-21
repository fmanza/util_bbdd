"""Protocolos internos que describen los contratos del manager usados por los adaptadores Oracle."""

from __future__ import annotations

from typing import Any, Protocol

from ...metadata.adapters.shared._base_manager_protocol import BaseAsyncManagerProtocol, BaseSyncManagerProtocol
from ...results import RowOrNone, Rows


class OracleSyncManagerProtocol(BaseSyncManagerProtocol, Protocol):
    """Contrato mínimo que OracleSyncAdapter espera del SyncDatabaseManager."""

    def execute_custom_many(self, sql: str, params: dict[str, Any] | None = None) -> Rows: ...

    def execute_custom_one(self, sql: str, params: dict[str, Any] | None = None) -> RowOrNone: ...


class OracleAsyncManagerProtocol(BaseAsyncManagerProtocol, Protocol):
    """Contrato mínimo que OracleAsyncAdapter espera del AsyncDatabaseManager."""

    async def execute_custom_many(self, sql: str, params: dict[str, Any] | None = None) -> Rows: ...

    async def execute_custom_one(self, sql: str, params: dict[str, Any] | None = None) -> RowOrNone: ...


__all__: list[str] = ["OracleAsyncManagerProtocol", "OracleSyncManagerProtocol"]
