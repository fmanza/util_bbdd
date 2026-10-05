"""Ejecución del SQL de catálogo (``metadata``, ADR-003) con las conexiones nativas de los managers (grupo C1).

``CatalogSource`` (``metadata/``, capa 5) no conoce a los managers (capa 6): estos le inyectan un
:class:`~util_bbdd.metadata.contracts.CatalogExecutor` que pide una conexión al manager (pool o conexión única), ejecuta
la consulta con el ``paramstyle`` del driver y la devuelve.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from .._core.exceptions import DatabaseException, MetadataError
from ..async_utils import maybe_await
from ..metadata._paramstyle import ParamStyle, to_driver
from ..metadata.source import DbapiCatalogExecutor

#: Módulo raíz del driver → ``paramstyle``. Los que no declaran ``paramstyle`` o no son DB-API (``asyncpg``) van aquí;
#: el resto se lee del propio módulo.
#:
#: Extensión: Registra nuevos drivers con :func:`register_driver_paramstyle`.
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


def register_driver_paramstyle(root_module: str, style: ParamStyle) -> None:
    """Registra un nuevo driver con su ``paramstyle``.

    Extensión dinámmica de :data:`_KNOWN_STYLES` sin editar el módulo.
    Útil para drivers personalizados o futuros.

    Args:
        root_module: Raíz del módulo (p.ej. 'psycopg3').
        style: Estilo de parámetros ('named', 'pyformat', 'qmark', etc.).

    Raises:
        ValueError: Si el estilo no es válido.
    """
    valid_styles = ("named", "pyformat", "format", "qmark", "numeric")
    if style not in valid_styles:
        raise ValueError(f"Estilo '{style}' no válido. Debe ser uno de: {valid_styles}")
    _KNOWN_STYLES[root_module] = style


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


def _is_oracle_lob(value: Any) -> bool:
    """Detecta si un valor es un Oracle LOB (``oracledb.LOB`` u otro driver Oracle).

    Usa duck-typing (`hasattr(value, "read")`) pero verifica módulo para evitar falsos positivos.
    Robusto ante cambios de estructura del driver.

    Args:
        value: Valor a inspeccionar.

    Returns:
        True si es un LOB de Oracle, False en caso contrario.
    """
    if not hasattr(value, "read"):
        return False
    # Comprueba módulo (oracledb, cx_Oracle, etc.) pero no falla si cambia estructura interna
    module_name = type(value).__module__.split(".")[0]
    return module_name in ("oracledb", "cx_Oracle")


def _materialize(value: Any) -> Any:
    """LOB de Oracle (``oracledb.LOB``) → texto; el resto tal cual."""
    if _is_oracle_lob(value):
        return value.read()
    return value


logger: logging.Logger = logging.getLogger(__name__)


def _has_unicode_error_in_chain(exc: BaseException) -> bool:
    """Inspecciona la cadena de excepciones para detectar UnicodeDecodeError.

    Recorre recursivamente ``exc.__cause__`` para buscar un ``UnicodeDecodeError``.
    Útil para diagnosticar errores de charset en mariadb driver.

    Args:
        exc: Excepción raíz a inspeccionar.

    Returns:
        True si se encuentra UnicodeDecodeError en la cadena, False en caso contrario.
    """
    cause: BaseException | None = exc.__cause__
    while cause is not None:
        if isinstance(cause, UnicodeDecodeError):
            return True
        cause = cause.__cause__
    return False


def _rollback(connection: Any) -> None:
    """Deja usable la conexión tras un error (PostgreSQL aborta la transacción en curso).

    Si el rollback falla, registra el error en DEBUG sin afectar el flujo de control.
    """
    rollback = getattr(connection, "rollback", None)
    if callable(rollback):
        try:
            rollback()
        except Exception as exc:
            logger.debug(f"Rollback falló (continuando): {exc}")


async def _arollback(connection: Any) -> None:
    """Versión async de _rollback; registra errores en DEBUG."""
    rollback = getattr(connection, "rollback", None)
    if callable(rollback):
        try:
            await maybe_await(rollback())
        except Exception as exc:
            logger.debug(f"Async rollback falló (continuando): {exc}")


class ManagerCatalogExecutor:
    """:class:`~util_bbdd.metadata.contracts.CatalogExecutor` sobre las conexiones de un manager síncrono.

    Con reintento automático para SystemError del driver mariadb (cursor corrupto tras fallo silencioso).
    Usa backoff exponencial: 100ms, 200ms, 400ms (configurable).

    Args:
        provider: Devuelve una conexión DB-API del manager (del pool o la única).
        releaser: La devuelve al pool (o no hace nada con la conexión única).
        max_retries: Número máximo de reintentos en caso de SystemError. Default: 3.
    """

    def __init__(self, provider: Callable[[], Any], releaser: Callable[[Any], None], max_retries: int = 3) -> None:
        self._provider = provider
        self._releaser = releaser
        self._max_retries = max_retries

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        """Ejecuta SQL de catálogo con reintento en caso de SystemError (mariadb driver).

        Raises:
            MetadataError: Si falla tras agotar reintentos o si ocurre otro error.
        """
        for attempt in range(self._max_retries):
            connection = self._provider()
            try:
                logger.debug(f"[Catálogo intento {attempt + 1}/{self._max_retries}] Ejecutando SQL: {sql[:80]}...")
                rows = DbapiCatalogExecutor(connection, driver_paramstyle(connection)).fetch_all(sql, params)
                return [tuple(_materialize(v) for v in row) for row in rows]
            except DatabaseException:
                raise
            except SystemError as exc:  # Error específico del driver mariadb (cursor corrupto)
                _rollback(connection)

                # Check if the underlying cause is a UnicodeDecodeError
                is_unicode_error = _has_unicode_error_in_chain(exc)

                if attempt < self._max_retries - 1:
                    delay_ms = 100 * (2**attempt)
                    logger.warning(
                        f"SystemError en catálogo (driver mariadb): {exc}. "
                        f"Retentando en {delay_ms}ms (intento {attempt + 1}/{self._max_retries})..."
                    )
                    time.sleep(delay_ms / 1000.0)
                    continue

                # Último reintento agotado
                logger.error(f"SystemError persistente tras {self._max_retries} intentos: {exc}")

                # Provide helpful message for Unicode errors
                error_msg = f"Error leyendo el catálogo (SystemError del driver mariadb, retentado {self._max_retries} veces): {exc}"
                if is_unicode_error:
                    error_msg += (
                        " [UnicodeDecodeError subyacente]. Esto puede ocurrir si la conexión a MariaDB no usa "
                        "charset UTF-8. Verifique que: (1) `character_set_client`, `character_set_connection` y "
                        "`character_set_database` están configurados a 'utf8mb4' en MariaDB, "
                        "(2) los datos en `information_schema` no contienen caracteres inválidos, "
                        "(3) especifique charset='utf8mb4' en los parámetros de conexión como último recurso."
                    )
                raise MetadataError(error_msg) from exc
            except Exception as exc:  # noqa: BLE001 - error del driver
                _rollback(connection)
                raise MetadataError(f"Error leyendo el catálogo: {exc}") from exc
            finally:
                self._releaser(connection)

        # No debería llegar aquí: cada intento termina con return o raise
        raise AssertionError("Unexpected exit from retry loop")  # pragma: no cover


class AsyncManagerCatalogExecutor:
    """:class:`~util_bbdd.metadata.contracts.AsyncCatalogExecutor` sobre las conexiones de un manager async.

    Con ``asyncpg`` (sin cursores DB-API) usa ``connection.fetch`` y parámetros ``$n``; con el resto, un cursor.
    Con reintento automático para SystemError del driver mariadb (mismo que sync).

    Args:
        provider: Devuelve una conexión DB-API del manager (async).
        releaser: La devuelve al pool (async).
        max_retries: Número máximo de reintentos en caso de SystemError. Default: 3.
    """

    def __init__(
        self,
        provider: Callable[[], Awaitable[Any]],
        releaser: Callable[[Any], Awaitable[None]],
        max_retries: int = 3,
    ) -> None:
        self._provider = provider
        self._releaser = releaser
        self._max_retries = max_retries

    async def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        """Ejecuta SQL de catálogo con reintento en caso de SystemError (mariadb driver).

        Raises:
            MetadataError: Si falla tras agotar reintentos o si ocurre otro error.
        """
        for attempt in range(self._max_retries):
            connection = await self._provider()
            try:
                logger.debug(
                    f"[Catálogo async intento {attempt + 1}/{self._max_retries}] Ejecutando SQL: {sql[:80]}..."
                )
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
            except SystemError as exc:  # Error específico del driver mariadb
                await _arollback(connection)

                # Check if the underlying cause is a UnicodeDecodeError
                is_unicode_error = _has_unicode_error_in_chain(exc)

                if attempt < self._max_retries - 1:
                    delay_ms = 100 * (2**attempt)
                    logger.warning(
                        f"SystemError en catálogo async (driver mariadb): {exc}. "
                        f"Retentando en {delay_ms}ms (intento {attempt + 1}/{self._max_retries})..."
                    )
                    await asyncio.sleep(delay_ms / 1000.0)
                    continue

                # Último reintento agotado
                logger.error(f"SystemError persistente (async) tras {self._max_retries} intentos: {exc}")
                error_msg = f"Error leyendo el catálogo (SystemError del driver mariadb, retentado {self._max_retries} veces): {exc}"
                if is_unicode_error:
                    error_msg += (
                        " [UnicodeDecodeError subyacente]. Esto puede ocurrir si la conexión a MariaDB no usa "
                        "charset UTF-8. Verifique que: (1) `character_set_client`, `character_set_connection` y "
                        "`character_set_database` están configurados a 'utf8mb4' en MariaDB, "
                        "(2) los datos en `information_schema` no contienen caracteres inválidos, "
                        "(3) especifique charset='utf8mb4' en los parámetros de conexión como último recurso."
                    )
                raise MetadataError(error_msg) from exc
            except Exception as exc:  # noqa: BLE001 - ver ManagerCatalogExecutor.fetch_all
                await _arollback(connection)
                raise MetadataError(f"Error leyendo el catálogo: {exc}") from exc
            finally:
                await self._releaser(connection)

        # No debería llegar aquí: cada intento termina con return o raise
        raise AssertionError("Unexpected exit from retry loop")  # pragma: no cover


__all__: list[str] = [
    "AsyncManagerCatalogExecutor",
    "ManagerCatalogExecutor",
    "driver_paramstyle",
    "register_driver_paramstyle",
]
