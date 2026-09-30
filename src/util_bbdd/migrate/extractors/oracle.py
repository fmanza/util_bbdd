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
    fetch_columns_for_schema_sql,
    fetch_fk_for_schema_sql,
    fetch_indexes_for_schema_sql,
    fetch_pk_for_schema_sql,
    fetch_routine_bodies_for_schema_sql,
    fetch_routines_sql,
    fetch_tables_sql,
    fetch_view_columns_for_schema_sql,
    fetch_views_sql,
)
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalRoutine,
    CanonicalTable,
    CanonicalView,
    MigrationWarning,
)
from ._schema_rows import group_by_object


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
        self._bodies: dict[tuple[str, str], str] = {}

    def _query(self, sql: str, params: dict[str, Any]) -> list[Any]:
        return list(self._manager.execute_custom_many(sql, params))

    def extract(self, schema: str) -> list[CanonicalTable]:
        """Extrae todas las tablas del schema Oracle como IR canónico."""
        params = {"owner": schema}
        table_rows = self._query(fetch_tables_sql(), params)
        # D1: una consulta por schema y tipo de objeto, agrupada por tabla (antes 4 consultas por tabla)
        columns_by_table = group_by_object(self._query(fetch_columns_for_schema_sql(), params))
        pks_by_table = group_by_object(self._query(fetch_pk_for_schema_sql(), params))
        fks_by_table = group_by_object(self._query(fetch_fk_for_schema_sql(), params))
        indexes_by_table = group_by_object(self._query(fetch_indexes_for_schema_sql(), params))
        tables: list[CanonicalTable] = []

        for t_row in table_rows:
            if not t_row:
                continue
            table_name = str(t_row[0]).strip()
            table_comment = str(t_row[2]).strip() if len(t_row) > 2 and t_row[2] else ""

            columns = self._extract_columns(columns_by_table.get(table_name, []))
            pk_cols = self._extract_pk(pks_by_table.get(table_name, []))
            fk_list = self._extract_fks(schema, fks_by_table.get(table_name, []))
            idx_list = self._extract_indexes(indexes_by_table.get(table_name, []))

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
        columns_by_view = (
            group_by_object(self._query(fetch_view_columns_for_schema_sql(), {"owner": schema})) if rows else {}
        )
        views: list[CanonicalView] = []

        for row in rows:
            if not row:
                continue
            view_name = str(row[0]).strip()
            text = str(row[1]).strip() if row[1] else ""
            comment = str(row[2]).strip() if len(row) > 2 and row[2] else ""

            columns = [str(r[0]).strip() for r in columns_by_view.get(view_name, []) if r and r[0]]
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

    def extract_routines(self, schema: str) -> list[CanonicalRoutine]:
        """Extrae todas las rutinas del schema Oracle como IR canónico.

        Los miembros de PACKAGE (is_package_member=True) se incluyen como
        inventario con body="" y no generan DDL de emisión.
        El body se obtiene concatenando las líneas de ALL_SOURCE.
        """
        rows = self._query(fetch_routines_sql(), {"owner": schema})
        self._bodies = self._routine_bodies(schema) if rows else {}
        routines: list[CanonicalRoutine] = []

        for row in rows:
            if not row or len(row) < 3:
                continue
            routine_name = str(row[0]).strip() if row[0] else ""
            raw_type = str(row[1]).strip().upper() if row[1] else ""

            # Tipos soportados directamente
            if raw_type in ("PROCEDURE", "FUNCTION"):
                routine_type = raw_type
                is_pkg_member = False
                pkg_name: str | None = None
                body = self._fetch_routine_body(schema, routine_name, routine_type)
                warnings: list[MigrationWarning] = []
                if not body:
                    warnings.append(
                        MigrationWarning(
                            table=routine_name,
                            column=None,
                            oracle_type=routine_type,
                            target_type="(no body)",
                            message=f"Body de '{routine_name}' no disponible en ALL_SOURCE; emitir stub.",
                            severity="WARNING",
                        )
                    )
            elif raw_type in ("PACKAGE", "PACKAGE BODY"):
                routine_type = "PROCEDURE"
                is_pkg_member = True
                pkg_name = routine_name
                # PACKAGE BODY: obtener fuente completo desde ALL_SOURCE para revisión manual.
                # PACKAGE spec: sin implementación, body vacío.
                body = (
                    self._fetch_routine_body(schema, routine_name, "PACKAGE BODY") if raw_type == "PACKAGE BODY" else ""
                )
                warnings = [
                    MigrationWarning(
                        table=routine_name,
                        column=None,
                        oracle_type=raw_type,
                        target_type="(package member)",
                        message=(
                            f"'{routine_name}' es un ORACLE {raw_type}; "
                            "no tiene equivalente directo — migración manual requerida."
                        ),
                        severity="WARNING",
                    )
                ]
            else:
                continue

            routines.append(
                CanonicalRoutine(
                    name=routine_name,
                    original_name=routine_name,
                    schema=schema,
                    routine_type=routine_type,
                    body=body,
                    return_type="",
                    comment="",
                    warnings=warnings,
                    is_package_member=is_pkg_member,
                    package_name=pkg_name,
                )
            )

        return routines

    def _routine_bodies(self, schema: str) -> dict[tuple[str, str], str]:
        """Código de todas las rutinas del owner con una consulta a ALL_SOURCE: ``{(nombre, tipo): texto}`` (D1)."""
        lines: dict[tuple[str, str], list[str]] = defaultdict(list)
        for row in self._query(fetch_routine_bodies_for_schema_sql(), {"owner": schema}):
            if row and len(row) > 3 and row[3]:
                lines[(str(row[0]).strip(), str(row[1]).strip().upper())].append(str(row[3]))
        return {key: "".join(parts).strip() for key, parts in lines.items()}

    def _fetch_routine_body(self, schema: str, routine_name: str, routine_type: str) -> str:
        """Body verbatim de una rutina Oracle (de las ya leídas por :meth:`_routine_bodies`)."""
        return self._bodies.get((routine_name, routine_type.upper()), "")

    def _extract_columns(self, rows: list[tuple[Any, ...]]) -> list[CanonicalColumn]:
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

    def _extract_pk(self, rows: list[tuple[Any, ...]]) -> list[str]:
        decoded = OracleConstraintDefaults.decode_pk_rows(rows)
        # Ordenar por ordinal_position (índice 2)
        decoded_sorted = sorted(decoded, key=lambda r: r[2])
        return [str(r[1]).strip() for r in decoded_sorted if r[1]]

    def _extract_fks(self, schema: str, rows: list[tuple[Any, ...]]) -> list[CanonicalFK]:
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

    def _extract_indexes(self, rows: list[tuple[Any, ...]]) -> list[CanonicalIndex]:
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
