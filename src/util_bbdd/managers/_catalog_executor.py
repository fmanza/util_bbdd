"""Ejecución del SQL de catálogo (``metadata``, ADR-003) con las conexiones nativas de los managers (grupo C1).

``CatalogSource`` (``metadata/``, capa 5) no conoce a los managers (capa 6): estos le inyectan un
:class:`~util_bbdd.metadata.contracts.CatalogExecutor` que pide una conexión al manager (pool o conexión única), ejecuta
la consulta con el ``paramstyle`` del driver y la devuelve.
"""

from __future__ import annotations

import contextlib
import sys

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from .._core.exceptions import DatabaseException, MetadataError
from ..async_utils import maybe_await
from ..metadata._paramstyle import ParamStyle, to_driver
from ..metadata.source import DbapiCatalogExecutor

#: Módulo raíz del driver → ``paramstyle``. Los que no declaran ``paramstyle`` o no son DB-API (``asyncpg``) van aquí;
#: el resto se lee del propio módulo.
_KNOWN_STYLES: dict[str, ParamStyle] = {
    "psycopg": "pyformat",
    "psycopg2": "pyformat",
    "oracledb": "named",
    "cx_Oracle": "named",
    "pymssql": "pyformat",
    "pyodbc": "qmark",
    "aioodbc": "qmark",
    "mariadb": "qmark",
    "pymysql": "pyformat",
    "aiomysql": "pyformat",
    "sqlite3": "qmark",
    "aiosqlite": "qmark",
    "jaydebeapi": "qmark",
    "asyncpg": "dollar",
}


def driver_paramstyle(connection: Any) -> ParamStyle:
    """``paramstyle`` del driver de ``connection`` (por el módulo de su clase).

    Raises:
        MetadataError: Si el driver es desconocido y su módulo no declara ``paramstyle``.
    """
    root = type(connection).__module__.split(".")[0]
    if root == "sqlalchemy":
        # Conexión de un pool de SQLAlchemy (``_ConnectionFairy``, p.ej. MySQL con pool): el estilo es el del driver
        wrapped = getattr(connection, "dbapi_connection", None)
        if wrapped is not None and wrapped is not connection:
            return driver_paramstyle(wrapped)
    known = _KNOWN_STYLES.get(root)
    if known is not None:
        return known
    declared = getattr(sys.modules.get(root), "paramstyle", None)
    if declared in ("named", "pyformat", "format", "qmark", "numeric"):
        return declared  # type: ignore[no-any-return]
    raise MetadataError(f"No se conoce el paramstyle del driver '{root}' para leer el catálogo")


def _materialize(value: Any) -> Any:
    """LOB de Oracle (``oracledb.LOB``) → texto; el resto tal cual."""
    if type(value).__module__.startswith("oracledb") and hasattr(value, "read"):
        return value.read()
    return value


def _rollback(connection: Any) -> None:
    """Deja usable la conexión tras un error (PostgreSQL aborta la transacción en curso)."""
    rollback = getattr(connection, "rollback", None)
    if callable(rollback):
        with contextlib.suppress(Exception):
            rollback()


async def _arollback(connection: Any) -> None:
    rollback = getattr(connection, "rollback", None)
    if callable(rollback):
        with contextlib.suppress(Exception):
            await maybe_await(rollback())


class ManagerCatalogExecutor:
    """:class:`~util_bbdd.metadata.contracts.CatalogExecutor` sobre las conexiones de un manager síncrono.

    Args:
        provider: Devuelve una conexión DB-API del manager (del pool o la única).
        releaser: La devuelve al pool (o no hace nada con la conexión única).
    """

    def __init__(self, provider: Callable[[], Any], releaser: Callable[[Any], None]) -> None:
        self._provider = provider
        self._releaser = releaser

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        connection = self._provider()
        try:
            rows = DbapiCatalogExecutor(connection, driver_paramstyle(connection)).fetch_all(sql, params)
            return [tuple(_materialize(v) for v in row) for row in rows]
        except DatabaseException:
            raise
        except Exception as exc:  # noqa: BLE001 - error del driver (cada uno tiene su jerarquía) → excepción de la librería
            _rollback(connection)
            raise MetadataError(f"Error leyendo el catálogo: {exc}") from exc
        finally:
            self._releaser(connection)


class AsyncManagerCatalogExecutor:
    """:class:`~util_bbdd.metadata.contracts.AsyncCatalogExecutor` sobre las conexiones de un manager async.

    Con ``asyncpg`` (sin cursores DB-API) usa ``connection.fetch`` y parámetros ``$n``; con el resto, un cursor.
    """

    def __init__(self, provider: Callable[[], Awaitable[Any]], releaser: Callable[[Any], Awaitable[None]]) -> None:
        self._provider = provider
        self._releaser = releaser

    async def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        connection = await self._provider()
        try:
            style = driver_paramstyle(connection)
            driver_sql, args = to_driver(sql, params, style)
            if style == "dollar":
                records = await connection.fetch(driver_sql, *(args or []))
                return [tuple(record) for record in records]
            cursor = await maybe_await(connection.cursor())
            try:
                if args is None:
                    await maybe_await(cursor.execute(driver_sql))
                else:
                    await maybe_await(cursor.execute(driver_sql, args))
                rows = await maybe_await(cursor.fetchall())
            finally:
                await maybe_await(cursor.close())
            return [tuple(_materialize(v) for v in row) for row in rows]
        except DatabaseException:
            raise
        except Exception as exc:  # noqa: BLE001 - ver ManagerCatalogExecutor.fetch_all
            await _arollback(connection)
            raise MetadataError(f"Error leyendo el catálogo: {exc}") from exc
        finally:
            await self._releaser(connection)


__all__: list[str] = ["AsyncManagerCatalogExecutor", "ManagerCatalogExecutor", "driver_paramstyle"]
