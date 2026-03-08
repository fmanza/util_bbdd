"""Ejecutor de queries async"""

import asyncio
import logging
import time

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
    - Aplica timeouts
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
        self.logger = logging.getLogger(__name__)
        self.connection_provider = connection_provider
        self.connection_releaser = connection_releaser
        self.registry = registry or QueryRegistry()
        self.resolver = resolver or QueryResolver(self.registry)

    async def execute_query(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
        fetch_one: bool = False,
        timeout: float | None = None,
    ) -> Any:
        """Ejecuta una query por nombre de forma asincrónica.

        Args:
            query_name: Nombre de la query registrada
            db_type: Tipo de base de datos (mariadb, oracle, etc.)
            params: Parámetros para la query
            fetch_one: Si True, retorna un registro; si False, todos
            timeout: Timeout en segundos

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
        timeout: float | None = None,
    ) -> Any:
        """Ejecuta SQL custom directamente de forma asincrónica.

        Args:
            sql: SQL a ejecutar
            params: Parámetros para el SQL
            fetch_one: Si True, retorna un registro; si False, todos
            timeout: Timeout en segundos

        Returns:
            Resultado de la query (tuple o list de tuples, según fetch_one)

        Raises:
            QueryTimeoutError: Si se excede timeout
            DatabaseOperationError: Si hay error en ejecución BD
        """
        conn = None
        start_time = time.time()

        try:
            conn = await self.connection_provider()

            # Función de ejecución asincrónica
            async def do_execute():
                cursor = await conn.cursor() if hasattr(conn, "cursor") else conn
                await cursor.execute(sql, params or {})
                if fetch_one:
                    return await cursor.fetchone()
                else:
                    return await cursor.fetchall()

            # Aplicar timeout si se especifica
            if timeout is not None:
                result = await asyncio.wait_for(do_execute(), timeout=timeout)
            else:
                result = await do_execute()

            elapsed_ms = (time.time() - start_time) * 1000
            result_rows = 1 if fetch_one else (len(result) if result else 0)

            self.logger.debug(f"✅ Custom query executed: elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}")

            return result

        except asyncio.TimeoutError as e:
            msg = "Custom query execution exceeded timeout"
            raise QueryTimeoutError(msg) from e

        except Exception as e:
            msg = f"Error executing custom query: {str(e)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "CUSTOM", db_type="unknown") from e

        finally:
            if conn:
                await self.connection_releaser(conn)
