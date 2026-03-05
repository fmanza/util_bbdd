"""Contrato común para pools de conexión."""

from __future__ import annotations

from typing import Any, Protocol


class ConnectionPoolProtocol(Protocol):
    """Interfaz mínima que deben cumplir todos los pools."""

    def get_connection(self) -> Any:
        """Obtiene una conexión disponible."""

    def close_connection(self, connection: Any) -> None:
        """Devuelve/cierra una conexión según implementación."""

    def close(self) -> None:
        """Cierra el pool y libera recursos."""
