"""Ejecutor de queries async"""

import asyncio
import logging
import time

from contextlib import asynccontextmanager
from typing import Any

from ..database_exceptions import (
    DatabaseOperationError,
    QueryNotFoundError,
    QueryTimeoutError,
    QueryValidationError,
)
from ..query_registry import QueryRegistry
from ..query_resolver import QueryResolver


class AsyncQueryExecutor:
    """Ejecuta queries SQL de forma asincrónica.

    Responsabilidades:
    - Resuelve queries por nombre usando QueryResolver
    - Valida parámetros usando validadores específicos por motor
    - Ejecuta SQL contra conexión SQLAlchemy async
    - Maneja lifecycle de conexiones (acquire/release)
    - Aplica timeouts configurables por instancia
    """

    def __init__(
        self,
        connection_provider,
        connection_releaser,
        registry: QueryRegistry | None = None,
        resolver: QueryResolver | None = None,
    ) -> None:
        """Inicializa AsyncQueryExecutor.

        Args:
            connection_provider: Coroutine que obtiene conexión para cada operación
            connection_releaser: Coroutine que libera conexión al finalizar
            registry: QueryRegistry (si None, crea una nueva)
            resolver: QueryResolver (si None, crea una nueva)
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.connection_provider = connection_provider
        self.connection_releaser = connection_releaser
        self.registry: QueryRegistry = registry or QueryRegistry()
        self.resolver: QueryResolver = resolver or QueryResolver(self.registry)
        self.query_timeout: float | None = None

    @asynccontextmanager
    async def _timeout_context(self, timeout_message: str):
        """Context manager para aplicar timeout homogéneo en operaciones async."""
        if self.query_timeout is None:
            yield
            return

        try:
            async with asyncio.timeout(self.query_timeout):
                yield
        except TimeoutError as e:
            raise QueryTimeoutError(timeout_message) from e

    async def execute_query(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
        fetch_one: bool = False,
    ) -> Any:
        """Ejecuta una query por nombre de forma asincrónica.

        Args:
            query_name: Nombre de la query registrada
            db_type: Tipo de base de datos (mariadb, oracle, etc.)
            params: Parámetros para la query
            fetch_one: Si True, retorna un registro; si False, todos

        Returns:
            Resultado de la query (tuple o list de tuples, según fetch_one)

        Raises:
            QueryNotFoundError: Si query no existe
            QueryValidationError: Si parámetros no cumplen validación
            QueryTimeoutError: Si se excede timeout
            DatabaseOperationError: Si hay error en ejecución BD
        """
        params = params or {}
        conn = None
        start_time = time.time()

        try:
            async with self._timeout_context(f"Query execution exceeded timeout: {query_name}"):
                # Resolver la query (obtiene QueryDefinition, valida, interpola SQL)
                resolved = self.resolver.resolve(query_name, db_type, params)

                conn = await self.connection_provider()

                # Ejecutar el SQL resuelto
                cursor = await conn.cursor() if hasattr(conn, "cursor") else conn
                await cursor.execute(resolved.final_sql, params or {})

                if fetch_one:
                    result = await cursor.fetchone()
                else:
                    result = await cursor.fetchall()

            elapsed_ms: float = (time.time() - start_time) * 1000
            if fetch_one:
                result_rows = 1
            else:
                if result:
                    result_rows: int = len(result)
                else:
                    result_rows = 0

            self.logger.debug(
                f"✅ Query executed: query_name={query_name}, db_type={db_type}, "
                f"elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}"
            )

            return result

        except (QueryNotFoundError, QueryValidationError, QueryTimeoutError):
            # Re-raise estos errores conocidos sin envolver
            raise

        except Exception as e:
            # Wrap unexpected errors
            msg = f"Error executing query {query_name}: {str(e)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "SELECT", db_type=db_type) from e

        finally:
            if conn:
                await self.connection_releaser(conn)

    async def execute_custom_query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        fetch_one: bool = False,
    ) -> Any:
        """Ejecuta SQL custom directamente de forma asincrónica.

        Args:
            sql: SQL a ejecutar
            params: Parámetros para el SQL
            fetch_one: Si True, retorna un registro; si False, todos

        Returns:
            Resultado de la query (tuple o list de tuples, según fetch_one)

        Raises:
            QueryTimeoutError: Si se excede timeout
            DatabaseOperationError: Si hay error en ejecución BD
        """
        conn = None
        start_time = time.time()

        try:
            async with self._timeout_context("Custom query execution exceeded timeout"):
                conn = await self.connection_provider()

                cursor = await conn.cursor() if hasattr(conn, "cursor") else conn
                await cursor.execute(sql, params or {})
                if fetch_one:
                    result = await cursor.fetchone()
                else:
                    result = await cursor.fetchall()

            elapsed_ms: float = (time.time() - start_time) * 1000
            if fetch_one:
                result_rows = 1
            else:
                if result:
                    result_rows: int = len(result)
                else:
                    result_rows = 0

            self.logger.debug(f"✅ Custom query executed: elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}")

            return result

        except QueryTimeoutError:
            raise

        except Exception as e:
            msg = f"Error executing custom query: {str(e)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "CUSTOM", db_type="unknown") from e

        finally:
            if conn:
                await self.connection_releaser(conn)
