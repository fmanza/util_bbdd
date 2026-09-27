"""Módulo de SQL Server - conexión y pool para SQL Server."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._variables import SQLServerVariableValidator
    from .async_connection_sqlserver import AsyncSQLServerConnection
    from .async_pool_connection_sqlserver import AsyncSQLServerPool
    from .connection_sqlserver import SQLServerConnection
    from .pool_connection_sqlserver import PoolConnection

__all__: list[str] = [
    "SQLServerConnection",
    "PoolConnection",
    "AsyncSQLServerConnection",
    "AsyncSQLServerPool",
    "SQLServerVariableValidator",
]

_SYMBOL_TO_MODULE: dict[str, str] = {
    "SQLServerConnection": "connection_sqlserver",
    "PoolConnection": "pool_connection_sqlserver",
    "AsyncSQLServerConnection": "async_connection_sqlserver",
    "AsyncSQLServerPool": "async_pool_connection_sqlserver",
    "SQLServerVariableValidator": "_variables",
}


def __getattr__(name: str) -> Any:
    module_name: str | None = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
