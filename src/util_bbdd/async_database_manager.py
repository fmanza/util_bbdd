"""Gestor async de conexiones y ejecucion de consultas."""

from __future__ import annotations

import inspect
import logging

from collections.abc import Awaitable, Callable
from typing import Any

from .async_database_query_executor import AsyncDatabaseQueryExecutor
from .connection.connect_factory import ConnectFactory
from .factory.pool_factory import PoolFactory


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class AsyncDatabaseManager:
    """Manager async-first para conexiones directas o con pool."""

    def __init__(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        use_pool: bool = True,
        connection_factory: Callable[..., Awaitable[Any]] | None = None,
        pool_factory: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.db_type: str = db_type.lower().strip()
        self.conn_params: dict[str, Any] = conn_params
        self.use_pool: bool = use_pool
        self._connection_factory: Callable[..., Awaitable[Any]] = (
            connection_factory or ConnectFactory.create_async_connection
        )
        self._pool_factory: Callable[..., Awaitable[Any]] = pool_factory or PoolFactory.create_async_pool

        self._initialized: bool = False
        self._connection: Any = None
        self.pool_connection: Any = None
        self.query_executor: AsyncDatabaseQueryExecutor | None = None

    async def ainit(self) -> AsyncDatabaseManager:
        """Inicializa recursos async una única vez."""
        if self._initialized:
            return self

        if self.use_pool:
            try:
                self.pool_connection = await self._pool_factory(self.db_type, self.conn_params)
            except NotImplementedError:
                self.use_pool = False

        if not self.use_pool:
            self._connection = await self._connection_factory(self.db_type, self.conn_params)

        self.query_executor = AsyncDatabaseQueryExecutor(
            connection_provider=self.get_connection,
            connection_releaser=self.release_connection,
        )
        self._initialized = True
        return self

    async def __aenter__(self) -> AsyncDatabaseManager:
        return await self.ainit()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.aclose()

    async def get_connection(self) -> Any:
        """Obtiene conexión del pool o directa."""
        if not self._initialized:
            await self.ainit()

        if self.pool_connection is not None:
            return await _maybe_await(self.pool_connection.acquire())

        return self._connection

    async def release_connection(self, connection: Any) -> None:
        """Libera conexión al pool o no-op en conexión directa."""
        if self.pool_connection is None:
            return
        await _maybe_await(self.pool_connection.release(connection))

    async def execute_custom_query(
        self,
        sql: str,
        params: Any | None = None,
        fetch_one: bool = False,
    ) -> Any:
        """Ejecuta SQL usando el executor async."""
        if not self._initialized:
            await self.ainit()

        if self.query_executor is None:
            raise RuntimeError("AsyncDatabaseQueryExecutor no inicializado")

        return await self.query_executor.execute_custom_query(
            sql=sql,
            params=params,
            fetch_one=fetch_one,
        )

    async def execute_query(
        self,
        query_name: str,
        fetch_one: bool = False,
        **params,
    ) -> Any:
        """Ejecuta query registrada por nombre usando el executor async.

        Args:
            query_name: Nombre de la query registrada
            fetch_one: Si True devuelve una fila, si False todas
            **params: Parámetros para la query

        Returns:
            Resultado de la query (lista de filas o una fila)

        Raises:
            QueryNotFoundError: Si la query no existe
            QueryValidationError: Si validación de parámetros falla
            RuntimeError: Si executor no está inicializado
        """
        if not self._initialized:
            await self.ainit()

        if self.query_executor is None:
            raise RuntimeError("AsyncDatabaseQueryExecutor no inicializado")

        return await self.query_executor.execute_query(
            query_name=query_name,
            db_type=self.db_type,
            params=params,
            fetch_one=fetch_one,
        )

    async def aclose(self) -> None:
        """Cierra pool o conexión directa."""
        if self.pool_connection is not None:
            await _maybe_await(self.pool_connection.aclose())
            self.pool_connection = None

        if self._connection is not None and hasattr(self._connection, "close"):
            await _maybe_await(self._connection.close())
            self._connection = None
