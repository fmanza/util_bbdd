"""Adaptadores Oracle para introspección de metadatos.

Proporciona adaptadores sync y async compatibles con duck-typing SourceAdapter
y RoutineAdapter protocols.

Ejemplo de uso:
    from util_bbdd.metadata.oracle import OracleSyncAdapter, OracleAsyncAdapter

    # O dejar que el registry auto-resuelva:
    from util_bbdd.metadata.adapters import get_global_adapter_registry
    registry = get_global_adapter_registry()
    adapter_class = registry.get_source_adapter_sync("oracle")

El registro global se popula automáticamente al importar este módulo.
"""

from __future__ import annotations

from ._oracle_models import OracleParameterDetail, OracleRoutineDetail
from .async_adapter import OracleAsyncAdapter
from .common import (
    escape_oracle_string,
    get_oracle_table_type,
    is_system_schema_oracle,
    normalize_oracle_type,
    oracle_type_mapping,
    parse_oracle_number_precision_scale,
    quote_oracle_identifier,
)
from .sync_adapter import OracleSyncAdapter

__all__: list[str] = [
    # Adapters
    "OracleAsyncAdapter",
    "OracleSyncAdapter",
    # Models
    "OracleParameterDetail",
    "OracleRoutineDetail",
    # Common helpers
    "escape_oracle_string",
    "get_oracle_table_type",
    "is_system_schema_oracle",
    "normalize_oracle_type",
    "oracle_type_mapping",
    "parse_oracle_number_precision_scale",
    "quote_oracle_identifier",
]


def _register_oracle_adapters() -> None:
    """Registra adaptadores Oracle en el registry global de adaptadores.

    Se ejecuta al importar este módulo. Falla silenciosamente solo si el registry
    no está disponible (p.ej. entornos especiales o importación circular). MDC-04
    (AUDIT_CODE 2026-09-22, mismo patrón detectado en mariadb): antes capturaba
    ``Exception`` en vez de ``ImportError``, enmascarando errores reales de
    bootstrap — incluido el ``ValueError`` que el registry lanza a propósito ante
    un doble registro.
    """
    try:
        from ..adapters import get_global_adapter_registry

        registry = get_global_adapter_registry()
        registry.register_source_adapter_sync("oracle", OracleSyncAdapter)
        registry.register_source_adapter_async("oracle", OracleAsyncAdapter)
        registry.register_routine_adapter_sync("oracle", OracleSyncAdapter)
        registry.register_routine_adapter_async("oracle", OracleAsyncAdapter)
    except ImportError:
        pass


# Auto-register al importar
_register_oracle_adapters()
