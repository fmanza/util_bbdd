"""Adaptadores PostgreSQL para introspección de metadatos.

Proporciona adaptadores sync y async compatibles con duck-typing SourceAdapter
y RoutineAdapter protocols.

Ejemplo de uso:
    from util_bbdd.metadata.postgresql import PostgreSQLSyncAdapter, PostgreSQLAsyncAdapter

    # O dejar que el registry auto-resuelva:
    from util_bbdd.metadata.adapters import get_global_adapter_registry
    registry = get_global_adapter_registry()
    adapter_class = registry.get_source_adapter_sync("postgresql")

El registro global se popula automáticamente al importar este módulo.
"""

from __future__ import annotations

from ._postgres_models import PgParameterDetail, PgRoutineDetail
from .async_adapter import PostgreSQLAsyncAdapter
from .common import (
    escape_pg_literal,
    get_pg_type_name_from_oid,
    normalize_postgres_type,
    parse_pg_array_type,
    parse_pg_type_with_params,
    quote_pg_identifier,
)
from .routines import (
    build_postgres_routine_ddl,
    build_public_postgres_routine_parameter_entry_rows,
    decode_postgres_parameter_rows,
    decode_postgres_routine_rows,
    filter_postgres_routine_parameter_entries,
    routine_entries_to_rows,
)
from .sync_adapter import PostgreSQLSyncAdapter
from .tables import (
    build_postgres_table_ddl,
    build_schema_qualified_table_name,
    decode_postgres_column_rows,
    fetch_columns_sql,
    fetch_fk_constraint_sql,
    fetch_indexes_sql,
    fetch_pk_constraint_sql,
    fetch_schemas_sql,
    fetch_tables_sql,
    fetch_unique_constraint_sql,
)

__all__: list[str] = [
    # Adapters
    "PostgreSQLAsyncAdapter",
    "PostgreSQLSyncAdapter",
    # Models
    "PgParameterDetail",
    "PgRoutineDetail",
    # Common helpers
    "escape_pg_literal",
    "get_pg_type_name_from_oid",
    "normalize_postgres_type",
    "parse_pg_array_type",
    "parse_pg_type_with_params",
    "quote_pg_identifier",
    # Routines
    "build_postgres_routine_ddl",
    "build_public_postgres_routine_parameter_entry_rows",
    "decode_postgres_parameter_rows",
    "decode_postgres_routine_rows",
    "filter_postgres_routine_parameter_entries",
    "routine_entries_to_rows",
    # Tables
    "build_postgres_table_ddl",
    "build_schema_qualified_table_name",
    "decode_postgres_column_rows",
    "fetch_columns_sql",
    "fetch_fk_constraint_sql",
    "fetch_indexes_sql",
    "fetch_pk_constraint_sql",
    "fetch_schemas_sql",
    "fetch_tables_sql",
    "fetch_unique_constraint_sql",
]


def _register_postgresql_adapters() -> None:
    """Registra adaptadores PostgreSQL en el registry global de adaptadores.

    Se ejecuta al importar este módulo. Falla silenciosamente si el registry
    no está disponible (p.ej. entornos especiales o importación circular).
    """
    try:
        from ..adapters import get_global_adapter_registry

        registry = get_global_adapter_registry()
        registry.register_source_adapter_sync("postgresql", PostgreSQLSyncAdapter)
        registry.register_source_adapter_async("postgresql", PostgreSQLAsyncAdapter)
        registry.register_routine_adapter_sync("postgresql", PostgreSQLSyncAdapter)
        registry.register_routine_adapter_async("postgresql", PostgreSQLAsyncAdapter)
    except Exception:
        # Silenciosamente fallar si el registry no está disponible
        # (ej: en casos de importación circular o entornos especiales)
        pass


_register_postgresql_adapters()
