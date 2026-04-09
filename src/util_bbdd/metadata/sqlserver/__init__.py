"""Adaptadores SQL Server para introspección de metadatos.

Proporciona adaptadores sync y async compatibles con duck-typing SourceAdapter
y RoutineAdapter protocols.

Ejemplo de uso:
    from util_bbdd.metadata.sqlserver import SqlServerSyncAdapter, SqlServerAsyncAdapter

    # O dejar que el registry auto-resuelva:
    from util_bbdd.metadata.adapters import get_global_adapter_registry
    registry = get_global_adapter_registry()
    adapter_class = registry.get_source_adapter_sync("sqlserver")

El registro global se popula automáticamente al importar este módulo.
"""

from __future__ import annotations

from ._sqlserver_models import SqlServerParameterDetail, SqlServerRoutineDetail
from .async_adapter import SqlServerAsyncAdapter
from .common import (
    decode_sqlserver_cascade_action,
    escape_sqlserver_string,
    is_system_schema_sqlserver,
    normalize_sqlserver_type,
    quote_sqlserver_identifier,
    sqlserver_type_mapping,
)
from .sync_adapter import SqlServerSyncAdapter

__all__: list[str] = [
    # Adapters
    "SqlServerAsyncAdapter",
    "SqlServerSyncAdapter",
    # Models
    "SqlServerParameterDetail",
    "SqlServerRoutineDetail",
    # Common helpers
    "decode_sqlserver_cascade_action",
    "escape_sqlserver_string",
    "is_system_schema_sqlserver",
    "normalize_sqlserver_type",
    "quote_sqlserver_identifier",
    "sqlserver_type_mapping",
]


def _register_sqlserver_adapters() -> None:
    """Registra adaptadores SQL Server en el registry global.

    Llamado automáticamente al importar este módulo.
    """
    try:
        from ..adapters import get_global_adapter_registry

        registry = get_global_adapter_registry()

        registry.register_source_adapter_sync("sqlserver", SqlServerSyncAdapter)
        registry.register_source_adapter_async("sqlserver", SqlServerAsyncAdapter)

        # Alternate names commonly used
        registry.register_source_adapter_sync("mssql", SqlServerSyncAdapter)
        registry.register_source_adapter_async("mssql", SqlServerAsyncAdapter)

    except ImportError:
        # registry no disponible, fallback silencioso
        pass


# Auto-registrar al importar
_register_sqlserver_adapters()
