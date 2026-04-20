"""Helpers internos de metadata para managers sync y async.

Este módulo mantiene compatibilidad hacia atrás mediante re-exports de todas las clases
y funciones. Para nuevo código, importar directamente desde módulos especializados:
  - _metadata_context: MetadataContextResolver, CacheKeyFactory
  - _metadata_cache: CacheManager
  - _metadata_request: MetadataFetchRequest, MetadataRequestBuilder (Fase 3)
  - _metadata_parser: DDLNormalizer, CharsetCollationParser (Fase 3)
  - _manager_metadata_runtime: Fetch strategies y helpers
"""

from __future__ import annotations

from ._manager_metadata_runtime import (
    GenericMetadataFetchStrategy,
    MariaDBMetadataFetchStrategy,
    MetadataFetchStrategy,
    get_metadata_fetch_strategy,
)

# Fase 2: Metadata Context & Cache
from ._metadata_cache import (
    CacheManager,
    clear_all_caches,
    clear_context_cache,
    clear_routine_cache,
    clear_table_cache,
    clear_tuple_cache_by_context,
)
from ._metadata_context import (
    CacheKeyFactory,
    MetadataContextResolver,
    add_metadata_context_params,
    cache_context_key,
    cache_routine_key,
    cache_table_key,
    get_query_context_database,
    get_query_context_label,
)

# Fase 3: Runtime Metadata - Request Builders, Parsers, DDL Normalizers
from ._metadata_parser import (
    CharsetCollationParser,
    ColumnCharsetCollationRow,
    DDLNormalizer,
)
from ._metadata_request import MetadataFetchRequest, MetadataRequestBuilder

__all__: list[str] = [
    # Fase 2: Context & Cache classes
    "MetadataContextResolver",
    "CacheKeyFactory",
    "CacheManager",
    # Fase 3: Request Builders & Parsers
    "MetadataFetchRequest",
    "MetadataRequestBuilder",
    "DDLNormalizer",
    "CharsetCollationParser",
    "ColumnCharsetCollationRow",
    # Fase 3: Fetch Strategies
    "MetadataFetchStrategy",
    "GenericMetadataFetchStrategy",
    "MariaDBMetadataFetchStrategy",
    "get_metadata_fetch_strategy",
    # Deprecated functions (backward compatibility)
    "get_query_context_database",
    "get_query_context_label",
    "add_metadata_context_params",
    "clear_all_caches",
    "clear_table_cache",
    "clear_routine_cache",
    "clear_tuple_cache_by_context",
    "clear_context_cache",
    "cache_context_key",
    "cache_table_key",
    "cache_routine_key",
]
