"""Normalizadores de metadatos para respuestas homogéneas."""

from __future__ import annotations

from typing import Any, TypedDict

from .metadata_contracts import Row, Rows


class NormalizedTableRow(TypedDict):
    """Representación normalizada de una tabla."""

    name: str
    raw: Row


class NormalizedColumnRow(TypedDict):
    """Representación normalizada de una columna."""

    name: str
    data_type: str | None
    raw: Row


def _first_non_empty_string(values: Row) -> str:
    for value in values:
        if isinstance(value, str):
            candidate: str = value.strip()
            if candidate:
                return candidate
    return ""


def normalize_table_rows(rows: Rows) -> list[NormalizedTableRow]:
    """Convierte filas crudas de tablas en estructura homogénea."""
    normalized: list[NormalizedTableRow] = []
    for row in rows:
        normalized.append(
            {
                "name": _first_non_empty_string(row),
                "raw": row,
            }
        )
    return normalized


def normalize_column_rows(rows: Rows) -> list[NormalizedColumnRow]:
    """Convierte filas crudas de columnas en estructura homogénea."""
    normalized: list[NormalizedColumnRow] = []
    for row in rows:
        if len(row) > 1 and isinstance(row[1], str) and row[1].strip():
            column_name = row[1].strip()
        else:
            column_name = _first_non_empty_string(row)

        data_type: str | None = None
        if len(row) > 2 and isinstance(row[2], str):
            dtype = row[2].strip()
            data_type = dtype or None

        normalized.append(
            {
                "name": column_name,
                "data_type": data_type,
                "raw": row,
            }
        )
    return normalized


def normalize_rows_as_dicts(rows: Rows) -> list[dict[str, Any]]:
    """Fallback de normalización genérica para filas heterogéneas."""
    return [{"raw": row} for row in rows]
