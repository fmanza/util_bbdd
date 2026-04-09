"""Gestor de lifecycle para operaciones sync."""

from __future__ import annotations

import logging

from typing import Any

from .._foundation.exceptions import DatabaseConnectionError, DatabaseValidationError
from .._foundation.validators_core import DatabaseTypeValidator
from ..connection.factory import ConnectionFactory
from ..connection.params import ConnectionParamsManager
from ..connection.protocols import ConnectionPoolProtocol
from ._manager_lifecycle import close_sync_resources


class SyncLifecycleManager:
    """Gestor de ciclo de vida sync para conexiones y recursos."""

    def __init__(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        logger: logging.Logger,
        validators: DatabaseTypeValidator,
    ) -> None:
        """
        Inicializa el gestor de lifecycle sync.

        Args:
            db_type: Tipo de base de datos.
            conn_params: Parámetros de conexión.
            logger: Logger para mensajes.
            validators: Validador de tipos de base de datos.
        """
        self.db_type = db_type
        self.conn_params = conn_params
        self.logger = logger
        self.validators = validators
        self.sql_server_driver: str = "pymssql"

    def validate_connection_params(self) -> None:
        """
        Valida y normaliza parámetros de conexión.

        Raises:
            DatabaseValidationError: Si la validación falla.
        """
        try:
            from .._foundation.driver_validator import DriverValidator

            self.validators.validate_db_type(self.db_type)

            if self.db_type == "sqlserver":
                self.sql_server_driver = DriverValidator.check_driver_availability(self.db_type, self.conn_params)
            else:
                DriverValidator.check_driver_availability(self.db_type, self.conn_params)

            self.conn_params = ConnectionParamsManager.prepare_and_validate(
                self.db_type,
                self.conn_params,
                self.validators,
            )
            self.logger.debug(f"✅ Parámetros validados para {self.db_type}")
        except DatabaseValidationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error validando parámetros: {e}")
            raise DatabaseValidationError(str(e), self.db_type) from e

    def initialize_pool(self, pool_factory_func: Any) -> ConnectionPoolProtocol | None:
        """
        Inicializa pool de conexiones.

        Args:
            pool_factory_func: Función factory para crear pool.

        Returns:
            Pool de conexiones o None si no soportado.

        Raises:
            Exception: Si la inicialización del pool falla.
        """
        if self.db_type in ["hsqldb"]:
            self.logger.warning(f"⚠️ Pool no soportado para {self.db_type}. Usando conexión única.")
            return None

        try:
            pool: Any = pool_factory_func(self.db_type, self.conn_params)

            test_conn = pool.get_connection()
            pool.close_connection(test_conn)
            self.logger.info(f"🔗 Pool habilitado para {self.db_type}")
            return pool  # type: ignore
        except ValueError as e:
            self.logger.warning(f"⚠️ Pool no disponible: {e}")
            return None

    def create_connection(self) -> Any:
        """
        Crea conexión directa a la base de datos.

        Returns:
            Conexión a la base de datos.

        Raises:
            DatabaseConnectionError: Si la conexión falla.
        """
        try:
            self.logger.info(f"🔗 Estableciendo conexión a {self.db_type}")

            valid_params = ConnectionParamsManager.sanitize_for_connection(
                self.db_type,
                self.conn_params,
                driver=self.sql_server_driver if self.db_type == "sqlserver" else None,
            )

            connection = ConnectionFactory.create_connection(
                self.db_type,
                valid_params,
                db_validator=self.validators,
                sql_server_driver=self.sql_server_driver,
            )
            self.logger.info("✅ Conexión establecida")
            return connection
        except DatabaseConnectionError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error en conexión: {e}")
            raise DatabaseConnectionError(f"Error conectando a {self.db_type}: {str(e)}", self.db_type) from e

    def close_resources(
        self,
        pool_connection: ConnectionPoolProtocol | None,
        cursor: Any,
        connection: Any,
        timeout_seconds: float | None = None,
        force: bool = False,
    ) -> None:
        """
        Cierra todos los recursos sync.

        Args:
            pool_connection: Pool a cerrar (opcional).
            cursor: Cursor a cerrar (opcional).
            connection: Conexión a cerrar (opcional).
            timeout_seconds: Timeout para cierre.
            force: Fuerza cierre inmediato.
        """
        close_sync_resources(
            pool_connection=pool_connection,
            cursor=cursor,
            connection=connection,
            logger=self.logger,
            db_type=self.db_type,
            timeout_seconds=timeout_seconds,
            force=force,
        )
        self.logger.info("✅ Recursos sync cerrados")

    def supports_pool(self) -> bool:
        """Indica si el motor soporta pool de conexiones."""
        return self.db_type not in ["hsqldb"]


__all__ = ["SyncLifecycleManager"]
