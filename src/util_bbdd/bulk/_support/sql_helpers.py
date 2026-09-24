"""Helpers internos para serialización y compilación SQL en bulk_crud."""

from __future__ import annotations

import re

from collections.abc import Sequence
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, BindParameter, Delete, Insert, Table, Update, and_, bindparam, delete, text, update
from sqlalchemy.engine import Dialect, make_url
from sqlalchemy.sql.sqltypes import _Binary
from sqlalchemy.types import TypeDecorator, TypeEngine

SqlRecord = dict[str, Any]


class PreSerializedJSON(TypeDecorator[Any]):
    """Tipo de parámetro para columnas JSON cuyo valor ya llega serializado por ``normalize_sql_literal``.

    P-19 (performance-audit de bulk, 2026-09-24): con el tipo ``JSON`` reflejado, SQLAlchemy volvía a serializar el
    texto (se guardaba un *string* JSON) y convertía ``None`` en el literal JSON ``null`` en lugar de ``NULL`` SQL.
    Este tipo no procesa el valor, pero conserva el tipo de la columna para el dialecto, de modo que PostgreSQL sigue
    recibiendo el cast (``::JSONB`` / ``::JSON``).
    """

    impl = JSON
    cache_ok = True

    def __init__(self, target: TypeEngine[Any]) -> None:
        super().__init__()
        self.target = target

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        return dialect.type_descriptor(self.target)

    def bind_processor(self, dialect: Dialect) -> None:
        return None


def restore_binary_values(records: Sequence[SqlRecord], table: Table) -> None:
    """Devuelve a ``bytes`` los valores de columnas binarias que ``normalize_sql_literal`` decodificó a ``str``.

    P-21 (performance-audit de bulk, 2026-09-24): ``normalize_sql_literal`` decodifica los ``bytes`` que son UTF-8 válido
    (``b"q"`` → ``"q"``). En columnas binarias, los parámetros tipados rechazaban ese ``str`` (``TypeError``) y Oracle lo
    guardaba como NULL. Codificar de nuevo en UTF-8 recupera exactamente los bytes originales. Modifica ``records``.
    """
    if not records:
        return
    binary_cols = [name for name in records[0] if name in table.c and isinstance(table.c[name].type, _Binary)]
    for record in records:
        for name in binary_cols:
            value = record[name]
            if isinstance(value, str):
                record[name] = value.encode("utf-8")


def json_passthrough_binds(table: Table, columns: Sequence[str]) -> dict[str, BindParameter[Any]]:
    """Devuelve ``{columna: bindparam}`` con :class:`PreSerializedJSON` para las columnas JSON de ``columns``.

    Pensado para ``insert(tabla).values(...)`` / ``update(tabla).values(...)``: las demás columnas se enlazan como
    siempre. Vacío si ninguna columna es de tipo JSON.
    """
    return {
        name: bindparam(name, type_=PreSerializedJSON(table.c[name].type))
        for name in columns
        if name in table.c and isinstance(table.c[name].type, JSON)
    }


def generate_sql_filename(*, engine_url: str, table: str, operation: str) -> Path:
    """Genera un nombre de fichero SQL a partir de la URL del engine."""
    try:
        db_name: str = make_url(engine_url).database or ""
    except Exception as error:
        raise ValueError(f"No se pudo extraer nombre de BD de engine.url: {engine_url}") from error
    if not db_name:
        raise ValueError(f"No se pudo extraer nombre de BD de engine.url: {engine_url}")

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
    """Sustituye parámetros ordenados usando placeholders %s o ?.

    BLK-05 (AUDIT_CODE 2026-09-22): localiza las posiciones de los placeholders
    en el ``sql_text`` original antes de sustituir, en vez de encadenar
    ``str.replace(..., 1)`` sobre el resultado parcial. Un valor de parámetro
    que contenga literalmente "%s" o "?" (p.ej. un BLOB/texto de usuario)
    podía ser reescaneado por la sustitución del siguiente parámetro y
    corromper el SQL generado.
    """
    if "%s" in sql_text:
        placeholder = "%s"
    elif "?" in sql_text:
        placeholder = "?"
    else:
        return sql_text

    positions: list[int] = [match.start() for match in re.finditer(re.escape(placeholder), sql_text)]
    if not positions:
        return sql_text

    placeholder_len = len(placeholder)
    result_parts: list[str] = []
    previous_end = 0
    for position, param_value in zip(positions, ordered_params, strict=False):
        result_parts.append(sql_text[previous_end:position])
        result_parts.append(format_sql_param_value(param_value))
        previous_end = position + placeholder_len
    result_parts.append(sql_text[previous_end:])
    return "".join(result_parts)


def _substitute_named_params(sql_text: str, params: dict[str, Any]) -> str:
    """Sustituye parámetros nombrados usando formatos %(name)s o :name.

    BLK-05 (AUDIT_CODE 2026-09-22): localiza todas las posiciones de
    placeholders en el ``sql_text`` original antes de sustituir, en vez de
    aplicar ``re.sub`` de forma incremental sobre el resultado parcial. Un
    valor ya sustituido que contuviera literalmente ":otro_param" o
    "%(otro_param)s" podía ser reescaneado y corromper sustituciones
    posteriores.
    """
    if not params:
        return sql_text

    matches: list[tuple[int, int, str]] = []
    for param_name in params:
        pattern = re.compile(rf"%\({re.escape(param_name)}\)s|:{re.escape(param_name)}\b")
        matches.extend((match.start(), match.end(), param_name) for match in pattern.finditer(sql_text))
    matches.sort(key=lambda item: item[0])

    result_parts: list[str] = []
    previous_end = 0
    for start, end, param_name in matches:
        if start < previous_end:
            continue
        result_parts.append(sql_text[previous_end:start])
        result_parts.append(format_sql_param_value(params[param_name]))
        previous_end = end
    result_parts.append(sql_text[previous_end:])
    return "".join(result_parts)


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
    "PreSerializedJSON",
    "SqlRecord",
    "build_override_identity_text_stmt",
    "compile_stmt_with_binary_support",
    "format_sql_param_value",
    "generate_delete_sql",
    "generate_insert_sql",
    "generate_insert_sql_override_identity",
    "generate_sql_filename",
    "generate_update_sql",
    "json_passthrough_binds",
    "restore_binary_values",
    "should_wrap_identity_insert",
    "wrap_identity_insert_sql",
]
