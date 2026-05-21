"""Clase base compartida para adapters de metadata que usan conexión directa.

Elimina la repetición del patrón de obtención de conexión con fallback presente
en MySQL, SQLite y SQL Server adapters (sync y async).
"""

from __future__ import annotations

from typing import Any


class BaseConnectionAdapter:
    """Mixin que provee acceso unificado a la conexión del manager.

    Subclases: MysqlSyncAdapter, SqliteSyncAdapter, SqlServerSyncAdapter
    y sus variantes async.
    """

    def __init__(self, manager: Any) -> None:
        self.manager = manager

    def _get_conn(self) -> Any | None:
        """Devuelve la conexión activa del manager, con fallback .db si .connection no existe."""
        return getattr(self.manager, "connection", None) or getattr(self.manager, "db", None)


__all__: list[str] = ["BaseConnectionAdapter"]
