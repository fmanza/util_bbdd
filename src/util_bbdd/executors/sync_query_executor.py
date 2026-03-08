"""Ejecutor de queries sync"""

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


class SyncQueryExecutor:
    """Ejecuta queries SQL de forma sincrónica.

    Responsabilidades:
    - Resuelve queries por nombre usando QueryRegistry
    - Valida parámetros usando validadores específicos por motor
    - Ejecuta SQL contra conexión SQLAlchemy
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
        """Inicializa SyncQueryExecutor.

        Args:
            connection_provider: Callable que obtiene conexión para cada operación
            connection_releaser: Callable que libera conexión al finalizar
            registry: QueryRegistry (si None, crea una nueva)
            resolver: QueryResolver (si None, crea una nueva)
        """
        self.logger = logging.getLogger(__name__)
        self.connection_provider = connection_provider
        self.connection_releaser = connection_releaser
        self.registry = registry or QueryRegistry()
        self.resolver = resolver or QueryResolver(self.registry)

    def execute_query(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any],
        fetch_one: bool = False,
        timeout: float | None = None,
    ) -> Any:
        """Ejecuta una query por nombre.

        Args:
            query_name: Nombre de la query registrada
            db_type: Tipo de base de datos (mariadb, oracle, etc.)
            params: Parámetros para la query
            fetch_one: Si True, retorna un registro; si False, todos
            timeout: Timeout en segundos (no implementado en sync, para future-proofing)

        Returns:
            Resultado de la query (tuple o list de tuples, según fetch_one)

        Raises:
            QueryNotFoundError: Si query no existe
            QueryValidationError: Si parámetros no cumplen validación
            QueryTimeoutError: Si se excede timeout
            DatabaseOperationError: Si hay error en ejecución BD
        """
        conn = None
        start_time = time.time()

        try:
            # Resolver la query (obtiene QueryDefinition, valida, interpola SQL)
            resolved = self.resolver.resolve(query_name, db_type, params)

            conn = self.connection_provider()

            # Ejecutar el SQL resuelto
            cursor = conn.cursor()
            cursor.execute(resolved.final_sql, params or {})

            result = cursor.fetchone() if fetch_one else cursor.fetchall()

            elapsed_ms = (time.time() - start_time) * 1000
            result_rows = 1 if fetch_one else (len(result) if result else 0)

            self.logger.debug(
                f"✅ Query executed: query_name={query_name}, db_type={db_type}, "
                f"elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}"
            )

            return result

        except TimeoutError as e:
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
                self.connection_releaser(conn)

    def execute_custom_query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        fetch_one: bool = False,
        timeout: float | None = None,
    ) -> Any:
        """Ejecuta SQL custom directamente.

        Args:
            sql: SQL a ejecutar
            params: Parámetros para el SQL
            fetch_one: Si True, retorna un registro; si False, todos
            timeout: Timeout en segundos (no implementado en sync, para future-proofing)

        Returns:
            Resultado de la query (tuple o list de tuples, según fetch_one)

        Raises:
            QueryTimeoutError: Si se excede timeout
            DatabaseOperationError: Si hay error en ejecución BD
        """
        conn = None
        start_time = time.time()

        try:
            conn = self.connection_provider()

            cursor = conn.cursor()
            cursor.execute(sql, params or {})

            result = cursor.fetchone() if fetch_one else cursor.fetchall()

            elapsed_ms = (time.time() - start_time) * 1000
            result_rows = 1 if fetch_one else (len(result) if result else 0)

            self.logger.debug(f"✅ Custom query executed: elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}")

            return result

        except TimeoutError as e:
            msg = "Custom query execution exceeded timeout"
            raise QueryTimeoutError(msg) from e

        except Exception as e:
            msg = f"Error executing custom query: {str(e)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "CUSTOM", db_type="unknown") from e

        finally:
            if conn:
                self.connection_releaser(conn)
