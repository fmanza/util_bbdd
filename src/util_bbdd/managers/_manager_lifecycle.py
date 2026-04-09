"""Helpers internos de lifecycle para managers sync y async."""

from __future__ import annotations

import logging

from collections.abc import Awaitable, Callable
from typing import Any

from .._foundation.exceptions import DatabaseOperationError
from ..async_utils import maybe_await
from ..connection.close import AsyncCloseMode, run_close_operation_sync


def get_sync_connection(
    *,
    pool_connection: Any,
    connection: Any,
    db_type: str,
    logger: logging.Logger,
) -> Any:
    """Obtiene una conexión sync desde pool o conexión directa."""
    if pool_connection:
        try:
            acquired_connection = pool_connection.get_connection()
        except TimeoutError as error:
            raise DatabaseOperationError(
                f"Timeout obteniendo conexión del pool para {db_type}: {error}",
                operation="CONNECT",
                db_type=db_type,
            ) from error
        except RuntimeError as error:
            raise DatabaseOperationError(
                f"Pool de conexiones no disponible para {db_type}: {error}",
                operation="CONNECT",
                db_type=db_type,
            ) from error
        except Exception as error:
            raise DatabaseOperationError(
                f"Error obteniendo conexión del pool para {db_type}: {error}",
                operation="CONNECT",
                db_type=db_type,
            ) from error

        if acquired_connection is None:
            raise DatabaseOperationError(
                f"Pool de conexiones devolvió conexión nula para {db_type}",
                operation="CONNECT",
                db_type=db_type,
            )

        logger.debug("📦 Conexión obtenida del pool")
        return acquired_connection

    if connection is None:
        raise DatabaseOperationError("No hay conexión disponible", db_type=db_type)

    return connection


def release_sync_connection(*, pool_connection: Any, connection: Any | None, logger: logging.Logger) -> None:
    """Devuelve una conexión sync al pool o la cierra si es directa."""
    if connection is None:
        return

    if pool_connection:
        pool_connection.close_connection(connection)
        logger.debug("📦 Conexión devuelta al pool")
        return

    connection.close()
    logger.debug("🔌 Conexión cerrada")


def close_sync_resources(
    *,
    pool_connection: Any,
    cursor: Any,
    connection: Any,
    logger: logging.Logger,
    db_type: str,
    timeout_seconds: float | None,
    force: bool,
) -> None:
    """Cierra recursos sync y agrega errores si aparecen varios fallos."""
    close_errors: list[Exception] = []

    if pool_connection is not None:
        try:
            pool_connection.close(timeout_seconds=timeout_seconds, force=force)
            logger.info("🔗 Pool liberado y cerrado")
        except Exception as error:
            close_errors.append(error)

    if cursor is not None:
        try:
            run_close_operation_sync(
                action=lambda: cursor.close(),
                timeout_seconds=timeout_seconds,
                action_name=f"cierre cursor {db_type}",
                db_type=db_type,
            )
            logger.debug(f"✅ Cursor cerrado para {db_type}")
        except Exception as error:
            close_errors.append(error)

    if connection is not None:
        try:
            run_close_operation_sync(
                action=lambda: connection.close(),
                timeout_seconds=timeout_seconds,
                action_name=f"cierre conexión {db_type}",
                db_type=db_type,
            )
            logger.info(f"✅ Conexión cerrada para {db_type}")
        except Exception as error:
            close_errors.append(error)

    if close_errors:
        error_details = " | ".join(str(error) for error in close_errors)
        raise DatabaseOperationError(
            message=f"Errores cerrando recursos de base de datos: {error_details}",
            operation="CLOSE",
            db_type=db_type,
        ) from close_errors[0]


async def init_async_resources(
    *,
    use_pool: bool,
    create_pool: Callable[[], Awaitable[Any]],
    create_connection: Callable[[], Awaitable[Any]],
) -> tuple[bool, Any, Any]:
    """Inicializa recursos async resolviendo fallback a conexión directa."""
    resolved_use_pool = use_pool
    pool_connection: Any = None
    connection: Any = None

    if resolved_use_pool:
        try:
            pool_connection = await create_pool()
        except NotImplementedError:
            resolved_use_pool = False

    if not resolved_use_pool:
        connection = await create_connection()

    return resolved_use_pool, pool_connection, connection


async def get_async_connection(
    *,
    initialized: bool,
    ensure_initialized: Callable[[], Awaitable[Any]],
    pool_connection: Any,
    connection: Any,
) -> Any:
    """Obtiene una conexión async inicializando el manager si es necesario."""
    if not initialized:
        await ensure_initialized()

    if pool_connection is not None:
        return await maybe_await(pool_connection.acquire())

    return connection


async def release_async_connection(*, pool_connection: Any, connection: Any) -> None:
    """Libera conexión async al pool o no hace nada si es directa."""
    if pool_connection is None:
        return
    await maybe_await(pool_connection.release(connection))


async def close_async_resources(*, pool_connection: Any, connection: Any, close_mode: AsyncCloseMode) -> None:
    """Cierra recursos async compartidos."""
    if pool_connection is not None:
        await maybe_await(pool_connection.close(mode=close_mode))
    if connection is not None and hasattr(connection, "close"):
        await maybe_await(connection.close())
