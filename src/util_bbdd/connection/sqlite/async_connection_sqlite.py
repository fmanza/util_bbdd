"""Conexión async para SQLite basada en aiosqlite."""

from __future__ import annotations

import logging

from typing import Any, Literal, cast

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..connection_params_manager import ConnectionParamsManager


class AsyncSQLiteConnection:
    """Maneja la conexión async a SQLite."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    async def connect(conn_params: dict[str, Any]) -> Any:
        """Establece conexión async a SQLite."""
        try:
            import aiosqlite

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "sqlite",
                conn_params,
            )

            db_path: str = str(sanitized_conn_params.get("database", ":memory:"))
            timeout: float = float(sanitized_conn_params.get("timeout", 5))
            check_same_thread: bool = bool(sanitized_conn_params.get("check_same_thread", False))
            isolation_level_raw: Literal["", "DEFERRED", "IMMEDIATE", "EXCLUSIVE"] = cast(
                Literal["", "DEFERRED", "IMMEDIATE", "EXCLUSIVE"],
                sanitized_conn_params.get("isolation_level", ""),
            )
            isolation_level: Literal["DEFERRED", "IMMEDIATE", "EXCLUSIVE"] | None = (
                None if isolation_level_raw == "" else isolation_level_raw
            )

            AsyncSQLiteConnection.logger.debug(f"🔗 Conectando a SQLite async: {db_path} (timeout={timeout}s)")
            conn: Any = await aiosqlite.connect(
                db_path,
                timeout=timeout,
                check_same_thread=check_same_thread,
                isolation_level=isolation_level,
            )
            await conn.execute("PRAGMA foreign_keys = ON")
            AsyncSQLiteConnection.logger.info(f"✅ Conexión SQLite async establecida: {db_path}")
            return conn
        except ImportError as err:
            AsyncSQLiteConnection.logger.error("❌ Error: módulo aiosqlite no disponible")
            raise DatabaseConnectionError("Módulo aiosqlite no disponible", "sqlite", str(err)) from err
        except Exception as err:
            AsyncSQLiteConnection.logger.error(f"❌ Error conectando a SQLite async: {err}")
            raise DatabaseConnectionError(
                f"Error conectando a SQLite async: {str(err)}",
                "sqlite",
                str(err),
            ) from err
