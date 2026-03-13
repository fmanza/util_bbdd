"""Oracle - módulo de conexión y pool para Oracle."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .async_connection_oracle import AsyncOracleConnection
    from .async_pool_connection_oracle import AsyncOraclePool
    from .connection_oracle import OracleConnection
    from .pool_connection_oracle import PoolConnection

__all__: list[str] = ["OracleConnection", "PoolConnection", "AsyncOracleConnection", "AsyncOraclePool"]

_SYMBOL_TO_MODULE: dict[str, str] = {
    "OracleConnection": "connection_oracle",
    "PoolConnection": "pool_connection_oracle",
    "AsyncOracleConnection": "async_connection_oracle",
    "AsyncOraclePool": "async_pool_connection_oracle",
}


def __getattr__(name: str) -> Any:
    module_name: str | None = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
