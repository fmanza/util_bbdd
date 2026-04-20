"""Helpers internos de lifecycle para managers sync y async."""

from __future__ import annotations

import logging

from collections.abc import Awaitable, Callable
from typing import Any

from .._core.exceptions import DatabaseOperationError
from ..async_utils import maybe_await
from ..connection.close import AsyncCloseMode, run_close_operation_sync


class SyncConnectionLifecycleManager:
    """Gestiona el ciclo de vida de conexiones sincrónicas (patrón: Manager).

    Centraliza la lógica de adquisición, liberación y cierre de recursos,
    proporcionando logging consistente y manejo uniforme de errores.
    """

    def __init__(self, db_type: str, logger: logging.Logger):
        """Inicializa el manager de ciclo de vida.

        Args:
            db_type: Tipo de base de datos (oracle, postgresql, etc.)
            logger: Logger para eventos de ciclo de vida
        """
        self.db_type: str = db_type
        self.logger: logging.Logger = logger

    def get_connection(
        self,
        *,
        pool_connection: Any,
        connection: Any,
    ) -> Any:
        """Obtiene una conexión sync desde pool o conexión directa.

        Args:
            pool_connection: Pool de conexiones (si disponible)
            connection: Conexión directa (si no hay pool)

        Returns:
            Any: Conexión adquirida

        Raises:
            DatabaseOperationError: Si no se puede adquirir conexión
        """
        if pool_connection:
            try:
                acquired_connection = pool_connection.get_connection()
            except TimeoutError as error:
                raise DatabaseOperationError(
                    f"Timeout obteniendo conexión del pool para {self.db_type}: {error}",
                    operation="CONNECT",
                    db_type=self.db_type,
                ) from error
            except RuntimeError as error:
                raise DatabaseOperationError(
                    f"Pool de conexiones no disponible para {self.db_type}: {error}",
                    operation="CONNECT",
                    db_type=self.db_type,
                ) from error
            except Exception as error:
                raise DatabaseOperationError(
                    f"Error obteniendo conexión del pool para {self.db_type}: {error}",
                    operation="CONNECT",
                    db_type=self.db_type,
                ) from error

            if acquired_connection is None:
                raise DatabaseOperationError(
                    f"Pool de conexiones devolvió conexión nula para {self.db_type}",
                    operation="CONNECT",
                    db_type=self.db_type,
                )

            self.logger.debug(f"[{self.db_type}] 📦 Conexión obtenida del pool")
            return acquired_connection

        if connection is None:
            raise DatabaseOperationError("No hay conexión disponible", db_type=self.db_type)

        return connection

    def release_connection(self, *, pool_connection: Any, connection: Any | None) -> None:
        """Devuelve una conexión sync al pool o la cierra si es directa.

        Args:
            pool_connection: Pool de conexiones (si disponible)
            connection: Conexión a liberar (opcional)
        """
        if connection is None:
            return

        if pool_connection:
            pool_connection.close_connection(connection)
            self.logger.debug(f"[{self.db_type}] 📦 Conexión devuelta al pool")
            return

        connection.close()
        self.logger.debug(f"[{self.db_type}] 🔌 Conexión cerrada")

    def close_resources(
        self,
        *,
        pool_connection: Any,
        cursor: Any,
        connection: Any,
        timeout_seconds: float | None,
        force: bool,
    ) -> None:
        """Cierra recursos sync y agrega errores si aparecen varios fallos.

        Args:
            pool_connection: Pool a cerrar (si disponible)
            cursor: Cursor a cerrar (si disponible)
            connection: Conexión a cerrar (si disponible)
            timeout_seconds: Timeout para cierre de conexión
            force: Forzar cierre sin graceful shutdown

        Raises:
            DatabaseOperationError: Si hay errores al cerrar recursos
        """
        close_errors: list[Exception] = []

        if pool_connection is not None:
            try:
                pool_connection.close(timeout_seconds=timeout_seconds, force=force)
                self.logger.info(f"[{self.db_type}] 🔗 Pool liberado y cerrado")
            except Exception as error:
                close_errors.append(error)
                self.logger.error(f"[{self.db_type}] Error cerrando pool: {error}", exc_info=True)

        if cursor is not None:
            try:
                run_close_operation_sync(
                    action=lambda: cursor.close(),
                    timeout_seconds=timeout_seconds,
                    action_name=f"cierre cursor {self.db_type}",
                    db_type=self.db_type,
                )
                self.logger.debug(f"[{self.db_type}] ✅ Cursor cerrado")
            except Exception as error:
                close_errors.append(error)
                self.logger.error(f"[{self.db_type}] Error cerrando cursor: {error}", exc_info=True)

        if connection is not None:
            try:
                run_close_operation_sync(
                    action=lambda: connection.close(),
                    timeout_seconds=timeout_seconds,
                    action_name=f"cierre conexión {self.db_type}",
                    db_type=self.db_type,
                )
                self.logger.info(f"[{self.db_type}] ✅ Conexión cerrada")
            except Exception as error:
                close_errors.append(error)
                self.logger.error(f"[{self.db_type}] Error cerrando conexión: {error}", exc_info=True)

        if close_errors:
            error_details = " | ".join(str(error) for error in close_errors)
            raise DatabaseOperationError(
                message=f"Errores cerrando recursos de base de datos: {error_details}",
                operation="CLOSE",
                db_type=self.db_type,
            ) from close_errors[0]


# Compatibilidad: Wrappers deprecated que delegan a SyncConnectionLifecycleManager
def get_sync_connection(
    *,
    pool_connection: Any,
    connection: Any,
    db_type: str,
    logger: logging.Logger,
) -> Any:
    """Obtiene una conexión sync desde pool o conexión directa (deprecated).

    Use: SyncConnectionLifecycleManager.get_connection() en su lugar.
    """
    manager = SyncConnectionLifecycleManager(db_type, logger)
    return manager.get_connection(pool_connection=pool_connection, connection=connection)


def release_sync_connection(*, pool_connection: Any, connection: Any | None, logger: logging.Logger) -> None:
    """Devuelve una conexión sync al pool o la cierra si es directa (deprecated).

    Use: SyncConnectionLifecycleManager.release_connection() en su lugar.
    """
    # Extraer db_type del pool si es posible, o usar genérico
    db_type = getattr(pool_connection, "db_type", "unknown") if pool_connection else "unknown"
    manager = SyncConnectionLifecycleManager(db_type, logger)
    manager.release_connection(pool_connection=pool_connection, connection=connection)


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
    """Cierra recursos sync y agrega errores si aparecen varios fallos (deprecated).

    Use: SyncConnectionLifecycleManager.close_resources() en su lugar.
    """
    manager = SyncConnectionLifecycleManager(db_type, logger)
    manager.close_resources(
        pool_connection=pool_connection,
        cursor=cursor,
        connection=connection,
        timeout_seconds=timeout_seconds,
        force=force,
    )


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
