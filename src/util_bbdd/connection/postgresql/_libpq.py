"""Traducción de ``PostgreSQLConnectionConfig.to_driver_kwargs()`` a parámetros de conexión de libpq (psycopg).

La config conserva nombres que consumen también el pool (URI) y asyncpg (``database``). Para libpq:

- ``database`` → ``dbname`` (un ``dbname`` explícito tiene prioridad);
- ``tcp_keepalives_idle/interval/count`` → ``keepalives_idle/interval/count`` (los ``tcp_*`` son los nombres del
  parámetro del servidor, no opciones de conexión: libpq los rechaza);
- booleanos → ``0``/``1`` (libpq rechaza ``keepalives="True"`` en el servidor).
"""

from __future__ import annotations

from typing import Any

_LIBPQ_RENAMES: dict[str, str] = {
    "tcp_keepalives_idle": "keepalives_idle",
    "tcp_keepalives_interval": "keepalives_interval",
    "tcp_keepalives_count": "keepalives_count",
}


def to_libpq_params(params: dict[str, Any]) -> dict[str, Any]:
    """Devuelve ``params`` con nombres y valores de opción de conexión de libpq."""
    result: dict[str, Any] = {}
    for key, value in params.items():
        if key == "database":
            continue
        result[_LIBPQ_RENAMES.get(key, key)] = int(value) if isinstance(value, bool) else value
    database: Any = params.get("database")
    if database is not None:
        result.setdefault("dbname", database)
    return result


__all__: list[str] = ["to_libpq_params"]
