"""Ejecutor async de consultas SQL."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time

from collections.abc import Awaitable, Callable
from typing import Any

from .database_exceptions import (
    DatabaseOperationError,
    QueryNotFoundError,
    QueryTimeoutError,
    QueryValidationError,
)
from .query_registry import QueryRegistry
from .query_resolver import QueryResolver


async def _maybe_await(value: Any) -> Any:
    """Espera el valor si es awaitable, si no lo devuelve sin cambios."""
    if inspect.isawaitable(value):
        return await value
    return value


class AsyncDatabaseQueryExecutor:
    """Ejecutor async independiente del motor."""

    def __init__(
        self,
        connection_provider: Callable[[], Awaitable[Any]],
        connection_releaser: Callable[[Any], Awaitable[None]],
        registry: QueryRegistry | None = None,
        resolver: QueryResolver | None = None,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self._connection_provider: Callable[[], Awaitable[Any]] = connection_provider
        self._connection_releaser: Callable[[Any], Awaitable[None]] = connection_releaser
        self.registry: QueryRegistry = registry or QueryRegistry()
        self.resolver: QueryResolver = resolver or QueryResolver(self.registry)

    async def execute_query(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
        fetch_options: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Ejecuta una query por nombre de forma asincrónica.

        Args:
            query_name: Nombre de la query registrada
            db_type: Tipo de base de datos (mariadb, oracle, etc.)
            params: Parámetros para la query
            fetch_options: Opciones de fetch (ej: {"fetch_one": True})
            timeout: Timeout en segundos

        Returns:
            Resultado de la query (tuple o list de tuples)

        Raises:
            QueryNotFoundError: Si query no existe
            QueryValidationError: Si parámetros no cumplen validación
            QueryTimeoutError: Si se excede timeout
            DatabaseOperationError: Si hay error en ejecución BD
        """
        params = params or {}
        fetch_options = fetch_options or {}
        fetch_one = fetch_options.get("fetch_one", False)
        conn: Any = None
        cursor: Any = None
        start_time = time.time()

        try:
            # Resolver la query (obtiene QueryDefinition, valida, interpola SQL)
            resolved = self.resolver.resolve(query_name, db_type, params)

            conn = await self._connection_provider()

            # Compatibilidad con conexiones de estilo cursor() o execute directo
            if hasattr(conn, "cursor"):
                cursor = await _maybe_await(conn.cursor())
                await _maybe_await(cursor.execute(resolved.final_sql, params or {}))
                if fetch_one:
                    result = await _maybe_await(cursor.fetchone())
                else:
                    result = await _maybe_await(cursor.fetchall())
            else:
                await _maybe_await(conn.execute(resolved.final_sql, params or {}))
                if fetch_one:
                    result = await _maybe_await(conn.fetchone())
                else:
                    result = await _maybe_await(conn.fetchall())

            elapsed_ms = (time.time() - start_time) * 1000
            result_rows = 1 if fetch_one else (len(result) if result else 0)

            self.logger.debug(
                f"✅ Query executed: query_name={query_name}, db_type={db_type}, "
                f"elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}"
            )

            return result

        except asyncio.TimeoutError as e:
            msg = f"Query execution exceeded timeout: {query_name}"
            raise QueryTimeoutError(msg) from e

        except (QueryNotFoundError, QueryValidationError):
            raise

        except Exception as e:
            msg = f"Error executing query {query_name}: {str(e)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "SELECT", db_type=db_type) from e

        finally:
            if cursor is not None and hasattr(cursor, "close"):
                try:
                    await _maybe_await(cursor.close())
                except Exception as err:
                    self.logger.warning(f"⚠️ Error cerrando cursor async: {err}")
            if conn is not None:
                await self._connection_releaser(conn)

    async def execute_custom_query(
        self,
        sql: str,
        params: Any | None = None,
        fetch_one: bool = False,
    ) -> Any:
        """Ejecuta SQL y devuelve una fila o todas las filas."""
        connection: Any = None
        cursor: Any = None
        try:
            connection = await self._connection_provider()

            # Compatibilidad con conexiones de estilo cursor() o execute directo.
            if hasattr(connection, "cursor"):
                cursor = await _maybe_await(connection.cursor())
                await _maybe_await(cursor.execute(sql, params))
                if fetch_one:
                    return await _maybe_await(cursor.fetchone())
                return await _maybe_await(cursor.fetchall())

            await _maybe_await(connection.execute(sql, params))
            if fetch_one:
                return await _maybe_await(connection.fetchone())
            return await _maybe_await(connection.fetchall())
        finally:
            if cursor is not None and hasattr(cursor, "close"):
                try:
                    await _maybe_await(cursor.close())
                except Exception as err:
                    self.logger.warning(f"⚠️ Error cerrando cursor async: {err}")
            if connection is not None:
                await self._connection_releaser(connection)
