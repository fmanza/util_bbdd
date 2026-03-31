"""Helpers internos para metadata read-side compartida de managers."""

from __future__ import annotations

import re

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..metadata.mariadb import (
    parse_mariadb_column_charset_collation_row,
    parse_mariadb_db_charset,
)

ColumnCharsetCollationRow = tuple[str, str | None, str | None]


@dataclass(frozen=True)
class MetadataFetchRequest:
    """Describe una consulta de metadata reusable para managers sync/async."""

    query_name: str
    params: dict[str, Any]
    error_message: str
    table_name: str | None = None
    expect_one: bool = False


def build_routines_fetch_request(context_database: str) -> MetadataFetchRequest:
    """Construye la request estándar para listar rutinas."""
    return MetadataFetchRequest(
        query_name="obtener_rutinas",
        params={"database": context_database},
        error_message="Error obteniendo rutinas",
    )


def build_table_ddl_fetch_request(
    context_database: str,
    table_name: str,
    add_metadata_context_params: Callable[[dict[str, Any], str | None], dict[str, Any]],
) -> MetadataFetchRequest:
    """Construye la request estándar para DDL de tabla."""
    return MetadataFetchRequest(
        query_name="create_table",
        params=add_metadata_context_params({"tabla": table_name}, context_database),
        error_message="Error obteniendo DDL",
        table_name=table_name,
        expect_one=True,
    )


def build_view_ddl_fetch_request(
    context_database: str,
    view_name: str,
    add_metadata_context_params: Callable[[dict[str, Any], str | None], dict[str, Any]],
) -> MetadataFetchRequest:
    """Construye la request estándar para DDL de vista."""
    return MetadataFetchRequest(
        query_name="create_view",
        params=add_metadata_context_params({"tabla": view_name}, context_database),
        error_message="Error obteniendo DDL de vista",
        table_name=view_name,
        expect_one=True,
    )


def build_columns_fetch_request(context_database: str, table_name: str) -> MetadataFetchRequest:
    """Construye la request estándar para columnas de tabla."""
    return MetadataFetchRequest(
        query_name="columnas_tabla",
        params={"database": context_database, "tabla": table_name},
        error_message="Error obteniendo columnas",
        table_name=table_name,
    )


def build_routine_parameters_fetch_request(
    context_database: str,
    routine_name: str,
    routine_type: str,
) -> MetadataFetchRequest:
    """Construye la request estándar para parámetros de rutina."""
    return MetadataFetchRequest(
        query_name="parametros_rutina",
        params={
            "database": context_database,
            "rutina": routine_name,
            "tipo_rutina": routine_type,
        },
        error_message="Error obteniendo parámetros de rutina",
        table_name=routine_name,
    )


def build_routine_ddl_fetch_request(
    context_database: str,
    routine_name: str,
    routine_type: str,
    add_metadata_context_params: Callable[[dict[str, Any], str | None], dict[str, Any]],
) -> MetadataFetchRequest:
    """Construye la request estándar para DDL de rutina."""
    return MetadataFetchRequest(
        query_name="create_rutina",
        params=add_metadata_context_params(
            {"rutina": routine_name, "tipo_rutina": routine_type},
            context_database,
        ),
        error_message="Error obteniendo DDL de rutina",
        table_name=routine_name,
        expect_one=True,
    )


def build_sync_rows_fetcher[T](
    *,
    db_type: str,
    mariadb_fetcher: Callable[[], T],
    request: MetadataFetchRequest,
    execute_many: Callable[[MetadataFetchRequest], T],
) -> Callable[[], T]:
    """Selecciona el fetcher sync adecuado para colecciones de metadata."""
    if db_type == "mariadb":
        return mariadb_fetcher

    return lambda: execute_many(request)


def build_sync_text_fetcher(
    *,
    db_type: str,
    mariadb_fetcher: Callable[[], str],
    request: MetadataFetchRequest,
    execute_one: Callable[[MetadataFetchRequest], Any],
    normalize_one: Callable[[Any], str],
) -> Callable[[], str]:
    """Selecciona el fetcher sync adecuado para textos DDL."""
    if db_type == "mariadb":
        return mariadb_fetcher

    return lambda: normalize_one(execute_one(request))


def build_async_rows_fetcher[T](
    *,
    db_type: str,
    mariadb_fetcher: Callable[[], Awaitable[T]],
    request: MetadataFetchRequest,
    execute_many: Callable[[MetadataFetchRequest], Awaitable[T]],
) -> Callable[[], Awaitable[T]]:
    """Selecciona el fetcher async adecuado para colecciones de metadata."""
    if db_type == "mariadb":
        return mariadb_fetcher

    async def _fetch_many() -> T:
        return await execute_many(request)

    return _fetch_many


def build_async_text_fetcher(
    *,
    db_type: str,
    mariadb_fetcher: Callable[[], Awaitable[str]],
    request: MetadataFetchRequest,
    execute_one: Callable[[MetadataFetchRequest], Awaitable[Any]],
    normalize_one: Callable[[Any], str],
) -> Callable[[], Awaitable[str]]:
    """Selecciona el fetcher async adecuado para textos DDL."""
    if db_type == "mariadb":
        return mariadb_fetcher

    async def _fetch_one_normalized() -> str:
        return normalize_one(await execute_one(request))

    return _fetch_one_normalized


def is_lob(value: Any) -> bool:
    """Indica si el valor expone API de lectura tipo LOB."""
    return hasattr(value, "read") and callable(value.read)


def read_lob(value: Any) -> str:
    """Lee de forma segura un valor tipo LOB."""
    try:
        return str(value.read())
    except Exception:
        return str(value)


def contains_create(text: str) -> bool:
    """Indica si el texto contiene una sentencia CREATE."""
    return "CREATE " in text.upper()


def _extract_preferred_ddl_candidate(value: Any) -> str:
    if value is None:
        return ""
    if is_lob(value):
        value = read_lob(value)
    if isinstance(value, (tuple, list)):
        nested_text = normalize_ddl_result(value)
        if contains_create(nested_text):
            return nested_text
        if nested_text.strip():
            return nested_text
        return ""
    text = str(value)
    if contains_create(text):
        return text
    return ""


def _extract_any_text(value: Any) -> str:
    if value is None:
        return ""
    if is_lob(value):
        return read_lob(value)
    if isinstance(value, (tuple, list)):
        return normalize_ddl_result(value)
    text = str(value)
    return text if text.strip() else ""


def normalize_ddl_result(ddl: Any) -> str:
    """Normaliza resultados heterogéneos de consultas DDL a texto."""
    if ddl is None:
        return ""
    if isinstance(ddl, str):
        return ddl
    if is_lob(ddl):
        return read_lob(ddl)
    if not isinstance(ddl, (tuple, list)):
        return str(ddl)

    for pos in (2, 1, 0):
        if len(ddl) <= pos:
            continue
        candidate = _extract_preferred_ddl_candidate(ddl[pos])
        if candidate:
            return candidate

    for value in ddl:
        text = _extract_any_text(value)
        if text:
            return text

    return ""


def parse_db_charset_oracle(result: tuple[Any, ...]) -> dict[str, Any]:
    """Parsea metadata charset/collation de Oracle."""
    if not result:
        return {}
    charset: str = str(result[0])
    if len(result) > 1:
        return {"charset": charset, "nchar_charset": str(result[1])}
    return {"charset": charset}


def parse_db_charset_postgresql(result: tuple[Any, ...]) -> dict[str, Any]:
    """Parsea metadata charset/collation de PostgreSQL."""
    if len(result) > 2:
        return {"encoding": str(result[0]), "collate": str(result[1]), "ctype": str(result[2])}
    if len(result) > 0:
        return {"encoding": str(result[0])}
    return {}


def parse_db_charset_single_field(result: tuple[Any, ...], field_name: str) -> dict[str, Any]:
    """Parsea metadata charset/collation de un único campo."""
    if len(result) == 0:
        return {}
    return {field_name: str(result[0])}


def parse_charset_collation_result(db_type: str, result: tuple[Any, ...] | None) -> dict[str, Any]:
    """Parsea resultado de charset/collation de base de datos según motor."""
    if not result:
        return {}

    parser_map = {
        "mariadb": parse_mariadb_db_charset,
        "oracle": parse_db_charset_oracle,
        "postgresql": parse_db_charset_postgresql,
        "sqlserver": lambda row: parse_db_charset_single_field(row, "collation"),
        "hsqldb": lambda row: parse_db_charset_single_field(row, "collation"),
        "sqlite": lambda row: parse_db_charset_single_field(row, "encoding"),
    }
    parser = parser_map.get(db_type, lambda _row: {})
    return parser(result)


def parse_collation_only_row(row: tuple[Any, ...], column_name: str) -> ColumnCharsetCollationRow:
    """Parsea filas que solo exponen collation."""
    collation: str | None = str(row[2]) if len(row) > 2 else None
    return (column_name, None, collation)


def parse_empty_charset_collation_row(_row: tuple[Any, ...], column_name: str) -> ColumnCharsetCollationRow:
    """Parsea filas sin soporte de charset/collation por columna."""
    return (column_name, None, None)


def parse_column_charset_collation_row(db_type: str, row: tuple[Any, ...]) -> ColumnCharsetCollationRow:
    """Parsea una fila de charset/collation por columna según motor."""
    column_name: str = str(row[0]) if len(row) > 0 else ""
    parser_map = {
        "mariadb": parse_mariadb_column_charset_collation_row,
        "oracle": parse_collation_only_row,
        "postgresql": parse_collation_only_row,
        "sqlserver": parse_collation_only_row,
        "hsqldb": parse_collation_only_row,
        "sqlite": parse_empty_charset_collation_row,
    }
    parser = parser_map.get(db_type, parse_empty_charset_collation_row)
    return parser(row, column_name)


def oracle_supports_columns_charset_collation(version_text: str) -> bool:
    """Evalúa si una versión Oracle soporta collation por columna."""
    version_match: re.Match[str] | None = re.search(r"Release\s+(\d+)\.(\d+)", version_text)
    if version_match is None:
        return False
    major = int(version_match.group(1))
    minor = int(version_match.group(2))
    return (major, minor) >= (12, 2)


def supports_columns_charset_collation(db_type: str, oracle_supported: bool | None = None) -> bool:
    """Indica si el motor soporta metadata fiable de charset/collation por columna."""
    if db_type == "oracle":
        return bool(oracle_supported) if oracle_supported is not None else False
    return db_type != "sqlite"


__all__: list[str] = [
    "MetadataFetchRequest",
    "build_async_rows_fetcher",
    "build_async_text_fetcher",
    "build_columns_fetch_request",
    "build_routine_ddl_fetch_request",
    "build_routine_parameters_fetch_request",
    "build_routines_fetch_request",
    "build_sync_rows_fetcher",
    "build_sync_text_fetcher",
    "build_table_ddl_fetch_request",
    "build_view_ddl_fetch_request",
    "ColumnCharsetCollationRow",
    "contains_create",
    "is_lob",
    "normalize_ddl_result",
    "oracle_supports_columns_charset_collation",
    "parse_charset_collation_result",
    "parse_column_charset_collation_row",
    "read_lob",
    "supports_columns_charset_collation",
]
