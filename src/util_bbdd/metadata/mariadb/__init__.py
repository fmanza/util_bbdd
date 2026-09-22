"""Helpers MariaDB compartidos para managers sync/async."""

from __future__ import annotations

from ._routine_models import MariaDBRoutineDetail, MariaDBRoutineParameterDetail
from .async_adapter import MariaDBAsyncAdapter
from .common import (
    decode_mariadb_hex_text,
    escape_mariadb_sql_literal,
    format_mariadb_default,
    parse_mariadb_column_charset_collation_row,
    parse_mariadb_db_charset,
    quote_mariadb_identifier,
)
from .routines import (
    build_mariadb_routine_ddl,
    build_public_mariadb_routine_parameter_entry_rows,
    decode_mariadb_routine_detail_entries,
    decode_mariadb_routine_parameter_detail_entries,
    filter_mariadb_routine_parameter_entries,
)
from .sync_adapter import MariaDBSyncAdapter
from .tables import build_mariadb_table_ddl, decode_mariadb_safe_column_rows

__all__: list[str] = [
    "MariaDBAsyncAdapter",
    "MariaDBRoutineDetail",
    "MariaDBRoutineParameterDetail",
    "MariaDBSyncAdapter",
    "build_mariadb_routine_ddl",
    "build_public_mariadb_routine_parameter_entry_rows",
    "build_mariadb_table_ddl",
    "decode_mariadb_hex_text",
    "decode_mariadb_routine_detail_entries",
    "decode_mariadb_routine_parameter_detail_entries",
    "decode_mariadb_safe_column_rows",
    "escape_mariadb_sql_literal",
    "filter_mariadb_routine_parameter_entries",
    "format_mariadb_default",
    "parse_mariadb_column_charset_collation_row",
    "parse_mariadb_db_charset",
    "quote_mariadb_identifier",
]


# Registrar adapters en el registry global (se ejecuta una vez al importar este módulo)
def _register_mariadb_adapters() -> None:
    """Registra adapters MariaDB en el registry global de adapters.

    Falla silenciosamente solo si el registry no está disponible (import circular
    o entorno especial). MDC-04 (AUDIT_CODE 2026-09-22): antes capturaba
    ``Exception`` en vez de ``ImportError``, enmascarando errores reales de
    bootstrap — incluido el ``ValueError`` que el registry lanza a propósito ante
    un doble registro (p.ej. una recarga accidental del módulo en tests).
    """
    try:
        from ..adapters import get_global_adapter_registry

        registry = get_global_adapter_registry()
        registry.register_source_adapter_sync("mariadb", MariaDBSyncAdapter)
        registry.register_source_adapter_async("mariadb", MariaDBAsyncAdapter)
        registry.register_routine_adapter_sync("mariadb", MariaDBSyncAdapter)
        registry.register_routine_adapter_async("mariadb", MariaDBAsyncAdapter)
    except ImportError:
        # Silenciosamente fallar si el registry no está disponible
        # (ej: en casos de importación circular o entornos especiales)
        pass


_register_mariadb_adapters()
