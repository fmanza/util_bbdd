"""Capabilities funcionales por motor."""

DB_ASYNC_CAPABILITIES: dict[str, bool] = {
    "mariadb": True,
    "oracle": True,
    "postgresql": True,
    "sqlserver": True,
    "sqlite": True,
    "hsqldb": False,
}


def is_async_supported(db_type: str) -> bool | None:
    """Indica si un motor soporta runtime async.

    Devuelve `None` para motores desconocidos.
    """
    return DB_ASYNC_CAPABILITIES.get(db_type.lower().strip())

