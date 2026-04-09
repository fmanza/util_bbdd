"""Adaptadores SQLite para introspección de metadatos.

Proporciona adaptadores sync y async compatibles con duck-typing SourceAdapter
y RoutineAdapter protocols.

Ejemplo de uso:
    from util_bbdd.metadata.sqlite import SqliteSyncAdapter, SqliteAsyncAdapter

    # O dejar que el registry auto-resuelva:
    from util_bbdd.metadata.adapters import get_global_adapter_registry
    registry = get_global_adapter_registry()
    adapter_class = registry.get_source_adapter_sync("sqlite")

El registro global se popula automáticamente al importar este módulo.
"""

from __future__ import annotations

from .async_adapter import SqliteAsyncAdapter
from .common import (
    escape_sqlite_string,
    is_system_schema_sqlite,
    normalize_sqlite_type,
    quote_sqlite_identifier,
    sqlite_type_mapping,
)
from .sync_adapter import SqliteSyncAdapter

__all__: list[str] = [
    # Adapters
    "SqliteAsyncAdapter",
    "SqliteSyncAdapter",
    # Common helpers
    "escape_sqlite_string",
    "is_system_schema_sqlite",
    "normalize_sqlite_type",
    "quote_sqlite_identifier",
    "sqlite_type_mapping",
]


def _register_sqlite_adapters() -> None:
    """Registra adaptadores SQLite en el registry global.

    Llamado automáticamente al importar este módulo.
    """
    try:
        from ..adapters import get_global_adapter_registry

        registry = get_global_adapter_registry()

        registry.register_source_adapter_sync("sqlite", SqliteSyncAdapter)
        registry.register_source_adapter_async("sqlite", SqliteAsyncAdapter)

    except ImportError:
        # registry no disponible, fallback silencioso
        pass


# Auto-registrar al importar
_register_sqlite_adapters()
