"""Driver ODBC de SQL Server por defecto: el más reciente instalado (5.7.0).

Hasta 5.6.0 el valor por defecto era siempre «ODBC Driver 17 for SQL Server» y, con solo el 18 instalado, había que
indicar ``driver_name``. Ahora, si no se indica, se usa el «ODBC Driver NN for SQL Server» de número más alto que
liste ``pyodbc.drivers()``; si no hay ninguno (o falta pyodbc, o unixODBC no está configurado), el 17 de siempre.
Un ``driver_name`` explícito manda siempre.

El cambio de 17 a 18 no altera el cifrado: ``Encrypt`` y ``TrustServerCertificate`` se escriben siempre en la cadena
de conexión (``SQLServerConnection.odbc_encrypt``).
"""

from __future__ import annotations

import functools
import logging
import re

from collections.abc import Iterable, Mapping
from typing import Any

logger = logging.getLogger(__name__)

#: Valor por defecto si no hay ningún driver ODBC de SQL Server detectable (el de siempre hasta 5.6.0)
FALLBACK_ODBC_DRIVER: str = "ODBC Driver 17 for SQL Server"
_MS_DRIVER: re.Pattern[str] = re.compile(r"^ODBC Driver (\d+) for SQL Server$")


def newest_odbc_driver(installed: Iterable[str]) -> str | None:
    """El «ODBC Driver NN for SQL Server» de número más alto entre ``installed`` (``None`` si no hay ninguno)."""
    versions = [(int(match.group(1)), name) for name in installed if (match := _MS_DRIVER.match(name))]
    return max(versions)[1] if versions else None


@functools.cache
def default_odbc_driver() -> str:
    """Driver ODBC por defecto del proceso: el más reciente instalado o :data:`FALLBACK_ODBC_DRIVER` (en caché)."""
    try:
        import pyodbc

        installed: list[str] = list(pyodbc.drivers())
    except Exception as error:  # ImportError o error del Driver Manager: se mantiene el comportamiento anterior
        logger.debug(f"Sin lista de drivers ODBC ({type(error).__name__}); se usa {FALLBACK_ODBC_DRIVER}")
        return FALLBACK_ODBC_DRIVER
    chosen = newest_odbc_driver(installed) or FALLBACK_ODBC_DRIVER
    logger.debug(f"Driver ODBC de SQL Server por defecto: {chosen} (instalados: {installed})")
    return chosen


def resolve_odbc_driver(conn_params: Mapping[str, Any]) -> str:
    """``driver_name`` de ``conn_params`` si se indicó (no vacío); si no, :func:`default_odbc_driver`."""
    explicit = conn_params.get("driver_name")
    return str(explicit) if explicit else default_odbc_driver()


__all__: list[str] = ["FALLBACK_ODBC_DRIVER", "default_odbc_driver", "newest_odbc_driver", "resolve_odbc_driver"]
