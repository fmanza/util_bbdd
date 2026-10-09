"""Política de pool de los Engine de SQLAlchemy, común a ``SQLAlchemyEngineFactory`` y ``AsyncSQLAlchemyEngineFactory``."""

from __future__ import annotations

from typing import Any

#: Valores por defecto del pool de los Engine. ``pool_size``/``max_overflow``/``pool_timeout`` coinciden con los de
#: ``QueuePool``; ``pool_recycle`` coincide con el de los pools nativos (``MySQLPoolConfig``, ``MariaDBPoolConfig``).
ENGINE_POOL_DEFAULTS: dict[str, int] = {
    "pool_size": 5,
    "max_overflow": 10,
    "pool_timeout": 30,
    "pool_recycle": 3600,
}


def engine_pool_kwargs(db_type: str, conn_params: dict[str, Any], **overrides: int | None) -> dict[str, int]:
    """kwargs de pool para ``create_engine``/``create_async_engine`` a partir de ``conn_params``.

    El Engine tiene su propio pool, independiente del pool nativo del manager: con ``pool_size=N`` un manager puede
    mantener hasta ``N`` conexiones nativas más ``N + max_overflow`` del Engine.

    Args:
        db_type: Motor normalizado. SQLite devuelve ``{}``: SQLAlchemy usa ``SingletonThreadPool``/``NullPool``, que
            no admiten estos parámetros.
        conn_params: Parámetros de conexión del manager.
        **overrides: Valores explícitos que prevalecen sobre ``conn_params`` (``None`` se ignora).
    """
    if db_type == "sqlite":
        return {}
    kwargs: dict[str, int] = {}
    for key, default in ENGINE_POOL_DEFAULTS.items():
        value: Any = overrides.get(key)
        if value is None:
            value = conn_params.get(key)
        kwargs[key] = default if value is None else int(value)
    return kwargs
