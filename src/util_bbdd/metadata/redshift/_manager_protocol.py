"""Protocolos internos que describen los contratos del manager usados por los adaptadores Redshift."""

from __future__ import annotations

from typing import Protocol

from ...metadata.adapters.shared._base_manager_protocol import BaseAsyncManagerProtocol, BaseSyncManagerProtocol
from ...results import RowOrNone, Rows


class RedshiftSyncManagerProtocol(BaseSyncManagerProtocol, Protocol):
    """Contrato mínimo que RedshiftSyncAdapter espera del SyncDatabaseManager."""

    def execute_custom_many(self, sql: str) -> Rows: ...

    def execute_custom_one(self, sql: str) -> RowOrNone: ...


class RedshiftAsyncManagerProtocol(BaseAsyncManagerProtocol, Protocol):
    """Contrato mínimo que RedshiftAsyncAdapter espera del AsyncDatabaseManager."""

    async def execute_custom_many(self, sql: str) -> Rows: ...

    async def execute_custom_one(self, sql: str) -> RowOrNone: ...


__all__: list[str] = ["RedshiftAsyncManagerProtocol", "RedshiftSyncManagerProtocol"]
