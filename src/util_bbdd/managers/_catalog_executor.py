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
from ..metadata._adaptive_executor import AdaptiveCatalogExecutor, inject_convert, select_strategy
from ..metadata._charset_detection import adiagnose
from ..metadata._paramstyle import ParamStyle, to_driver
from ..metadata.source import DbapiCatalogExecutor

#: Módulo raíz del driver → ``paramstyle``. Los que no declaran ``paramstyle`` o no son DB-API (``asyncpg``) van aquí;
#: el resto se lee del propio módulo.
#:
#: Extensión: Registra nuevos drivers con :func:`register_driver_paramstyle`.
#: Drivers que usan detección adaptativa de charset (MariaDB/MySQL family).
_ADAPTIVE_DRIVERS: frozenset[str] = frozenset({"mariadb", "pymysql"})
#: Drivers async de la familia MariaDB/MySQL: diagnóstico de charset y CONVERT si el diagnóstico lo pide.
_ASYNC_ADAPTIVE_DRIVERS: frozenset[str] = frozenset({"aiomysql"})


def _driver_root(connection: Any) -> str:
    """Módulo raíz del driver de ``connection``, desenvolviendo el proxy de un pool de SQLAlchemy (MySQL con pool)."""
    root = type(connection).__module__.split(".")[0]
    if root == "sqlalchemy":
        wrapped = getattr(connection, "dbapi_connection", None)
        if wrapped is not None and wrapped is not connection:
            return _driver_root(wrapped)
    return root


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


def _build_system_error_msg(total_attempts: int, exc: SystemError, is_unicode_error: bool) -> str:
    msg = (
        f"Error leyendo el catálogo de MariaDB (SystemError del driver mariadb, "
        f"{total_attempts} intentos sin fallback): {exc}"
    )
    if is_unicode_error:
        msg += " [UnicodeDecodeError subyacente en la cadena de excepciones]."
    msg += (
        "\n\nDiagnóstico:\n"
        "  (1) Verifique charset de servidor MariaDB: @@character_set_server debe ser 'utf8mb4'\n"
        "  (2) Verifique charset de sesión: @@character_set_client, @@character_set_connection\n"
        "  (3) Si information_schema contiene datos heredados de utf8mb3, limpie con:\n"
        "      ALTER TABLE <tabla> COMMENT = 'comentario nuevo limpio';\n"
        "  (4) Si @@character_set_server es 'latin1', el driver mariadb ≤ 1.1.x falla a nivel\n"
        "      C en cursor.fetchrows() aunque el SQL use CONVERT(). El CONVERT en SQL no es\n"
        "      suficiente: el driver decodifica los bytes antes de que Python los vea.\n"
        "      Solución: actualizar a mariadb ≥ 1.2 (pip install 'mariadb>=1.2') o configurar\n"
        "      @@character_set_server = utf8mb4 en el servidor MariaDB.\n"
        "  (5) Versión de mariadb driver actual: pip show mariadb\n"
        "\nDocs: https://mariadb.com/kb/en/library/character-sets-and-collations/"
    )
    return msg


class ManagerCatalogExecutor:
    """:class:`~util_bbdd.metadata.contracts.CatalogExecutor` sobre las conexiones de un manager síncrono.

    Con reintento automático mínimo (2×) para SystemError del driver mariadb.
    Sin fallback: error explícito con diagnóstico accionable (Opción E).

    Args:
        provider: Devuelve una conexión DB-API del manager (del pool o la única).
        releaser: La devuelve al pool (o no hace nada con la conexión única).
        max_retries: Número máximo de reintentos en caso de SystemError. Default: 2 (sin fallback).
    """

    def __init__(
        self,
        provider: Callable[[], Any],
        releaser: Callable[[Any], None],
        max_retries: int = 2,
        connection_params: dict[str, Any] | None = None,
    ) -> None:
        self._provider = provider
        self._releaser = releaser
        self._max_retries = max_retries
        self._adaptive: AdaptiveCatalogExecutor | None = None
        # connection_params is accepted for backward compatibility but not used (no fallback strategy)

    def _resolve_executor(self, connection: Any) -> DbapiCatalogExecutor | AdaptiveCatalogExecutor:
        """Devuelve AdaptiveCatalogExecutor para MariaDB/MySQL (también con pool), DbapiCatalogExecutor para el resto."""
        if _driver_root(connection) not in _ADAPTIVE_DRIVERS:
            return DbapiCatalogExecutor(connection, driver_paramstyle(connection))
        if self._adaptive is None:
            self._adaptive = AdaptiveCatalogExecutor(connection, driver_paramstyle(connection))
        else:
            self._adaptive.connection = connection
        return self._adaptive

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        """Ejecuta SQL de catálogo con reintento mínimo en caso de SystemError (mariadb driver).

        Usa charset validation explícita (Opción B) y error claro sin fallback (Opción E).
        Si ocurre SystemError tras agotar reintentos, lanza error con diagnóstico accionable.

        Raises:
            MetadataError: Si falla tras agotar reintentos o si ocurre otro error.
        """
        total_attempts = self._max_retries + 1  # 1 initial attempt + max_retries retries
        for attempt in range(total_attempts):
            connection = self._provider()
            try:
                logger.debug(f"[Catálogo intento {attempt + 1}/{total_attempts}] Ejecutando SQL: {sql[:80]}...")
                rows = self._resolve_executor(connection).fetch_all(sql, dict(params))
                return [tuple(_materialize(v) for v in row) for row in rows]
            except DatabaseException:
                raise
            except SystemError as exc:  # Error específico del driver mariadb (cursor corrupto)
                _rollback(connection)
                is_unicode_error = _has_unicode_error_in_chain(exc)
                # Se conserva el diagnóstico de charset: el ejecutor adaptativo ya cae a CONVERT si la lectura nativa
                # falla, y repetirlo costaba 8 consultas por reintento.

                if attempt < total_attempts - 1:
                    delay_ms = 100 * (2**attempt)  # 100ms, 200ms, ... (exponential backoff)
                    logger.warning(
                        f"SystemError en catálogo (driver mariadb, intento {attempt + 1}/{total_attempts}): {exc}. "
                        f"Retentando en {delay_ms}ms..."
                    )
                    time.sleep(delay_ms / 1000.0)
                    continue

                # Todos los intentos agotados: error explícito con diagnóstico (sin fallback)
                logger.error(f"SystemError persistente tras {total_attempts} intentos (sin fallback): {exc}")
                raise MetadataError(_build_system_error_msg(total_attempts, exc, is_unicode_error)) from exc
            except Exception as exc:  # noqa: BLE001 - error del driver
                _rollback(connection)
                raise MetadataError(f"Error leyendo el catálogo: {exc}") from exc
            finally:
                self._releaser(connection)

        # No debería llegar aquí: cada iteración hace return, raise, o continue
        raise AssertionError("Unexpected exit from retry loop")  # pragma: no cover  # type: ignore[return-value]


async def _cursor_execute(cursor: Any, driver_sql: str, args: dict[str, Any] | list[Any] | None) -> None:
    if args is None:
        await maybe_await(cursor.execute(driver_sql))
    else:
        await maybe_await(cursor.execute(driver_sql, args))


class AsyncManagerCatalogExecutor:
    """:class:`~util_bbdd.metadata.contracts.AsyncCatalogExecutor` sobre las conexiones de un manager async.

    Con ``asyncpg`` (sin cursores DB-API) usa ``connection.fetch`` y parámetros ``$n``; con el resto, un cursor.
    Con reintento automático mínimo para SystemError del driver mariadb.
    Sin fallback: error explícito con diagnóstico accionable (Opción E).

    Args:
        provider: Devuelve una conexión DB-API del manager (async).
        releaser: La devuelve al pool (async).
        max_retries: Número máximo de reintentos en caso de SystemError. Default: 2.
    """

    def __init__(
        self,
        provider: Callable[[], Awaitable[Any]],
        releaser: Callable[[Any], Awaitable[None]],
        max_retries: int = 2,
    ) -> None:
        self._provider = provider
        self._releaser = releaser
        self._max_retries = max_retries
        # Estrategia de charset (aiomysql): se diagnostica una vez con la primera conexión, como el ejecutor sync.
        self._charset_strategy: str | None = None

    async def _charset_safe_sql(self, connection: Any, sql: str) -> str:
        """``sql`` con CONVERT en los campos de texto del catálogo si el diagnóstico de charset lo pide (aiomysql)."""
        if _driver_root(connection) not in _ASYNC_ADAPTIVE_DRIVERS:
            return sql
        if self._charset_strategy is None:
            self._charset_strategy = select_strategy(await adiagnose(connection))
        return inject_convert(sql) if self._charset_strategy == "convert" else sql

    async def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        """Ejecuta SQL de catálogo con reintento mínimo en caso de SystemError (mariadb driver).

        Usa charset validation explícita (Opción B) y error claro sin fallback (Opción E).
        Si ocurre SystemError tras agotar reintentos, lanza error con diagnóstico accionable.

        Raises:
            MetadataError: Si falla tras agotar reintentos o si ocurre otro error.
        """
        total_attempts = self._max_retries + 1  # 1 initial attempt + max_retries retries
        for attempt in range(total_attempts):
            connection = await self._provider()
            try:
                logger.debug(f"[Catálogo async intento {attempt + 1}/{total_attempts}] Ejecutando SQL: {sql[:80]}...")
                style = driver_paramstyle(connection)
                driver_sql, args = to_driver(await self._charset_safe_sql(connection, sql), params, style)
                if style == "dollar":
                    records = await connection.fetch(driver_sql, *(args or []))
                    return [tuple(record) for record in records]
                cursor = await maybe_await(connection.cursor())
                try:
                    await _cursor_execute(cursor, driver_sql, args)
                    rows = await maybe_await(cursor.fetchall())
                finally:
                    await maybe_await(cursor.close())
                return [tuple(_materialize(v) for v in row) for row in rows]
            except DatabaseException:
                raise
            except SystemError as exc:  # Error específico del driver mariadb
                await _arollback(connection)
                is_unicode_error = _has_unicode_error_in_chain(exc)

                if attempt < total_attempts - 1:
                    delay_ms = 100 * (2**attempt)  # 100ms, 200ms, ... (exponential backoff)
                    logger.warning(
                        f"SystemError en catálogo async (driver mariadb, intento {attempt + 1}/{total_attempts}): {exc}. "
                        f"Retentando en {delay_ms}ms..."
                    )
                    await asyncio.sleep(delay_ms / 1000.0)
                    continue

                # Todos los intentos agotados: error explícito con diagnóstico (sin fallback)
                logger.error(f"SystemError persistente (async) tras {total_attempts} intentos (sin fallback): {exc}")
                raise MetadataError(_build_system_error_msg(total_attempts, exc, is_unicode_error)) from exc
            except Exception as exc:  # noqa: BLE001 - ver ManagerCatalogExecutor.fetch_all
                await _arollback(connection)
                raise MetadataError(f"Error leyendo el catálogo: {exc}") from exc
            finally:
                await self._releaser(connection)

        # No debería llegar aquí: cada intento termina con return o raise
        raise AssertionError("Unexpected exit from retry loop")  # pragma: no cover  # type: ignore[return-value]


__all__: list[str] = [
    "AsyncManagerCatalogExecutor",
    "ManagerCatalogExecutor",
    "driver_paramstyle",
    "register_driver_paramstyle",
]
