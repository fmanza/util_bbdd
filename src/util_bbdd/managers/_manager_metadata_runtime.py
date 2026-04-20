"""Re-exporter: Helpers internos para metadata read-side compartida de managers.

Este módulo consolida imports desde _metadata_request y _metadata_parser,
manteniendo backward compatibility con código legacy.

Fase 3: Runtime Metadata - Consolidación de builders, parsers y helpers de DDL.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

# Re-exports: New classes from Fase 3
from ._metadata_parser import (
    CharsetCollationParser,
    ColumnCharsetCollationRow,
    DDLNormalizer,
    contains_create,
    is_lob,
    normalize_ddl_result,
    oracle_supports_columns_charset_collation,
    parse_charset_collation_result,
    parse_column_charset_collation_row,
    parse_db_charset_oracle,
    parse_db_charset_postgresql,
    parse_db_charset_single_field,
    read_lob,
    supports_columns_charset_collation,
)
from ._metadata_request import (
    MetadataFetchRequest,
    MetadataRequestBuilder,
    build_columns_fetch_request,
    build_routine_ddl_fetch_request,
    build_routine_parameters_fetch_request,
    build_routines_fetch_request,
    build_table_ddl_fetch_request,
    build_view_ddl_fetch_request,
)

_T = TypeVar("_T")


# Estrategias de fetching: Protocols y implementaciones por motor
class MetadataFetchStrategy(Protocol):
    """Contrato para construir fetchers sync/async por motor."""

    def build_sync_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], _T],
        execute_many: Callable[[MetadataFetchRequest], _T],
    ) -> Callable[[], _T]: ...

    def build_sync_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], str],
        execute_one: Callable[[MetadataFetchRequest], Any],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], str]: ...

    def build_async_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[_T]],
        execute_many: Callable[[MetadataFetchRequest], Awaitable[_T]],
    ) -> Callable[[], Awaitable[_T]]: ...

    def build_async_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[str]],
        execute_one: Callable[[MetadataFetchRequest], Awaitable[Any]],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], Awaitable[str]]: ...


@dataclass(frozen=True)
class GenericMetadataFetchStrategy:
    """Estrategia por defecto para motores SQL estándar."""

    def build_sync_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], _T],
        execute_many: Callable[[MetadataFetchRequest], _T],
    ) -> Callable[[], _T]:
        del specialized_fetcher
        return lambda: execute_many(request)

    def build_sync_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], str],
        execute_one: Callable[[MetadataFetchRequest], Any],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], str]:
        del specialized_fetcher
        return lambda: normalize_one(execute_one(request))

    def build_async_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[_T]],
        execute_many: Callable[[MetadataFetchRequest], Awaitable[_T]],
    ) -> Callable[[], Awaitable[_T]]:
        del specialized_fetcher

        async def _fetch_many() -> _T:
            return await execute_many(request)

        return _fetch_many

    def build_async_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[str]],
        execute_one: Callable[[MetadataFetchRequest], Awaitable[Any]],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], Awaitable[str]]:
        del specialized_fetcher

        async def _fetch_one_normalized() -> str:
            return normalize_one(await execute_one(request))

        return _fetch_one_normalized


@dataclass(frozen=True)
class MariaDBMetadataFetchStrategy:
    """Estrategia especializada para MariaDB."""

    def build_sync_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], _T],
        execute_many: Callable[[MetadataFetchRequest], _T],
    ) -> Callable[[], _T]:
        del request, execute_many
        return specialized_fetcher

    def build_sync_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], str],
        execute_one: Callable[[MetadataFetchRequest], Any],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], str]:
        del request, execute_one, normalize_one
        return specialized_fetcher

    def build_async_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[_T]],
        execute_many: Callable[[MetadataFetchRequest], Awaitable[_T]],
    ) -> Callable[[], Awaitable[_T]]:
        del request, execute_many
        return specialized_fetcher

    def build_async_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[str]],
        execute_one: Callable[[MetadataFetchRequest], Awaitable[Any]],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], Awaitable[str]]:
        del request, execute_one, normalize_one
        return specialized_fetcher


_DEFAULT_METADATA_FETCH_STRATEGY = GenericMetadataFetchStrategy()
_METADATA_FETCH_STRATEGIES: dict[str, MetadataFetchStrategy] = {
    "mariadb": MariaDBMetadataFetchStrategy(),
}


def get_metadata_fetch_strategy(db_type: str) -> MetadataFetchStrategy:
    """Retorna la estrategia de metadata para el motor indicado."""
    normalized_db_type: str = str(db_type or "").lower().strip()
    return _METADATA_FETCH_STRATEGIES.get(normalized_db_type, _DEFAULT_METADATA_FETCH_STRATEGY)


__all__: list[str] = [
    # New classes (Fase 3)
    "MetadataFetchRequest",
    "MetadataRequestBuilder",
    "CharsetCollationParser",
    "DDLNormalizer",
    # Fetch Strategies
    "MetadataFetchStrategy",
    "GenericMetadataFetchStrategy",
    "MariaDBMetadataFetchStrategy",
    "get_metadata_fetch_strategy",
    # Request Builders (deprecated wrappers)
    "build_columns_fetch_request",
    "build_routine_ddl_fetch_request",
    "build_routine_parameters_fetch_request",
    "build_routines_fetch_request",
    "build_table_ddl_fetch_request",
    "build_view_ddl_fetch_request",
    # Type aliases
    "ColumnCharsetCollationRow",
    # DDL Helpers (deprecated wrappers)
    "contains_create",
    "is_lob",
    "normalize_ddl_result",
    "read_lob",
    # Charset/Collation Parsers (deprecated wrappers)
    "oracle_supports_columns_charset_collation",
    "parse_charset_collation_result",
    "parse_column_charset_collation_row",
    "parse_db_charset_oracle",
    "parse_db_charset_postgresql",
    "parse_db_charset_single_field",
    "supports_columns_charset_collation",
]
