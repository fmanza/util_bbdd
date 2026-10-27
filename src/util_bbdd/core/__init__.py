"""Core helpers compartidos entre capas de util_bbdd."""

from .capabilities import (
    DB_ASYNC_CAPABILITIES,
    ENGINE_CAPABILITIES,
    EngineCapabilities,
    get_engine_capabilities,
    is_async_supported,
)

__all__: list[str] = [
    "DB_ASYNC_CAPABILITIES",
    "ENGINE_CAPABILITIES",
    "EngineCapabilities",
    "get_engine_capabilities",
    "is_async_supported",
]
