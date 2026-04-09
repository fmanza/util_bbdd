"""Adaptadores Redshift para introspección de metadatos.

Proporciona adaptadores sync y async compatibles con duck-typing SourceAdapter
y RoutineAdapter protocols.

Redshift es una base de datos derivada de PostgreSQL con diferencias clave:
- Tipos: Subconjunto de PostgreSQL (sin arrays, ranges, UDTs)
- Constraints: PK/FK/CHECK son ADVISORY (metadata-only, no enforced)
- Catalogs: pg_catalog (schemas, tablas) + information_schema (columnas, routines)
- Rendimiento: Optimizado para OLAP; incluye SortKeys (metadata)

Ejemplo de uso:
    from util_bbdd.metadata.redshift import RedshiftSyncAdapter, RedshiftAsyncAdapter

    # O dejar que el registry auto-resuelva:
    from util_bbdd.metadata.adapters import get_global_adapter_registry
    registry = get_global_adapter_registry()
    adapter_class = registry.get_source_adapter_sync("redshift")

El registro global se popula automáticamente al importar este módulo.
"""

from __future__ import annotations

from ._redshift_models import RedshiftRoutineDetail
from .async_adapter import RedshiftAsyncAdapter
from .common import (
    escape_redshift_string,
    is_system_schema_redshift,
    normalize_redshift_type,
    quote_redshift_identifier,
    redshift_type_mapping,
)
from .sync_adapter import RedshiftSyncAdapter

__all__: list[str] = [
    # Adapters
    "RedshiftAsyncAdapter",
    "RedshiftSyncAdapter",
    # Models
    "RedshiftRoutineDetail",
    # Common helpers
    "escape_redshift_string",
    "is_system_schema_redshift",
    "normalize_redshift_type",
    "quote_redshift_identifier",
    "redshift_type_mapping",
]


def _register_redshift_adapters() -> None:
    """Registra adaptadores Redshift en el registry global.

    Llamado automáticamente al importar este módulo.
    """
    try:
        from ..adapters import get_global_adapter_registry

        registry = get_global_adapter_registry()

        registry.register_source_adapter_sync("redshift", RedshiftSyncAdapter)
        registry.register_source_adapter_async("redshift", RedshiftAsyncAdapter)

        # Alternate names commonly used
        registry.register_source_adapter_sync("redshift-postgres", RedshiftSyncAdapter)
        registry.register_source_adapter_async("redshift-postgres", RedshiftAsyncAdapter)

    except ImportError:
        # registry no disponible, fallback silencioso
        pass


# Auto-registrar al importar
_register_redshift_adapters()
