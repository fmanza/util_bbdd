"""
SQLite - Módulo de conexión y pool para SQLite
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .async_connection_sqlite import AsyncSQLiteConnection
from .async_pool_connection_sqlite import AsyncSQLitePool
from .connection_sqlite import SQLiteConnection
from .pool_connection_sqlite import PoolConnection

if TYPE_CHECKING:
    from ._variables import SQLiteVariableValidator

__all__: list[str] = [
    "SQLiteConnection",
    "PoolConnection",
    "AsyncSQLiteConnection",
    "AsyncSQLitePool",
    "SQLiteVariableValidator",
]

_SYMBOL_TO_MODULE: dict[str, str] = {
    "SQLiteVariableValidator": "_variables",
}


def __getattr__(name: str) -> Any:
    module_name: str | None = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
