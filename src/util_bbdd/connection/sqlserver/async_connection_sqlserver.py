"""Conexión async para SQL Server basada en aioodbc."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager
from .connection_sqlserver import SQLServerConnection


class AsyncSQLServerConnection:
    """Maneja la conexión async a SQL Server."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def _escape_odbc_value(value: Any) -> str:
        """Envuelve un valor en ``{}`` (doblando ``}`` internas) para un connection string ODBC.

        Sin este quoting, un valor con ``;``, ``{`` o ``}`` puede inyectar atributos adicionales
        en la cadena de conexión (p. ej. ``TrustServerCertificate=yes``) — ver AUDIT_CODE CNX-02,
        2026-09-22. Usado también por ``AsyncPoolConnection`` (sqlserver), que reutiliza
        ``_build_dsn``.
        """
        return "{" + str(value).replace("}", "}}") + "}"

    @staticmethod
    def _build_dsn(conn_params: dict[str, Any]) -> str:
        host: str = str(conn_params.get("host", "localhost"))
        user: str = str(conn_params.get("user", "sa"))
        password: str = str(conn_params.get("password", ""))
        database: str = str(conn_params.get("database", "master"))
        port: int = int(conn_params.get("port", 1433))
        driver_name: str = str(conn_params.get("driver_name", "ODBC Driver 17 for SQL Server"))
        encryption: str = SQLServerConnection.odbc_encrypt(conn_params.get("encryption", "optional"))
        trust_cert: bool = bool(conn_params.get("trust_cert", False))
        use_mars: bool = bool(conn_params.get("use_mars", True))

        esc = AsyncSQLServerConnection._escape_odbc_value
        return (
            f"Driver={esc(driver_name)};"
            f"Server={esc(f'{host},{port}')};"  # host,puerto dentro de las llaves: fuera, el Driver Manager lo rechaza
            f"Database={esc(database)};"
            f"UID={esc(user)};"
            f"PWD={esc(password)};"
            f"Encrypt={encryption};"
            f"TrustServerCertificate={'yes' if trust_cert else 'no'};"
            f"MARS_Connection={'yes' if use_mars else 'no'};"
        )

    @staticmethod
    async def connect(conn_params: dict[str, Any]) -> Any:
        """Establece conexión async a SQL Server."""
        try:
            import aioodbc

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "sqlserver",
                conn_params,
                driver="pyodbc",
            )
            dsn: str = AsyncSQLServerConnection._build_dsn(sanitized_conn_params)
            login_timeout: int = int(sanitized_conn_params.get("login_timeout", 20))

            AsyncSQLServerConnection.logger.debug("🔗 Conectando a SQL Server async (aioodbc)")
            conn: Any = await aioodbc.connect(dsn=dsn, timeout=login_timeout)
            AsyncSQLServerConnection.logger.info("✅ Conexión SQL Server async establecida")
            return conn
        except ImportError as err:
            AsyncSQLServerConnection.logger.error("❌ Error: módulo aioodbc no disponible")
            raise ConnectionError("Módulo aioodbc no disponible", db_type="sqlserver", details=str(err)) from err
        except Exception as err:
            AsyncSQLServerConnection.logger.error(f"❌ Error conectando a SQL Server async: {err}")
            raise ConnectionError(
                f"Error conectando a SQL Server async: {str(err)}",
                db_type="sqlserver",
                details=str(err),
            ) from err
