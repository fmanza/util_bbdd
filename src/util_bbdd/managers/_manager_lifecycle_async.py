"""Gestor de lifecycle para operaciones async."""

from __future__ import annotations

import logging

from collections.abc import Awaitable, Callable
from typing import Any

from .._drivers import DatabaseTypeValidator


class AsyncLifecycleManager:
    """Gestor de ciclo de vida async para conexiones y recursos."""

    def __init__(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        logger: logging.Logger,
        validators: DatabaseTypeValidator | None = None,
    ) -> None:
        """
        Inicializa el gestor de lifecycle async.

        Args:
            db_type: Tipo de base de datos.
            conn_params: Parámetros de conexión.
            logger: Logger para mensajes.
            validators: Validador de tipos de base de datos (opcional).
        """
        self.db_type = db_type.lower().strip()
        self.conn_params = conn_params
        self.logger = logger
        self.validators = validators

    async def initialize_pool(self, pool_factory_func: Callable[..., Awaitable[Any]]) -> Any | None:
        """
        Inicializa pool de conexiones async.

        Args:
            pool_factory_func: Función factory async para crear pool.

        Returns:
            Pool de conexiones o None si no soportado.
        """
        if self.db_type in ["hsqldb"]:
            self.logger.warning(f"⚠️ Pool no soportado para {self.db_type}")
            return None

        try:
            pool = await pool_factory_func(self.db_type, self.conn_params)
            self.logger.info(f"🔗 Pool async habilitado para {self.db_type}")
            return pool
        except Exception as e:
            self.logger.warning(f"⚠️ Pool async no disponible: {e}")
            return None

    async def create_connection(self, connection_factory_func: Callable[..., Awaitable[Any]]) -> Any:
        """
        Crea conexión async a la base de datos.

        Args:
            connection_factory_func: Función factory async para conexión.

        Returns:
            Conexión async a la base de datos.
        """
        try:
            self.logger.info(f"🔗 Estableciendo conexión async a {self.db_type}")
            connection = await connection_factory_func(self.db_type, self.conn_params)
            self.logger.info("✅ Conexión async establecida")
            return connection
        except Exception as e:
            self.logger.error(f"❌ Error en conexión async: {e}")
            raise

    async def close_connection(self, connection: Any) -> None:
        """
        Cierra conexión async.

        Args:
            connection: Conexión async a cerrar.
        """
        if connection is None:
            return

        try:
            if hasattr(connection, "aclose"):
                await connection.aclose()
            elif hasattr(connection, "close"):
                if callable(connection.close):
                    result = connection.close()
                    if hasattr(result, "__await__"):
                        await result
            self.logger.debug("🔌 Conexión async cerrada")
        except Exception as e:
            self.logger.error(f"❌ Error cerrando conexión async: {e}")

    async def close_pool(self, pool: Any) -> None:
        """
        Cierra pool async.

        Args:
            pool: Pool async a cerrar.
        """
        if pool is None:
            return

        try:
            if hasattr(pool, "close"):
                result = pool.close()
                if hasattr(result, "__await__"):
                    await result
            self.logger.info("🔗 Pool async cerrado")
        except Exception as e:
            self.logger.error(f"❌ Error cerrando pool async: {e}")

    def supports_pool(self) -> bool:
        """Indica si el motor soporta pool de conexiones."""
        return self.db_type not in ["hsqldb"]


__all__ = ["AsyncLifecycleManager"]
