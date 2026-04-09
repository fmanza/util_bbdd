"""Adaptadores Snowflake para introspección de metadatos.

Proporciona adaptadores sync y async compatibles con duck-typing SourceAdapter
y RoutineAdapter protocols.

Snowflake es un cloud warehouse con características únicas:
- Esquema de 3 niveles: DATABASE.SCHEMA.TABLE
- Tipos: SQL estándar + semi-structured (OBJECT, ARRAY, VARIANT)
- Constraints: PK/FK/CHECK son ADVISORY (metadata-only, no enforced)
- Catalogs: INFORMATION_SCHEMA (estándar SQL, Snowflake dialect)
- Índices: NO nativos; usa CLUSTERING KEY para optimización
- UDFs: soporte para SQL, JavaScript, Java, Python, etc.

Ejemplo de uso:
    from util_bbdd.metadata.snowflake import SnowflakeSyncAdapter, SnowflakeAsyncAdapter

    # O dejar que el registry auto-resuelva:
    from util_bbdd.metadata.adapters import get_global_adapter_registry
    registry = get_global_adapter_registry()
    adapter_class = registry.get_source_adapter_sync("snowflake")

El registro global se popula automáticamente al importar este módulo.
"""

from __future__ import annotations

from ._snowflake_models import SnowflakeRoutineDetail
from .async_adapter import SnowflakeAsyncAdapter
from .common import (
    escape_snowflake_string,
    is_system_schema_snowflake,
    normalize_snowflake_identifier,
    normalize_snowflake_type,
    parse_snowflake_database_schema_table,
    quote_snowflake_identifier,
    snowflake_type_mapping,
)
from .sync_adapter import SnowflakeSyncAdapter

__all__: list[str] = [
    # Adapters
    "SnowflakeAsyncAdapter",
    "SnowflakeSyncAdapter",
    # Models
    "SnowflakeRoutineDetail",
    # Common helpers
    "escape_snowflake_string",
    "is_system_schema_snowflake",
    "normalize_snowflake_identifier",
    "normalize_snowflake_type",
    "parse_snowflake_database_schema_table",
    "quote_snowflake_identifier",
    "snowflake_type_mapping",
]


def _register_snowflake_adapters() -> None:
    """Registra adaptadores Snowflake en el registry global.

    Llamado automáticamente al importar este módulo.
    """
    try:
        from ..adapters import get_global_adapter_registry

        registry = get_global_adapter_registry()

        registry.register_source_adapter_sync("snowflake", SnowflakeSyncAdapter)
        registry.register_source_adapter_async("snowflake", SnowflakeAsyncAdapter)

        # Alternate names commonly used
        registry.register_source_adapter_sync("snowflake-cloud", SnowflakeSyncAdapter)
        registry.register_source_adapter_async("snowflake-cloud", SnowflakeAsyncAdapter)

    except ImportError:
        # registry no disponible, fallback silencioso
        pass


# Auto-registrar al importar
_register_snowflake_adapters()
