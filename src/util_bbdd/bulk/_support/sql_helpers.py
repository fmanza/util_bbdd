"""Helpers internos para serialización y compilación SQL en bulk_crud."""

from __future__ import annotations

import re

from collections.abc import Sequence
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import Delete, Insert, Table, Update, and_, delete, text, update

SqlRecord = dict[str, Any]


def generate_sql_filename(*, engine_url: str, table: str, operation: str) -> Path:
    """Genera un nombre de fichero SQL a partir de la URL del engine."""
    try:
        db_name: str = engine_url.split("/")[-1].split("?")[0]
        if not db_name:
            raise ValueError("No se pudo extraer nombre de BD de engine.url")
    except Exception as error:
        raise ValueError(f"No se pudo extraer nombre de BD de engine.url: {engine_url}") from error

    timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"{db_name}-{table}-{operation.lower()}_{timestamp}.sql")


def generate_insert_sql(stmt: Insert, records: Sequence[SqlRecord], dialect: Any) -> list[str]:
    """Genera SQL INSERT literal para una secuencia de registros."""
    return [compile_stmt_with_binary_support(stmt.values(record), dialect) for record in records]


def generate_insert_sql_override_identity(stmt: Insert, records: Sequence[SqlRecord], dialect: Any) -> list[str]:
    """Genera SQL INSERT PostgreSQL con OVERRIDING SYSTEM VALUE para columnas identity always."""
    result: list[str] = []
    for record in records:
        sql = compile_stmt_with_binary_support(stmt.values(record), dialect)
        sql = re.sub(r"\)\s+VALUES\b", ") OVERRIDING SYSTEM VALUE VALUES", sql, count=1, flags=re.IGNORECASE)
        result.append(sql)
    return result


def build_override_identity_text_stmt(table: Table, columns: Sequence[str], dialect: Any) -> Any:
    """Construye un text() INSERT con OVERRIDING SYSTEM VALUE para ejecución en PostgreSQL."""
    preparer = dialect.identifier_preparer
    quoted_table: str = preparer.format_table(table)
    quoted_cols: list[str] = [preparer.quote(col) for col in columns]
    params: list[str] = [f":{col}" for col in columns]
    sql: str = (
        f"INSERT INTO {quoted_table} ({', '.join(quoted_cols)}) OVERRIDING SYSTEM VALUE VALUES ({', '.join(params)})"
    )
    return text(sql)


def should_wrap_identity_insert(table: Table, insert_cols: Sequence[str], dialect: Any) -> bool:
    """Devuelve True si hay que envolver los INSERT con SET IDENTITY_INSERT ON/OFF.

    Solo aplica en MSSQL cuando alguna columna de insert_cols tiene IDENTITY definida
    en la tabla (getattr(col, 'identity', None) is not None).
    """
    if dialect.name != "mssql":
        return False
    col_set: set[str] = set(insert_cols)
    return any(col.name in col_set and getattr(col, "identity", None) is not None for col in table.columns)


def wrap_identity_insert_sql(sql_lines: list[str], table: Table, dialect: Any) -> list[str]:
    """Envuelve una lista de INSERT con SET IDENTITY_INSERT <tabla> ON/OFF para SQL Server."""
    preparer = dialect.identifier_preparer
    quoted_table: str = preparer.format_table(table)
    return [
        f"SET IDENTITY_INSERT {quoted_table} ON;",
        *sql_lines,
        f"SET IDENTITY_INSERT {quoted_table} OFF;",
    ]


def generate_update_sql(
    *,
    table: Table,
    records: Sequence[SqlRecord],
    update_cols: Sequence[str],
    pk_param_map: dict[str, str],
    pk_cols: Sequence[str],
    dialect: Any,
) -> list[str]:
    """Genera SQL UPDATE literal para una secuencia de registros."""
    sql_lines: list[str] = []
    for record in records:
        update_values: dict[str, Any] = {column: record[column] for column in update_cols}
        pk_conditions: dict[str, Any] = {pk_param_map[column]: record[pk_param_map[column]] for column in pk_cols}
        stmt: Update = (
            update(table)
            .where(and_(*(table.c[column] == pk_conditions[pk_param_map[column]] for column in pk_cols)))
            .values(update_values)
        )
        sql_lines.append(compile_stmt_with_binary_support(stmt, dialect))
    return sql_lines


def generate_delete_sql(
    *,
    records: Sequence[SqlRecord],
    table: Table,
    pk_cols: Sequence[str],
    dialect: Any,
) -> list[str]:
    """Genera SQL DELETE literal para una secuencia de claves primarias."""
    sql_lines: list[str] = []
    for record in records:
        conditions = [table.c[column] == record[column] for column in pk_cols]
        stmt: Delete = delete(table).where(and_(*conditions))
        sql_lines.append(compile_stmt_with_binary_support(stmt, dialect))
    return sql_lines


def _substitute_ordered_params(sql_text: str, ordered_params: list[Any]) -> str:
    """Sustituye parámetros ordenados usando placeholders %s o ?."""
    if "%s" in sql_text:
        for param_value in ordered_params:
            sql_text = sql_text.replace("%s", format_sql_param_value(param_value), 1)
        return sql_text

    if "?" in sql_text:
        for param_value in ordered_params:
            sql_text = sql_text.replace("?", format_sql_param_value(param_value), 1)
        return sql_text

    return sql_text


def _substitute_named_params(sql_text: str, params: dict[str, Any]) -> str:
    """Sustituye parámetros nombrados usando formatos %(name)s o :name."""
    sql_result: str = sql_text
    for param_name, param_value in params.items():
        sql_literal: str = format_sql_param_value(param_value)
        sql_result = re.sub(rf"%\({re.escape(param_name)}\)s", sql_literal, sql_result)
        sql_result = re.sub(rf":{re.escape(param_name)}\b", sql_literal, sql_result)
    return sql_result


def _get_ordered_params(compiled: Any, params: dict[str, Any]) -> list[Any]:
    """Obtiene parámetros en orden desde positiontup o como lista de valores."""
    positiontup = getattr(compiled, "positiontup", None)
    if positiontup:
        return [params[name] for name in positiontup if name in params]
    return list(params.values())


def compile_stmt_with_binary_support(stmt: Any, dialect: Any) -> str:
    """Compila un statement con fallback para binarios no renderizables."""
    try:
        compiled = stmt.compile(dialect=dialect, compile_kwargs={"literal_binds": True})
        return f"{compiled};"
    except Exception as error:
        if "BLOB" not in str(error) and "binary" not in str(error).lower():
            raise

        compiled = stmt.compile(dialect=dialect)
        sql_text = str(compiled)
        params = compiled.params or {}
        if not params:
            return f"{sql_text};"

        ordered_params = _get_ordered_params(compiled, params)
        sql_text = _substitute_ordered_params(sql_text, ordered_params)
        if sql_text != str(compiled):
            return f"{sql_text};"

        sql_result = _substitute_named_params(sql_text, params)
        return f"{sql_result};"


def format_sql_param_value(value: Any) -> str:
    """Convierte un valor Python a su literal SQL."""
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return f"0x{value.hex().upper()}"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (datetime, date, time)):
        return f"'{str(value)}'"
    if isinstance(value, str):
        escaped_value: str = value.replace("'", "''")
        return f"'{escaped_value}'"
    if isinstance(value, (int, float)):
        return str(value)

    string_value: str = str(value)
    escaped_string: str = string_value.replace("'", "''")
    return f"'{escaped_string}'"


__all__: list[str] = [
    "SqlRecord",
    "build_override_identity_text_stmt",
    "compile_stmt_with_binary_support",
    "format_sql_param_value",
    "generate_delete_sql",
    "generate_insert_sql",
    "generate_insert_sql_override_identity",
    "generate_sql_filename",
    "generate_update_sql",
    "should_wrap_identity_insert",
    "wrap_identity_insert_sql",
]
