"""Extractor de metadatos Oracle hacia IR canónico.

Lee filas RAW para preservar data_length, data_precision y data_scale
que decode_oracle_column_rows descarta pero son necesarios para el mapeo de tipos.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ...metadata.oracle.constraints import OracleConstraintDefaults
from ...metadata.oracle.indexes import decode_oracle_index_rows
from ...metadata.oracle.tables import (
    fetch_columns_sql,
    fetch_fk_constraint_sql,
    fetch_indexes_sql,
    fetch_pk_constraint_sql,
    fetch_tables_sql,
    fetch_view_columns_sql,
    fetch_views_sql,
)
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
)


def _parse_raw_column(row: Any) -> dict[str, Any] | None:
    """Parsea una fila cruda de Oracle (9 elementos) preservando precision/scale."""
    if not isinstance(row, (tuple, list)) or len(row) < 9:
        return None

    data_type = str(row[1]).strip().upper() if row[1] else "VARCHAR2"

    try:
        data_length = int(row[5]) if row[5] is not None else None
    except (ValueError, TypeError):
        data_length = None

    try:
        precision = int(row[6]) if row[6] is not None else None
    except (ValueError, TypeError):
        precision = None

    try:
        scale = int(row[7]) if row[7] is not None else None
    except (ValueError, TypeError):
        scale = None

    default_raw = str(row[4]).strip() if row[4] else None

    return {
        "name": str(row[0]).strip() if row[0] else "",
        "data_type": data_type,
        "nullable": str(row[2]).strip().upper() == "YES" if row[2] else True,
        "ordinal": int(row[3]) if row[3] is not None else 0,
        "default": default_raw,
        "data_length": data_length,
        "precision": precision,
        "scale": scale,
        "comment": str(row[8]).strip() if row[8] else "",
    }


class OracleSchemaExtractor:
    """Extrae el esquema Oracle hacia CanonicalTable usando queries RAW.

    Usa duck-typing sobre el manager (SyncDatabaseManager compatible):
    requiere execute_custom_many(sql: str, params: dict) → Rows.
    """

    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def _query(self, sql: str, params: dict[str, Any]) -> list[Any]:
        return list(self._manager.execute_custom_many(sql, params))

    def extract(self, schema: str) -> list[CanonicalTable]:
        """Extrae todas las tablas del schema Oracle como IR canónico."""
        table_rows = self._query(fetch_tables_sql(), {"owner": schema})
        tables: list[CanonicalTable] = []

        for t_row in table_rows:
            if not t_row:
                continue
            table_name = str(t_row[0]).strip()
            table_comment = str(t_row[2]).strip() if len(t_row) > 2 and t_row[2] else ""

            columns = self._extract_columns(schema, table_name)
            pk_cols = self._extract_pk(schema, table_name)
            fk_list = self._extract_fks(schema, table_name)
            idx_list = self._extract_indexes(schema, table_name)

            # Marcar columnas PK
            pk_set = {c.upper() for c in pk_cols}
            for col in columns:
                if col.name.upper() in pk_set:
                    col.is_primary_key = True

            tables.append(
                CanonicalTable(
                    name=table_name,
                    original_name=table_name,
                    schema=schema,
                    columns=columns,
                    primary_key=pk_cols,
                    indexes=idx_list,
                    foreign_keys=fk_list,
                    comment=table_comment,
                    warnings=[],
                )
            )

        return tables

    def extract_views(self, schema: str) -> list[CanonicalView]:
        """Extrae todas las vistas del schema Oracle como IR canónico.

        Usa ``ALL_VIEWS.text`` (tipo LONG) que los drivers cx_Oracle y
        python-oracledb devuelven como ``str`` completo. Para Oracle < 12.2
        el comportamiento depende de la configuración del driver.
        """
        rows = self._query(fetch_views_sql(), {"owner": schema})
        views: list[CanonicalView] = []

        for row in rows:
            if not row:
                continue
            view_name = str(row[0]).strip()
            text = str(row[1]).strip() if row[1] else ""
            comment = str(row[2]).strip() if len(row) > 2 and row[2] else ""

            columns = self._extract_view_columns(schema, view_name)
            views.append(
                CanonicalView(
                    name=view_name,
                    original_name=view_name,
                    schema=schema,
                    query=text,
                    columns=columns,
                    comment=comment,
                    warnings=[],
                )
            )

        return views

    def _extract_view_columns(self, schema: str, view_name: str) -> list[str]:
        rows = self._query(fetch_view_columns_sql(), {"owner": schema, "view_name": view_name})
        return [str(r[0]).strip() for r in rows if r and r[0]]

    def _extract_columns(self, schema: str, table: str) -> list[CanonicalColumn]:
        rows = self._query(fetch_columns_sql(), {"owner": schema, "table_name": table})
        columns: list[CanonicalColumn] = []

        for row in rows:
            parsed = _parse_raw_column(row)
            if parsed is None:
                continue

            columns.append(
                CanonicalColumn(
                    name=parsed["name"],
                    original_name=parsed["name"],
                    oracle_type=parsed["data_type"],
                    target_type="",  # el transformer lo rellena
                    nullable=parsed["nullable"],
                    default=parsed["default"],
                    comment=parsed["comment"],
                    ordinal=parsed["ordinal"],
                    char_length=parsed["data_length"],
                    precision=parsed["precision"],
                    scale=parsed["scale"],
                )
            )

        return columns

    def _extract_pk(self, schema: str, table: str) -> list[str]:
        rows = self._query(fetch_pk_constraint_sql(), {"owner": schema, "table_name": table})
        decoded = OracleConstraintDefaults.decode_pk_rows(rows)
        # Ordenar por ordinal_position (índice 2)
        decoded_sorted = sorted(decoded, key=lambda r: r[2])
        return [str(r[1]).strip() for r in decoded_sorted if r[1]]

    def _extract_fks(self, schema: str, table: str) -> list[CanonicalFK]:
        rows = self._query(fetch_fk_constraint_sql(), {"owner": schema, "table_name": table})
        decoded = OracleConstraintDefaults.decode_fk_rows(rows)

        # Agrupar por constraint_name (puede haber FK multi-columna)
        fk_map: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "name": "",
                "columns": [],
                "ref_owner": "",
                "ref_table": "",
                "ref_columns": [],
                "on_delete": "NO ACTION",
                "on_update": "NO ACTION",
            }
        )

        for r in sorted(decoded, key=lambda x: x[7]):  # ordinal_position
            fk_name = str(r[0]).strip()
            entry = fk_map[fk_name]
            entry["name"] = fk_name
            entry["columns"].append(str(r[1]).strip())
            entry["ref_owner"] = str(r[2]).strip()
            entry["ref_table"] = str(r[3]).strip()
            entry["ref_columns"].append(str(r[4]).strip())
            entry["on_delete"] = str(r[5]).strip() if r[5] else "NO ACTION"
            entry["on_update"] = str(r[6]).strip() if r[6] else "NO ACTION"

        result: list[CanonicalFK] = []
        for fk_name, entry in fk_map.items():
            result.append(
                CanonicalFK(
                    name=fk_name,
                    original_name=fk_name,
                    columns=entry["columns"],
                    ref_table=entry["ref_table"],
                    ref_columns=entry["ref_columns"],
                    on_delete=entry["on_delete"],
                    on_update=entry["on_update"],
                    is_external=entry["ref_owner"].upper() != schema.upper(),
                )
            )

        return result

    def _extract_indexes(self, schema: str, table: str) -> list[CanonicalIndex]:
        rows = self._query(fetch_indexes_sql(), {"owner": schema, "table_name": table})
        decoded = decode_oracle_index_rows(rows)

        # Agrupar por index_name
        idx_map: dict[str, dict[str, Any]] = defaultdict(lambda: {"name": "", "columns": [], "unique": False})

        for r in sorted(decoded, key=lambda x: x[4]):  # ordinal_position
            idx_name = str(r[0]).strip()
            entry = idx_map[idx_name]
            entry["name"] = idx_name
            entry["columns"].append(str(r[1]).strip())
            entry["unique"] = str(r[3]).strip().upper() == "UNIQUE"

        result: list[CanonicalIndex] = []
        for idx_name, entry in idx_map.items():
            result.append(
                CanonicalIndex(
                    name=idx_name,
                    original_name=idx_name,
                    columns=entry["columns"],
                    unique=entry["unique"],
                )
            )

        return result


__all__: list[str] = [
    "OracleSchemaExtractor",
]
