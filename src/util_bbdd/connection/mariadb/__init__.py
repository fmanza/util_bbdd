"""
MariaDB - Módulo de conexión y pool para MariaDB
"""

from .connection_mariadb import MariaDBConnection
from .pool_connection_mariadb import PoolConnection

__all__: list[str] = ["MariaDBConnection", "PoolConnection"]
