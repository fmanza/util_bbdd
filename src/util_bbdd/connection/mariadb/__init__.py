"""
MariaDB - Módulo de conexión y pool para MariaDB
"""

from .async_connection_mariadb import AsyncMariaDBConnection
from .async_pool_connection_mariadb import AsyncMariaDBPool
from .connection_mariadb import MariaDBConnection
from .pool_connection_mariadb import PoolConnection

__all__: list[str] = [
    "MariaDBConnection",
    "PoolConnection",
    "AsyncMariaDBConnection",
    "AsyncMariaDBPool",
]
