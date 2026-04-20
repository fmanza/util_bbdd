"""Helpers internos de metadata para managers sync y async."""

from __future__ import annotations

from ._manager_metadata_runtime import (
    GenericMetadataFetchStrategy,
    MariaDBMetadataFetchStrategy,
    MetadataFetchStrategy,
    get_metadata_fetch_strategy,
)
from ._metadata_cache import CacheManager
from ._metadata_context import CacheKeyFactory, MetadataContextResolver
from ._metadata_parser import CharsetCollationParser, ColumnCharsetCollationRow, DDLNormalizer
from ._metadata_request import MetadataFetchRequest, MetadataRequestBuilder

__all__: list[str] = [
    "MetadataContextResolver",
    "CacheKeyFactory",
    "CacheManager",
    "MetadataFetchRequest",
    "MetadataRequestBuilder",
    "DDLNormalizer",
    "CharsetCollationParser",
    "ColumnCharsetCollationRow",
    "MetadataFetchStrategy",
    "GenericMetadataFetchStrategy",
    "MariaDBMetadataFetchStrategy",
    "get_metadata_fetch_strategy",
]
