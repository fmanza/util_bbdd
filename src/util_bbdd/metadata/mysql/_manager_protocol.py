"""Protocolos internos que describen los contratos del manager usados por los adaptadores MySQL."""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import Any, Protocol

from ...metadata.cache import DatabaseMetadataCache
from ...results import RowOrNone, Rows


class MySQLSyncManagerProtocol(Protocol):
    """Contrato mínimo que MySQLSyncAdapter espera del SyncDatabaseManager."""

    @property
    def logger(self) -> logging.Logger:
        """Logger para trazabilidad."""
        ...

    @property
    def db_cache(self) -> DatabaseMetadataCache:
        """Cache de metadatos."""
        ...

    def _cache_context_key(self, context: str) -> str: ...

    def _get_query_context_label(self) -> str: ...

    def _get_query_context_database(self) -> str: ...

    def _get_cached_rows(
        self,
        *,
        cache_lookup: Callable[[], list[Any] | None],
        cache_store: Callable[[list[Any]], None],
        fetch_rows: Callable[[], list[Any]],
        cache_hit_message: str,
        success_message: str,
        fetch_debug_message: str | None,
    ) -> list[Any]: ...

    def _execute_metadata_many(
        self,
        query_name: str,
        *,
        params: dict[str, Any],
        error_message: str,
    ) -> Rows: ...

    def execute_custom_many(self, sql: str) -> Rows: ...

    def execute_custom_one(self, sql: str) -> RowOrNone: ...


class MySQLAsyncManagerProtocol(Protocol):
    """Contrato mínimo que MySQLAsyncAdapter espera del AsyncDatabaseManager."""

    @property
    def logger(self) -> logging.Logger:
        """Logger para trazabilidad."""
        ...

    @property
    def db_cache(self) -> DatabaseMetadataCache:
        """Cache de metadatos."""
        ...

    def _cache_context_key(self, context: str) -> str: ...

    def _get_query_context_label(self) -> str: ...

    def _get_query_context_database(self) -> str: ...

    async def _get_cached_rows_async(
        self,
        *,
        cache_lookup: Callable[[], list[Any] | None],
        cache_store: Callable[[list[Any]], None],
        fetch_rows: Callable[[], Any],
        cache_hit_message: str | None,
        success_message: str | None,
        fetch_debug_message: str | None,
    ) -> list[Any]: ...

    async def _execute_metadata_many(
        self,
        query_name: str,
        *,
        params: dict[str, Any],
        error_message: str,
    ) -> Rows: ...

    async def execute_custom_many(self, sql: str) -> Rows: ...

    async def execute_custom_one(self, sql: str) -> RowOrNone: ...


__all__: list[str] = ["MySQLAsyncManagerProtocol", "MySQLSyncManagerProtocol"]
