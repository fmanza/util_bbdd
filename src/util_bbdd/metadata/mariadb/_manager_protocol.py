"""Protocolos internos que describen los contratos del manager usados por los adaptadores MariaDB."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from ...metadata.cache import DatabaseMetadataCache
from ...results import RowOrNone, Rows


class MariaDBSyncManagerProtocol(Protocol):
    """Contrato mínimo que MariaDBSyncAdapter espera del SyncDatabaseManager."""

    @property
    def db_cache(self) -> DatabaseMetadataCache: ...

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

    def get_tables(self) -> Rows: ...

    def get_columns(self, tabla: str) -> Rows: ...

    def get_primary_keys(self, tabla: str) -> Rows: ...

    def get_foreign_keys(self, tabla: str) -> Rows: ...

    def get_indices(self, tabla: str) -> Rows: ...

    def execute_query_many(self, query_name: str, **kwargs: Any) -> Rows: ...


class MariaDBAsyncManagerProtocol(Protocol):
    """Contrato mínimo que MariaDBAsyncAdapter espera del AsyncDatabaseManager."""

    @property
    def db_cache(self) -> DatabaseMetadataCache: ...

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

    async def get_tables(self) -> Rows: ...

    async def get_columns(self, tabla: str) -> Rows: ...

    async def get_primary_keys(self, tabla: str) -> Rows: ...

    async def get_foreign_keys(self, tabla: str) -> Rows: ...

    async def get_indices(self, tabla: str) -> Rows: ...

    async def execute_query_many(self, query_name: str, **kwargs: Any) -> Rows: ...


__all__: list[str] = ["MariaDBAsyncManagerProtocol", "MariaDBSyncManagerProtocol"]
