"""MariaDB - módulo de conexión y pool para MariaDB.

Este módulo evita imports eager de drivers opcionales para no fallar en import-time
cuando el entorno no tiene todos los conectores instalados.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._config import MySQLOptimalConfig
    from ._variables import MySQLVariableValidator
    from .async_connection_mariadb import AsyncMariaDBConnection
    from .async_pool_connection_mariadb import AsyncMariaDBPool
    from .connection_mariadb import MariaDBConnection
    from .pool_connection_mariadb import PoolConnection

__all__: list[str] = [
    "MariaDBConnection",
    "PoolConnection",
    "AsyncMariaDBConnection",
    "AsyncMariaDBPool",
    "MySQLVariableValidator",
    "MySQLOptimalConfig",
]

_SYMBOL_TO_MODULE: dict[str, str] = {
    "MariaDBConnection": "connection_mariadb",
    "PoolConnection": "pool_connection_mariadb",
    "AsyncMariaDBConnection": "async_connection_mariadb",
    "AsyncMariaDBPool": "async_pool_connection_mariadb",
    "MySQLVariableValidator": "_variables",
    "MySQLOptimalConfig": "_config",
}


def __getattr__(name: str) -> Any:
    module_name: str | None = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
