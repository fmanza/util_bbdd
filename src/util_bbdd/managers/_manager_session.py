"""Gestores de sesión para conexiones sync y async."""

from __future__ import annotations

import logging

from typing import Any

from ..connection.protocols import ConnectionPoolProtocol
from ..executors.sync_query_executor import SyncQueryExecutor
from ._manager_lifecycle import get_sync_connection, release_sync_connection


class SyncSessionManager:
    """Gestor de sesión para operaciones sync."""

    def __init__(self, pool_connection: ConnectionPoolProtocol | None, logger: logging.Logger) -> None:
        """
        Inicializa el gestor de sesión sync.

        Args:
            pool_connection: Pool de conexiones opcional.
            logger: Logger para mensajes.
        """
        self.pool_connection = pool_connection
        self.logger = logger
        self._connection: Any = None
        self._cursor: Any = None

    def get_connection(self, connection: Any | None = None, db_type: str = "") -> Any:
        """
        Obtiene conexión del pool o directa.

        Args:
            connection: Conexión directa (si no hay pool).
            db_type: Tipo de base de datos (para logging).

        Returns:
            Conexión a la base de datos.
        """
        return get_sync_connection(
            pool_connection=self.pool_connection,
            connection=connection,
            db_type=db_type,
            logger=self.logger,
        )

    def close_connection(self, connection: Any | None = None) -> None:
        """
        Devuelve conexión al pool o la cierra.

        Args:
            connection: Conexión a cerrar/devolver.
        """
        release_sync_connection(pool_connection=self.pool_connection, connection=connection, logger=self.logger)

    def build_sync_executor(
        self,
        connection_provider: Any,
        connection_releaser: Any,
        registry: Any,
        resolver: Any,
    ) -> SyncQueryExecutor:
        """
        Construye ejecutor sync para consultas.

        Args:
            connection_provider: Función que obtiene conexión.
            connection_releaser: Función que libera conexión.
            registry: Registro de consultas.
            resolver: Resolutor de consultas.

        Returns:
            SyncQueryExecutor configurado.
        """
        executor = SyncQueryExecutor(
            connection_provider=connection_provider,
            connection_releaser=connection_releaser,
            registry=registry,
            resolver=resolver,
        )
        self.logger.debug("✅ Query executor sync inicializado")
        return executor


class AsyncSessionManager:
    """Gestor de sesión para operaciones async."""

    def __init__(self, pool_connection: Any | None, logger: logging.Logger) -> None:
        """
        Inicializa el gestor de sesión async.

        Args:
            pool_connection: Pool de conexiones async opcional.
            logger: Logger para mensajes.
        """
        self.pool_connection = pool_connection
        self.logger = logger
        self._connection: Any = None

    async def get_connection(self) -> Any:
        """
        Obtiene conexión del pool o directa (async).

        Returns:
            Conexión a la base de datos.
        """
        from ._manager_lifecycle import get_async_connection

        return await get_async_connection(
            initialized=True,
            ensure_initialized=self._noop_init,
            pool_connection=self.pool_connection,
            connection=self._connection,
        )

    async def release_connection(self, connection: Any) -> None:
        """
        Libera conexión al pool o no-op (async).

        Args:
            connection: Conexión a liberar.
        """
        from ._manager_lifecycle import release_async_connection

        await release_async_connection(pool_connection=self.pool_connection, connection=connection)

    async def _noop_init(self) -> None:
        """Inicialización no-op para protocolo async."""
        pass


__all__ = ["SyncSessionManager", "AsyncSessionManager"]
