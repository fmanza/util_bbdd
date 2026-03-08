"""Contratos async para conexiones y pools."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AsyncConnectionProtocol(Protocol):
    """Interfaz minima de una conexion async."""

    async def execute(self, query: str, params: Any | None = None) -> Any:
        """Ejecuta una consulta en la conexion."""

    async def fetchone(self) -> Any:
        """Devuelve una fila del resultado actual."""

    async def fetchall(self) -> Any:
        """Devuelve todas las filas del resultado actual."""

    async def close(self) -> None:
        """Cierra la conexion."""


@runtime_checkable
class AsyncPoolProtocol(Protocol):
    """Interfaz minima de un pool async."""

    async def acquire(self) -> Any:
        """Obtiene una conexion del pool."""

    async def release(self, connection: Any) -> None:
        """Devuelve una conexion al pool."""

    async def aclose(self) -> None:
        """Cierra el pool y libera recursos."""
