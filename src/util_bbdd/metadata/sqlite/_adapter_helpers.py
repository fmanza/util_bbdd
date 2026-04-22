"""Helpers para construcción y decodificación de queries SQLite.

Funciones puras para generar PRAGMA queries y decodificar resultados.
"""

from __future__ import annotations

from typing import Any

from ._sqlite_models import SqlitePragmaResult
from .common import quote_sqlite_identifier


def build_pragma_table_query(table_name: str) -> str:
    """Construye query PRAGMA table_info para introspección de columnas.

    Args:
        table_name: Nombre de la tabla

    Returns:
        str: SQL PRAGMA table_info
    """
    escaped_table = quote_sqlite_identifier(table_name)
    return f"PRAGMA table_info({escaped_table});"


def build_pragma_fk_query(table_name: str) -> str:
    """Construye query PRAGMA foreign_key_list para introspección de FKs.

    Nota: Requiere PRAGMA foreign_keys=ON activado en la conexión.

    Args:
        table_name: Nombre de la tabla

    Returns:
        str: SQL PRAGMA foreign_key_list
    """
    escaped_table = quote_sqlite_identifier(table_name)
    return f"PRAGMA foreign_key_list({escaped_table});"


def build_pragma_index_list_query(table_name: str) -> str:
    """Construye query PRAGMA index_list para introspección de índices.

    Args:
        table_name: Nombre de la tabla

    Returns:
        str: SQL PRAGMA index_list
    """
    escaped_table = quote_sqlite_identifier(table_name)
    return f"PRAGMA index_list({escaped_table});"


def build_pragma_index_info_query(index_name: str) -> str:
    """Construye query PRAGMA index_info para introspección de columnas de índice.

    Args:
        index_name: Nombre del índice

    Returns:
        str: SQL PRAGMA index_info
    """
    escaped_index = quote_sqlite_identifier(index_name)
    return f"PRAGMA index_info({escaped_index});"


def _normalize_pragma_table_result(row: Any) -> SqlitePragmaResult | None:
    """Normaliza una fila individual de PRAGMA table_info a SqlitePragmaResult.

    Args:
        row: Tupla de 6+ elementos de PRAGMA table_info

    Returns:
        SqlitePragmaResult o None si es inválida
    """
    if not row or len(row) < 6:
        return None

    return SqlitePragmaResult(
        cid=int(row[0]) if row[0] is not None else -1,
        name=str(row[1]) if row[1] else "",
        type_name=str(row[2]) if row[2] else "TEXT",
        notnull=int(row[3]) if row[3] is not None else 0,
        default_value=str(row[4]) if row[4] else None,
        pk=int(row[5]) if row[5] is not None else 0,
    )


def decode_pragma_table_info_rows(rows: list[Any]) -> list[SqlitePragmaResult]:
    """Decodifica resultados de PRAGMA table_info a SqlitePragmaResult.

    PRAGMA table_info retorna: (cid, name, type, notnull, dflt_value, pk)

    Args:
        rows: Lista de tuplas de PRAGMA table_info

    Returns:
        list[SqlitePragmaResult]: Resultados decodificados
    """
    return [normalized for row in rows if (normalized := _normalize_pragma_table_result(row)) is not None]


def _normalize_fk_row(row: Any) -> tuple[str, str, str, str, str, str, int] | None:
    """Normaliza una fila individual de PRAGMA foreign_key_list.

    Args:
        row: Tupla de 8+ elementos de PRAGMA foreign_key_list

    Returns:
        Tupla (constraint_name, column_name, ref_table, ref_column, on_delete_action, on_update_action, ordinal_position)
        o None si es inválida
    """
    if not row or len(row) < 8:
        return None

    fk_id = str(row[0]) if row[0] is not None else "0"
    seq = int(row[1]) if row[1] is not None else 0
    ref_table = str(row[2]).strip() if row[2] else ""
    column_name = str(row[3]).strip() if row[3] else ""
    ref_column = str(row[4]).strip() if row[4] else ""
    on_delete = str(row[5]).upper() if row[5] else "NO ACTION"
    on_update = str(row[6]).upper() if row[6] else "NO ACTION"

    # Constraint name synthesis: "fk_{id}_{column}"
    constraint_name = f"fk_{fk_id}_{column_name.lower()}"

    return (constraint_name, column_name, ref_table, ref_column, on_delete, on_update, seq + 1)


def decode_pragma_fk_rows(rows: list[Any]) -> list[tuple]:
    """Decodifica resultados de PRAGMA foreign_key_list a tuplas normalizadas.

    PRAGMA foreign_key_list retorna:
    (id, seq, table, from, to, on_delete, on_update, match)

    Retorna tuplas: (constraint_name, column_name, ref_table, ref_column,
                     on_delete_action, on_update_action, ordinal_position)

    Args:
        rows: Lista de tuplas de PRAGMA foreign_key_list

    Returns:
        list[tuple]: Filas normalizadas
    """
    return [normalized for row in rows if (normalized := _normalize_fk_row(row)) is not None]


def decode_pragma_index_rows(rows: list[tuple[Any, ...]]) -> dict[str, dict[str, Any]]:
    """Decodifica PRAGMA index_list + index_info a mapeo normalizado.

    PRAGMA index_list retorna: (seq, name, unique, origin, partial)
    PRAGMA index_info retorna: (seqno, cid, name)

    Args:
        rows: Lista de tuplas de PRAGMA index_list

    Returns:
        dict[str, dict[str, Any]]: Mapeo {index_name: {unique, columns}}
    """
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row or len(row) < 5:
            continue

        index_name = str(row[1]).strip() if row[1] else ""
        is_unique = int(row[2]) if row[2] is not None else 0

        if index_name:
            result[index_name] = {"unique": bool(is_unique), "columns": []}

    return result
