"""Core helpers compartidos entre capas de util_bbdd."""

from .capabilities import DB_ASYNC_CAPABILITIES, is_async_supported

__all__: list[str] = ["DB_ASYNC_CAPABILITIES", "is_async_supported"]
