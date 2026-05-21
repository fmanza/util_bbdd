"""Protocolos base compartidos por todos los motor-specific manager protocols.

Cada motor `_manager_protocol.py` hereda de estas bases y añade únicamente
las divergencias propias (firma de execute_custom_* y métodos motor-específicos).
"""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import Any, Protocol

from ....metadata.cache import DatabaseMetadataCache
from ....results import Rows


class BaseSyncManagerProtocol(Protocol):
    """Contrato mínimo común a todos los SyncAdapter managers.

    Cubre los 7 métodos idénticos en los 8 motor protocols. Cada motor hereda
    esta base y declara su variante de execute_custom_many / execute_custom_one.
    """

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


class BaseAsyncManagerProtocol(Protocol):
    """Contrato mínimo común a todos los AsyncAdapter managers.

    Cubre los 7 métodos idénticos en los 8 motor protocols. Cada motor hereda
    esta base y declara su variante async de execute_custom_many / execute_custom_one.
    """

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


__all__: list[str] = ["BaseAsyncManagerProtocol", "BaseSyncManagerProtocol"]
