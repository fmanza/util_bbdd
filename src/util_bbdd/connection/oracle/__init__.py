"""
Oracle - Módulo de conexión y pool para Oracle
"""

from .connection_oracle import OracleConnection
from .pool_connection_oracle import PoolConnection

__all__: list[str] = ["OracleConnection", "PoolConnection"]
