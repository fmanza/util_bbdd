"""Protocolos (interfaces) para conexiones, pools y close utilities.

Define contratos que deben cumplir todas las implementaciones
de conexiones y pools de conexión.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

__all__ = [
    "ConnectionPoolProtocol",
    "AsyncConnectionProtocol",
    "AsyncPoolProtocol",
    "AsyncCloseMode",
]

# Type alias para modo de cierre async
AsyncCloseMode = Literal["immediate", "graceful"]


# ============================================================================
# Protocolo: Pool de Conexión Sincrónico
# ============================================================================


@runtime_checkable
class ConnectionPoolProtocol(Protocol):
    """Interfaz mínima que deben cumplir todos los pools sincrónico.

    Define el contrato para acceso y cierre de conexiones.
    """

    def get_connection(self) -> Any:
        """Obtiene una conexión disponible del pool.

        Returns:
            Conexión del driver específico

        Raises:
            PoolTimeoutError: Si no hay conexiones disponibles
        """
        ...

    def close_connection(self, connection: Any) -> None:
        """Devuelve o cierra una conexión según implementación.

        Args:
            connection: Conexión a devolver/cerrar
        """
        ...

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        """Cierra el pool con política explícita de timeout/forzado.

        Args:
            timeout_seconds: Tiempo máximo para cierre graceful (None = sin límite)
            force: Si True, cierra inmediatamente sin esperar
        """
        ...


# ============================================================================
# Protocolos: Conexión y Pool Asincrónico
# ============================================================================


@runtime_checkable
class AsyncConnectionProtocol(Protocol):
    """Interfaz mínima de una conexión asincrónica.

    Define método básicos para ejecutar queries en una conexión async.
    """

    async def execute(self, query: str, params: Any | None = None) -> Any:
        """Ejecuta una consulta en la conexión.

        Args:
            query: SQL a ejecutar
            params: Parámetros de la query (opcional)

        Returns:
            Resultado según driver (cursor, resultado directo, etc.)
        """
        ...

    async def fetchone(self) -> Any:
        """Devuelve una fila del resultado actual.

        Returns:
            Una fila como tupla/dict o None si no hay más filas
        """
        ...

    async def fetchall(self) -> Any:
        """Devuelve todas las filas del resultado actual.

        Returns:
            Lista de filas como tuplas/dicts
        """
        ...

    async def close(self) -> None:
        """Cierra la conexión de forma async."""
        ...


@runtime_checkable
class AsyncPoolProtocol(Protocol):
    """Interfaz mínima de un pool asincrónico.

    Define métodos para adquirir, devolver y cerrar conexiones
    en contexto async.
    """

    async def acquire(self) -> Any:
        """Obtiene una conexión disponible del pool.

        Returns:
            Conexión del driver específico

        Raises:
            PoolTimeoutError: Si no hay conexiones disponibles
        """
        ...

    async def release(self, connection: Any) -> None:
        """Devuelve una conexión al pool.

        Args:
            connection: Conexión a devolver
        """
        ...

    async def close(self, mode: AsyncCloseMode = "graceful") -> None:
        """Cierra el pool en modo inmediato o graceful.

        Args:
            mode: Tipo de cierre ('immediate' o 'graceful')
                 - immediate: Cierra inmediatamente sin esperar
                 - graceful: Espera a que terminen conexiones activas
        """
        ...
