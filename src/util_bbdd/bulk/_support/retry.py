"""Qué errores de una carga masiva son transitorios y merecen reintento (B-13, performance-audit de bulk 2026-10-01).

Antes ``ParallelBulkLoader`` reintentaba por clase de excepción (``OperationalError``, ``TimeoutError``). Cada driver
mapea a esa clase cosas distintas: PyMySQL mete ahí errores permanentes (1045 acceso denegado, 1054 columna desconocida,
1292 valor incorrecto) y oracledb deja fuera el deadlock (ORA-00060 es ``DatabaseError``). Ahora se decide por el código
del servidor o del driver:

- Siempre: ``TimeoutError`` y los errores con los que SQLAlchemy invalidó la conexión (desconexión).
- PostgreSQL (``sqlstate``/``pgcode``): serialización ``40001``, deadlock ``40P01``, lock no disponible ``55P03``,
  apagado o reinicio del servidor ``57P01``–``57P03`` y la clase de conexión ``08``.
- MySQL/MariaDB (errno): lock wait timeout 1205, deadlock 1213, servidor desaparecido 2006, conexión perdida 2013.
- SQL Server: pyodbc por SQLSTATE (timeout ``HYT00``/``HYT01``, enlace ``08S01``…) o el error nativo 1205 (víctima de
  deadlock) en el mensaje; pymssql por número (1205).
- Oracle (``code``): deadlock 60, fin de canal 3113/3114/3135, sin listener 12541 y ``DPY-4011`` (conexión cerrada).
"""

from __future__ import annotations

import re

from typing import Any

from sqlalchemy.exc import DBAPIError

_PG_RETRIABLE_SQLSTATES: frozenset[str] = frozenset({"40001", "40P01", "55P03", "57P01", "57P02", "57P03"})
_PG_RETRIABLE_CLASSES: tuple[str, ...] = ("08",)

# MySQL/MariaDB y pymssql dan el número de error como entero en args[0] (o en errno).
_RETRIABLE_ERRNOS: frozenset[int] = frozenset({1205, 1213, 2006, 2013})

_ODBC_RETRIABLE_SQLSTATES: frozenset[str] = frozenset({"HYT00", "HYT01", "08S01", "08001", "08003", "08004", "40001"})
# Error nativo de SQL Server en el mensaje de pyodbc: "... (1205) (SQLExecDirectW)".
_MSSQL_NATIVE_IN_MESSAGE = re.compile(r"\((1205)\)")

_ORACLE_RETRIABLE_CODES: frozenset[int] = frozenset({60, 3113, 3114, 3135, 12541})
_ORACLE_RETRIABLE_FULL_CODES: frozenset[str] = frozenset({"DPY-4011"})


def is_retriable(exc: BaseException) -> bool:
    """``True`` si ``exc`` es un error transitorio de la BD o de la conexión (reintentar puede funcionar)."""
    if isinstance(exc, TimeoutError):
        return True
    if not isinstance(exc, DBAPIError):
        return False
    if exc.connection_invalidated:
        return True
    return _driver_error_is_retriable(exc.orig)


def _driver_error_is_retriable(orig: Any) -> bool:
    """Decide por el código que expone el error del driver (ver el docstring del módulo)."""
    # Primero el errno: los errores del conector ``mariadb`` llevan también ``sqlstate`` (lock wait timeout 1205 →
    # ``HY000``) y, decididos por sqlstate, no se reintentaban (A2, audit-code 2026-10-01).
    errno = getattr(orig, "errno", None)  # conector mariadb
    if isinstance(errno, int) and not isinstance(errno, bool):
        return errno in _RETRIABLE_ERRNOS
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)  # psycopg 3 / psycopg2
    if isinstance(sqlstate, str):
        return sqlstate in _PG_RETRIABLE_SQLSTATES or sqlstate.startswith(_PG_RETRIABLE_CLASSES)
    args: tuple[Any, ...] = tuple(getattr(orig, "args", ()))
    if not args:
        return False
    first = args[0]
    code = getattr(first, "code", None)  # oracledb: args[0] es un _Error con code y full_code
    if isinstance(code, int):
        return code in _ORACLE_RETRIABLE_CODES or getattr(first, "full_code", None) in _ORACLE_RETRIABLE_FULL_CODES
    if isinstance(first, int) and not isinstance(first, bool):  # PyMySQL, pymssql
        return first in _RETRIABLE_ERRNOS
    if isinstance(first, str):  # pyodbc: (sqlstate, mensaje)
        message = str(args[1]) if len(args) > 1 else ""
        return first in _ODBC_RETRIABLE_SQLSTATES or bool(_MSSQL_NATIVE_IN_MESSAGE.search(message))
    return False


__all__: list[str] = ["is_retriable"]
