"""
Módulo de conexión para operaciones de base de datos.

Proporciona construcción de parámetros, fábricas de conexión y pools.
"""

from .conn_params_builder import build_conn_params
from .connect_factory import ConnectFactory
from .connection_params_manager import ConnectionParamsManager
from .pool_protocol import ConnectionPoolProtocol

__all__: list[str] = [
    "build_conn_params",
    "ConnectFactory",
    "ConnectionPoolProtocol",
    "ConnectionParamsManager",
]
