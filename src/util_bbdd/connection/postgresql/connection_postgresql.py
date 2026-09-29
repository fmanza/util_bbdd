"""Conexión raw al driver PostgreSQL."""

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

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
            ConnectionError: Si hay error en la conexión.
        """
        try:
            import psycopg

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "postgresql",
                conn_params,
            )
            # libpq llama ``dbname`` a la base de datos: psycopg.connect rechaza ``database`` ("invalid connection
            # option"). La config conserva ``database`` porque el pool (conninfo) y asyncpg lo usan con ese nombre;
            # un ``dbname`` explícito tiene prioridad.
            database: Any = sanitized_conn_params.pop("database", None)
            if database is not None:
                sanitized_conn_params.setdefault("dbname", database)
            # libpq espera enteros en las opciones booleanas (``keepalives=1``); ``True`` llegaría como "True".
            sanitized_conn_params = {
                key: int(value) if isinstance(value, bool) else value for key, value in sanitized_conn_params.items()
            }

            PostgreSQLConnection.logger.debug(
                f"🔗 Conectando a PostgreSQL (psycopg3) con parámetros: {list(sanitized_conn_params.keys())}"
            )
            conn = psycopg.connect(**sanitized_conn_params)
            PostgreSQLConnection.logger.info("✅ Conexión PostgreSQL (psycopg3) establecida")
            return conn
        except ImportError as e:
            PostgreSQLConnection.logger.error("❌ Error: módulo psycopg (psycopg3) no disponible")
            raise ConnectionError(
                "Módulo psycopg (psycopg3) no disponible", db_type="postgresql", details=str(e)
            ) from e
        except Exception as e:
            PostgreSQLConnection.logger.error(f"❌ Error conectando a PostgreSQL: {e}")
            raise ConnectionError(
                f"Error conectando a PostgreSQL: {str(e)}", db_type="postgresql", details=str(e)
            ) from e
