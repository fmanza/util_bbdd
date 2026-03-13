"""Conexión raw al driver PostgreSQL."""

import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..params import ConnectionParamsManager


class PostgreSQLConnection:
    """Maneja la conexión raw a PostgreSQL."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def connect(conn_params: dict[str, Any]) -> Any:
        """
        Establece conexión raw a PostgreSQL usando psycopg3.

        Args:
            conn_params: Parámetros de conexión validados.

        Returns:
            Conexión a PostgreSQL.

        Raises:
            DatabaseConnectionError: Si hay error en la conexión.
        """
        try:
            import psycopg

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "postgresql",
                conn_params,
            )

            PostgreSQLConnection.logger.debug(
                f"🔗 Conectando a PostgreSQL (psycopg3) con parámetros: {list(sanitized_conn_params.keys())}"
            )
            conn = psycopg.connect(**sanitized_conn_params)
            PostgreSQLConnection.logger.info("✅ Conexión PostgreSQL (psycopg3) establecida")
            return conn
        except ImportError as e:
            PostgreSQLConnection.logger.error("❌ Error: módulo psycopg (psycopg3) no disponible")
            raise DatabaseConnectionError("Módulo psycopg (psycopg3) no disponible", "postgresql", str(e)) from e
        except Exception as e:
            PostgreSQLConnection.logger.error(f"❌ Error conectando a PostgreSQL: {e}")
            raise DatabaseConnectionError(f"Error conectando a PostgreSQL: {str(e)}", "postgresql", str(e)) from e
