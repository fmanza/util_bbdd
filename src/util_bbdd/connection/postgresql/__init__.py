"""Módulo de PostgreSQL - conexión y pool para PostgreSQL."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .async_connection_postgresql import AsyncPostgreSQLConnection
    from .async_pool_connection_postgresql import AsyncPostgreSQLPool
    from .connection_postgresql import PostgreSQLConnection
    from .pool_connection_postgresql import PoolConnection

__all__: list[str] = ["PostgreSQLConnection", "PoolConnection", "AsyncPostgreSQLConnection", "AsyncPostgreSQLPool"]

_SYMBOL_TO_MODULE: dict[str, str] = {
    "PostgreSQLConnection": "connection_postgresql",
    "PoolConnection": "pool_connection_postgresql",
    "AsyncPostgreSQLConnection": "async_connection_postgresql",
    "AsyncPostgreSQLPool": "async_pool_connection_postgresql",
}


def __getattr__(name: str) -> Any:
    module_name: str | None = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
