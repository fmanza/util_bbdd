"""Conexión raw al driver HSQLDB."""

import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError, DatabaseValidationError

from ..params import ConnectionParamsManager


class HSQLDBConnection:
    """Maneja la conexión raw a HSQLDB."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def connect(conn_params: dict[str, Any]) -> Any:
        """
        Establece conexión raw a HSQLDB.

        Args:
            conn_params: Parámetros de conexión validados.

        Returns:
            Conexión a HSQLDB.

        Raises:
            DatabaseConnectionError: Si hay error en la conexión.
            DatabaseValidationError: Si faltan parámetros requeridos.
        """
        try:
            import jaydebeapi

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "hsqldb",
                conn_params,
            )

            # HSQLDB requiere parámetros especiales JDBC
            jdbc_driver = sanitized_conn_params.get("jdbc_driver", "org.hsqldb.jdbcDriver")
            jdbc_url = sanitized_conn_params.get("jdbc_url", None)
            jdbc_jar = sanitized_conn_params.get("jdbc_jar", None)

            if not jdbc_url:
                HSQLDBConnection.logger.error("❌ Se requiere jdbc_url para HSQLDB")
                raise DatabaseValidationError("Se requiere jdbc_url para HSQLDB", "hsqldb")
            if not jdbc_jar:
                HSQLDBConnection.logger.error("❌ Se requiere jdbc_jar para HSQLDB")
                raise DatabaseValidationError("Se requiere jdbc_jar para HSQLDB", "hsqldb")

            user = sanitized_conn_params.get("user", "")
            password = sanitized_conn_params.get("password", "")

            HSQLDBConnection.logger.debug(f"🔗 Conectando a HSQLDB con JDBC: {jdbc_url}")
            conn = jaydebeapi.connect(jdbc_driver, jdbc_url, user, password, jdbc_jar)
            HSQLDBConnection.logger.info("✅ Conexión HSQLDB establecida")
            return conn
        except DatabaseValidationError:
            raise
        except ImportError as e:
            HSQLDBConnection.logger.error("❌ Error: módulo jaydebeapi no disponible")
            raise DatabaseConnectionError("Módulo jaydebeapi no disponible", "hsqldb", str(e)) from e
        except Exception as e:
            HSQLDBConnection.logger.error(f"❌ Error conectando a HSQLDB: {e}")
            raise DatabaseConnectionError(f"Error conectando a HSQLDB: {str(e)}", "hsqldb", str(e)) from e
