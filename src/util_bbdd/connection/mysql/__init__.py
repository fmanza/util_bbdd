"""MySQL - conexión y pool con PyMySQL (sync) y aiomysql (async).

Este módulo evita imports eager de drivers opcionales para no fallar en import-time
cuando el entorno no tiene todos los conectores instalados.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .async_connection_mysql import AsyncMySQLConnection
    from .async_pool_connection_mysql import AsyncMySQLPool
    from .connection_mysql import MySQLConnection
    from .pool_connection_mysql import PoolConnection

__all__: list[str] = [
    "MySQLConnection",
    "PoolConnection",
    "AsyncMySQLConnection",
    "AsyncMySQLPool",
]

_SYMBOL_TO_MODULE: dict[str, str] = {
    "MySQLConnection": "connection_mysql",
    "PoolConnection": "pool_connection_mysql",
    "AsyncMySQLConnection": "async_connection_mysql",
    "AsyncMySQLPool": "async_pool_connection_mysql",
}


def __getattr__(name: str) -> Any:
    module_name: str | None = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
