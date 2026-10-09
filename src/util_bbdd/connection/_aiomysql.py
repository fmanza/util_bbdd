"""Traducción única de los kwargs de ``MariaDBConnectionConfig``/``MySQLConnectionConfig`` a ``aiomysql.connect``.

La usan la conexión y el pool async de MariaDB y de MySQL (antes había tres implementaciones con listas distintas).
"""

from __future__ import annotations

import inspect
import logging
import ssl

from collections.abc import Collection
from typing import Any

from ._advisory import warn_once
from .mysql.connection_mysql import build_ssl_context, pop_mysql_ssl_options

logger: logging.Logger = logging.getLogger(__name__)

#: Parámetros con nombre de ``aiomysql.connect`` (0.3.2). Se usan si ``connect`` acepta ``**kwargs`` (dobles de test o
#: envoltorios), cuya firma no dice qué admite el driver real.
AIOMYSQL_CONNECT_PARAMS: frozenset[str] = frozenset(
    {
        "host",
        "user",
        "password",
        "db",
        "port",
        "unix_socket",
        "charset",
        "sql_mode",
        "read_default_file",
        "conv",
        "use_unicode",
        "client_flag",
        "cursorclass",
        "init_command",
        "connect_timeout",
        "read_default_group",
        "autocommit",
        "echo",
        "local_infile",
        "loop",
        "ssl",
        "auth_plugin",
        "program_name",
        "server_public_key",
    }
)


def _supported_params(connect: Any) -> set[str]:
    parameters = inspect.signature(connect).parameters.values()
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters):
        return set(AIOMYSQL_CONNECT_PARAMS)
    return {p.name for p in parameters if p.kind is not inspect.Parameter.VAR_POSITIONAL}


def build_aiomysql_connect_kwargs(
    driver_kwargs: dict[str, Any],
    connect: Any,
    *,
    exclude: Collection[str] = (),
) -> dict[str, Any]:
    """Adapta los kwargs de una config MySQL/MariaDB a la firma real de ``aiomysql.connect``.

    aiomysql llama ``db`` a la base de datos y no acepta ``read_timeout``/``write_timeout`` ni las claves TLS de
    PyMySQL: los parámetros ``ssl_*`` se convierten en ``ssl=SSLContext`` (misma semántica que el camino sync, ver
    :func:`~util_bbdd.connection.mysql.connection_mysql.build_ssl_context`) y se descarta (con aviso) todo lo que su
    firma no admita.

    Args:
        driver_kwargs: Salida de ``<Motor>ConnectionConfig.to_driver_kwargs()`` (o de la config de pool).
        connect: ``aiomysql.connect`` (se inspecciona su firma).
        exclude: Claves que no se envían aunque el driver las admita. MariaDB excluye ``init_command``: su
            ``SET NAMES utf8mb4`` es para el conector sync y en async pisaría ``charset``.
    """
    kwargs: dict[str, Any] = {key: value for key, value in driver_kwargs.items() if key not in exclude}
    if "database" in kwargs:
        kwargs["db"] = kwargs.pop("database")
    supported: set[str] = _supported_params(connect)
    # ``ssl=True`` (MariaDB) activa TLS aunque no haya ficheros; aiomysql solo acepta ``ssl=SSLContext``.
    tls_requested: bool = kwargs.pop("ssl", None) is True
    ssl_options: dict[str, Any] = pop_mysql_ssl_options(kwargs)
    if (ssl_options or tls_requested) and "ssl" in supported:
        ctx = build_ssl_context(ssl_options)
        if ctx.verify_mode == ssl.CERT_NONE:
            # Una vez por servidor: el async_creator de un AsyncEngine pasa por aquí en cada conexión nueva.
            warn_once(
                logger,
                ("aiomysql-tls-unverified", kwargs.get("host"), kwargs.get("port")),
                "⚠️ TLS async sin verificar el certificado del servidor: indique ssl_ca para verificarlo",
            )
        kwargs["ssl"] = ctx
    elif ssl_options or tls_requested:
        logger.warning("⚠️ El connect async no acepta 'ssl': la conexión no usará TLS")
    discarded: set[str] = set(kwargs) - supported
    if discarded:
        logger.debug(f"Parámetros no soportados por aiomysql.connect descartados: {sorted(discarded)}")
    return {key: value for key, value in kwargs.items() if key in supported and value is not None}
