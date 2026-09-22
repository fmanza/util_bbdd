"""Adaptadores MySQL para introspección de metadatos.

Proporciona adaptadores sync y async compatibles con duck-typing SourceAdapter
y RoutineAdapter protocols.

Ejemplo de uso:
    from util_bbdd.metadata.mysql import MysqlSyncAdapter, MysqlAsyncAdapter

    # O dejar que el registry auto-resuelva:
    from util_bbdd.metadata.adapters import get_global_adapter_registry
    registry = get_global_adapter_registry()
    adapter_class = registry.get_source_adapter_sync("mysql")

El registro global se popula automáticamente al importar este módulo.
"""

from __future__ import annotations

from ._mysql_models import MysqlRoutineDetail
from .async_adapter import MysqlAsyncAdapter
from .common import (
    decode_mysql_cascade_action,
    escape_mysql_string,
    is_system_schema_mysql,
    mysql_type_mapping,
    normalize_mysql_type,
    quote_mysql_identifier,
)
from .sync_adapter import MysqlSyncAdapter

__all__: list[str] = [
    # Adapters
    "MysqlAsyncAdapter",
    "MysqlSyncAdapter",
    # Models
    "MysqlRoutineDetail",
    # Common helpers
    "decode_mysql_cascade_action",
    "escape_mysql_string",
    "is_system_schema_mysql",
    "mysql_type_mapping",
    "normalize_mysql_type",
    "quote_mysql_identifier",
]


def _register_mysql_adapters() -> None:
    """Registra adaptadores MySQL en el registry global.

    Llamado automáticamente al importar este módulo.
    """
    try:
        from ..adapters import get_global_adapter_registry

        registry = get_global_adapter_registry()

        registry.register_source_adapter_sync("mysql", MysqlSyncAdapter)
        registry.register_source_adapter_async("mysql", MysqlAsyncAdapter)
        registry.register_routine_adapter_sync("mysql", MysqlSyncAdapter)
        registry.register_routine_adapter_async("mysql", MysqlAsyncAdapter)

        # Alternate names commonly used
        registry.register_source_adapter_sync("mariadb-mysql", MysqlSyncAdapter)
        registry.register_source_adapter_async("mariadb-mysql", MysqlAsyncAdapter)
        registry.register_routine_adapter_sync("mariadb-mysql", MysqlSyncAdapter)
        registry.register_routine_adapter_async("mariadb-mysql", MysqlAsyncAdapter)

    except ImportError:
        # registry no disponible, fallback silencioso
        pass


# Auto-registrar al importar
_register_mysql_adapters()
