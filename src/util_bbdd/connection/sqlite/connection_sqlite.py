"""Conexión raw al driver SQLite."""

import logging

from sqlite3 import Connection
from typing import Any, Literal, cast

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager


class SQLiteConnection:
    """Maneja la conexión raw a SQLite."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def connect(conn_params: dict[str, Any]) -> Any:
        """
        Establece conexión raw a SQLite.

        Args:
            conn_params: Parámetros de conexión validados (requiere 'database').
                - database: Ruta al archivo SQLite o ':memory:' para BD en memoria
                - timeout: Timeout en segundos (opcional, default 5)
                - check_same_thread: Validar mismo thread (opcional, default False para pool)
                - isolation_level: Nivel de aislamiento (opcional)

        Returns:
            Conexión a SQLite.

        Raises:
            ConnectionError: Si hay error en la conexión.

        Example:
            ```python
            # Conexión a archivo
            conn_params = {
                "database": "/path/to/database.db",
                "timeout": 10
            }

            # Conexión en memoria
            conn_params = {"database": ":memory:"}

            conn = SQLiteConnection.connect(conn_params)
            ```
        """
        try:
            import sqlite3

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "sqlite",
                conn_params,
            )

            db_path = sanitized_conn_params.get("database", ":memory:")
            timeout = sanitized_conn_params.get("timeout", 5)
            check_same_thread = sanitized_conn_params.get("check_same_thread", False)
            isolation_level_raw: Literal["", "DEFERRED", "IMMEDIATE", "EXCLUSIVE"] = cast(
                Literal["", "DEFERRED", "IMMEDIATE", "EXCLUSIVE"],
                sanitized_conn_params.get("isolation_level", ""),
            )
            isolation_level: Literal["DEFERRED", "IMMEDIATE", "EXCLUSIVE"] | None = (
                None if isolation_level_raw == "" else isolation_level_raw
            )

            SQLiteConnection.logger.debug(f"🔗 Conectando a SQLite: {db_path} (timeout={timeout}s)")

            conn: Connection = sqlite3.connect(
                db_path,
                timeout=timeout,
                check_same_thread=check_same_thread,
                isolation_level=isolation_level,
            )

            # Habilitar foreign keys por defecto
            conn.execute("PRAGMA foreign_keys = ON")

            SQLiteConnection.logger.info(f"✅ Conexión SQLite establecida: {db_path}")
            return conn
        except ImportError as e:
            SQLiteConnection.logger.error("❌ Error: módulo sqlite3 no disponible")
            raise ConnectionError("Módulo sqlite3 no disponible", db_type="sqlite", details=str(e)) from e
        except Exception as e:
            SQLiteConnection.logger.error(f"❌ Error conectando a SQLite: {e}")
            raise ConnectionError(f"Error conectando a SQLite: {str(e)}", db_type="sqlite", details=str(e)) from e
