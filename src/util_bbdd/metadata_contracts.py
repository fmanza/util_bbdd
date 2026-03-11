"""
⚠️ DEPRECATED: Use `from util_bbdd.metadata import ...` instead

This module is kept for backward compatibility only.
All classes have been moved to util_bbdd.metadata module.
"""

from .metadata.contracts import (
    AsyncMetadataProvider,
    Row,
    Rows,
    SyncMetadataProvider,
)

__all__ = ["Row", "Rows", "SyncMetadataProvider", "AsyncMetadataProvider"]
