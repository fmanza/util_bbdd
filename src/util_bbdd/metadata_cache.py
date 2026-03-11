"""
⚠️ DEPRECATED: Use `from util_bbdd.metadata import ...` instead

This module is kept for backward compatibility only.
All classes have been moved to util_bbdd.metadata module.
"""

from .metadata.cache import DatabaseMetadataCache, RelationshipMetadataCache

__all__ = ["DatabaseMetadataCache", "RelationshipMetadataCache"]
