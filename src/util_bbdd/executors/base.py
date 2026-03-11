"""Clase base para ejecutores de queries (sync y async).

Define la interfaz común y utilidades compartidas para la ejecución
de queries SQL en modo sincrónico y asincrónico.
"""

import logging
import time

from abc import ABC, abstractmethod
from typing import Any

from .._core import (
    DatabaseOperationError,
    QueryNotFoundError,
    QueryTimeoutError,
    QueryValidationError,
)
from ..query.registry import QueryRegistry
from ..query.resolver import QueryResolver
from ..result_normalizer import ResultNormalizer
from ..result_types import RowOrNone, Rows

__all__ = ["QueryExecutorBase"]


class QueryExecutorBase(ABC):
    """Clase base abstracta para ejecutores de queries.

    Define la interfaz común y utilidades compartidas entre
    AsyncQueryExecutor y SyncQueryExecutor.

    Responsabilidades:
    - Inicializar dependencias (providers, resolver, normalizer)
    - Validación y resolución de queries
    - Manejo de timeouts
    - Normalización de resultados
    """

    def __init__(
        self,
        connection_provider: Any,
        connection_releaser: Any,
        registry: QueryRegistry | None = None,
        resolver: QueryResolver | None = None,
    ) -> None:
        """Inicializa el ejecutor con dependencias inyectadas.

        Args:
            connection_provider: Callable para obtener conexión
            connection_releaser: Callable para liberar conexión
            registry: QueryRegistry (opcional, crea default si es None)
            resolver: QueryResolver (opcional, crea default si es None)
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.connection_provider = connection_provider
        self.connection_releaser = connection_releaser
        self.registry: QueryRegistry = registry or QueryRegistry()
        self.resolver: QueryResolver = resolver or QueryResolver(self.registry)
        self.result_normalizer = ResultNormalizer()

        self.logger.debug(
            f"✅ {self.__class__.__name__} initialized with "
            f"provider={type(connection_provider).__name__}, "
            f"releaser={type(connection_releaser).__name__}"
        )

    @staticmethod
    def _build_deadline(timeout: float | None) -> float | None:
        """Construye deadline absoluto desde timeout relativo.

        Args:
            timeout: Timeout en segundos (None = sin timeout)

        Returns:
            Timestamp absoluto (monotonic) o None si sin timeout
        """
        if timeout is None:
            return None
        return time.monotonic() + timeout

    @staticmethod
    def _raise_if_timed_out(deadline: float | None, message: str) -> None:
        """Levanta excepción si se excede deadline.

        Args:
            deadline: Timestamp deadline absoluto
            message: Mensaje de error si timeout

        Raises:
            DbQueryTimeoutError: Si time.monotonic() >= deadline
        """
        if deadline is None:
            return
        if time.monotonic() >= deadline:
            raise QueryTimeoutError(
                message=message,
                operation="EXECUTE_QUERY",
                db_type=None,
            )

    def _resolve_query(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Resuelve una query usando el resolver.

        Args:
            query_name: Nombre de la query
            db_type: Tipo de BD
            params: Parámetros (opcional)

        Returns:
            ResolvedQuery con SQL final y metadatos

        Raises:
            QueryNotFoundError: Si query no existe
            QueryValidationError: Si validación falla
            DatabaseOperationError: En error general
        """
        try:
            self.logger.debug(f"Resolving query: {query_name} for db_type={db_type}")
            resolved = self.resolver.resolve(query_name, db_type, params or {})
            self.logger.debug(f"✅ Query resolved: {query_name}, params={list((params or {}).keys())}")
            return resolved

        except (QueryNotFoundError, QueryValidationError):
            raise

        except Exception as err:
            self.logger.error(
                f"❌ Error resolving query '{query_name}': {err}",
                exc_info=True,
            )
            raise DatabaseOperationError(
                message=f"Error resolving query '{query_name}'",
                operation="RESOLVE_QUERY",
                db_type=db_type,
                details=str(err),
            ) from err

    @abstractmethod
    async def execute_one(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
    ) -> RowOrNone:
        """Ejecuta query y espera una fila o None (async interface).

        Debe ser implementado por subclases.

        Args:
            query_name: Nombre de la query
            db_type: Tipo de BD
            params: Parámetros

        Returns:
            Una fila o None
        """
        ...

    @abstractmethod
    async def execute_many(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
    ) -> Rows:
        """Ejecuta query y espera múltiples filas (async interface).

        Debe ser implementado por subclases.

        Args:
            query_name: Nombre de la query
            db_type: Tipo de BD
            params: Parámetros

        Returns:
            Lista de filas
        """
        ...
