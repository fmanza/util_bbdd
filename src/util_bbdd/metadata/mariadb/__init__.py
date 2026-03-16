"""Helpers MariaDB compartidos para managers sync/async."""

from .async_adapter import MariaDBAsyncAdapter
from .common import (
    decode_mariadb_hex_text,
    escape_mariadb_sql_literal,
    format_mariadb_default,
    normalize_mariadb_routine_status_rows,
    parse_mariadb_column_charset_collation_row,
    parse_mariadb_db_charset,
    quote_mariadb_identifier,
)
from .routines import (
    build_mariadb_routine_ddl,
    build_public_mariadb_routine_parameter_rows,
    decode_mariadb_routine_detail_rows,
    decode_mariadb_routine_parameter_detail_rows,
    filter_mariadb_routine_parameter_rows,
)
from .sync_adapter import MariaDBSyncAdapter
from .tables import build_mariadb_table_ddl, decode_mariadb_safe_column_rows

__all__: list[str] = [
    "MariaDBAsyncAdapter",
    "MariaDBSyncAdapter",
    "build_mariadb_routine_ddl",
    "build_mariadb_table_ddl",
    "build_public_mariadb_routine_parameter_rows",
    "decode_mariadb_hex_text",
    "decode_mariadb_routine_detail_rows",
    "decode_mariadb_routine_parameter_detail_rows",
    "decode_mariadb_safe_column_rows",
    "escape_mariadb_sql_literal",
    "filter_mariadb_routine_parameter_rows",
    "format_mariadb_default",
    "normalize_mariadb_routine_status_rows",
    "parse_mariadb_column_charset_collation_row",
    "parse_mariadb_db_charset",
    "quote_mariadb_identifier",
]
