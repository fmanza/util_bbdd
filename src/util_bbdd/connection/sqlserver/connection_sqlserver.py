"""Conexión raw al driver SQL Server."""

import logging
from typing import Any

from pyodbc import Connection

from ..connection_params_manager import ConnectionParamsManager
from util_bbdd.database_exceptions import DatabaseConnectionError


class SQLServerConnection:
    """Maneja la conexión raw a SQL Server."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def connect(conn_params: dict[str, Any], driver: str = "pymssql") -> Any:
        """
        Establece conexión raw a SQL Server usando pymssql o pyodbc.

        Args:
            conn_params: Parámetros de conexión validados.
            driver: Driver a usar ('pymssql' o 'pyodbc'). Por defecto 'pymssql'.

        Returns:
            Conexión a SQL Server.

        Raises:
            DatabaseConnectionError: Si hay error en la conexión.
        """
        try:
            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "sqlserver",
                conn_params,
                driver=driver,
            )

            if driver == "pymssql":
                return SQLServerConnection._connect_pymssql(sanitized_conn_params)
            elif driver == "pyodbc":
                return SQLServerConnection._connect_pyodbc(sanitized_conn_params)
            else:
                raise DatabaseConnectionError(f"Driver SQL Server no reconocido: {driver}", "sqlserver")
        except DatabaseConnectionError:
            raise
        except Exception as e:
            SQLServerConnection.logger.error(f"❌ Error conectando a SQL Server: {e}")
            raise DatabaseConnectionError(f"Error conectando a SQL Server: {str(e)}", "sqlserver", str(e)) from e

    @staticmethod
    def _connect_pymssql(conn_params: dict[str, Any]) -> Any:
        """
        Crea conexión raw a SQL Server usando pymssql.

        Args:
            conn_params: Parámetros filtrados de conexión.

        Returns:
            Conexión a SQL Server con pymssql.

        Raises:
            DatabaseConnectionError: Si hay error en la conexión.
        """
        try:
            import pymssql

            params: dict[str, Any] = dict(conn_params)
            params.pop("sql_server_driver", None)
            params.pop("driver_name", None)
            params.pop("login_timeout", None)
            params.pop("encryption", None)
            params.pop("trust_cert", None)
            params.pop("use_mars", None)

            SQLServerConnection.logger.debug(
                f"🔗 Conectando a SQL Server (pymssql) con parámetros: {list(params.keys())}"
            )
            conn = pymssql.connect(**params)
            SQLServerConnection.logger.info("✅ Conexión SQL Server (pymssql) establecida")
            return conn
        except ImportError as e:
            SQLServerConnection.logger.error("❌ Error: módulo pymssql no disponible")
            raise DatabaseConnectionError("Módulo pymssql no disponible", "sqlserver", str(e)) from e
        except Exception as e:
            SQLServerConnection.logger.error(f"❌ Error conectando a SQL Server (pymssql): {e}")
            raise DatabaseConnectionError(f"Error conectando a SQL Server: {str(e)}", "sqlserver", str(e)) from e

    @staticmethod
    def _connect_pyodbc(conn_params: dict[str, Any]) -> Any:
        """
        Crea conexión raw a SQL Server usando pyodbc.

        Args:
            conn_params: Parámetros filtrados de conexión.

        Returns:
            Conexión a SQL Server con pyodbc.

        Raises:
            DatabaseConnectionError: Si hay error en la conexión.
        """
        try:
            import pyodbc

            host = conn_params.get("host", "localhost")
            user = conn_params.get("user", "sa")
            password = conn_params.get("password", "")
            database = conn_params.get("database", "master")
            port = conn_params.get("port", 1433)
            driver_name = conn_params.get("driver_name", "ODBC Driver 17 for SQL Server")
            encryption = conn_params.get("encryption", "optional")
            trust_cert = conn_params.get("trust_cert", False)

            conn_str: str = (
                f"Driver={{{driver_name}}};"
                f"Server={host},{port};"
                f"Database={database};"
                f"UID={user};"
                f"PWD={password};"
                f"Encrypt={encryption.lower()};"
                f"TrustServerCertificate={'yes' if trust_cert else 'no'};"
            )

            timeout = conn_params.get("login_timeout", 20)

            SQLServerConnection.logger.debug(f"🔗 Conectando a SQL Server (pyodbc) a {host}:{port}/{database}")
            conn: Connection = pyodbc.connect(conn_str, timeout=timeout)
            SQLServerConnection.logger.info("✅ Conexión SQL Server (pyodbc) establecida")
            return conn
        except ImportError as e:
            SQLServerConnection.logger.error("❌ Error: módulo pyodbc no disponible")
            raise DatabaseConnectionError("Módulo pyodbc no disponible", "sqlserver", str(e)) from e
        except Exception as e:
            SQLServerConnection.logger.error(f"❌ Error conectando a SQL Server (pyodbc): {e}")
            raise DatabaseConnectionError(f"Error conectando a SQL Server: {str(e)}", "sqlserver", str(e)) from e

