"""Extractor de metadatos SQL Server hacia IR canónico.

Consulta INFORMATION_SCHEMA y vistas de sistema (sys.*) para extraer
tablas, columnas, PKs, FKs, índices y vistas. Usa duck-typing sobre el
manager (SyncDatabaseManager compatible): requiere
``execute_custom_many(sql, params) → Rows``.

Parámetros SQL: estilo ``%(name)s`` (Python DB-API 2.0 para pymssql).
Para pyodbc usar un manager wrapper que convierta ``%(name)s`` a ``?``.

Detección de IDENTITY: usa ``COLUMNPROPERTY(OBJECT_ID(...), col, 'IsIdentity')``
(compatible con SQL Server 2008+).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ...metadata.sqlserver._adapter_helpers import build_sqlserver_routines_query
from ...metadata.sqlserver.tables import (
    fetch_columns_for_schema_sql,
    fetch_fk_for_schema_sql,
    fetch_indexes_for_schema_sql,
    fetch_pk_for_schema_sql,
    fetch_routine_bodies_for_schema_sql,
    fetch_tables_sql,
    fetch_views_sql,
)
from .._compat.sql_view_header import split_create_view_header
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalRoutine,
    CanonicalTable,
    CanonicalView,
    MigrationWarning,
)
from ._schema_rows import ObjectRows, group_by_object


def _parse_raw_column(row: Any) -> dict[str, Any] | None:
    """Parsea una fila de INFORMATION_SCHEMA.COLUMNS SQL Server (9 elementos).

    Columnas esperadas (en orden):
        0: COLUMN_NAME
        1: DATA_TYPE
        2: CHARACTER_MAXIMUM_LENGTH  (-1 indica MAX)
        3: NUMERIC_PRECISION
        4: NUMERIC_SCALE
        5: IS_NULLABLE               ('YES'/'NO')
        6: COLUMN_DEFAULT
        7: IS_IDENTITY               (1/0/None)
        8: ORDINAL_POSITION
    """
    if not isinstance(row, (tuple, list)) or len(row) < 9:
        return None

    data_type = str(row[1]).strip().upper() if row[1] else "VARCHAR"

    try:
        # -1 es el sentinel de SQL Server para MAX; se preserva tal cual
        char_length_raw = int(row[2]) if row[2] is not None else None
        char_length = char_length_raw  # puede ser -1 (MAX)
    except (ValueError, TypeError):
        char_length = None

    try:
        precision = int(row[3]) if row[3] is not None else None
    except (ValueError, TypeError):
        precision = None

    try:
        scale = int(row[4]) if row[4] is not None else None
    except (ValueError, TypeError):
        scale = None

    try:
        is_identity = bool(int(row[7])) if row[7] is not None else False
    except (ValueError, TypeError):
        is_identity = False

    default_raw = str(row[6]).strip() if row[6] is not None else None

    return {
        "name": str(row[0]).strip() if row[0] else "",
        "data_type": data_type,
        "char_length": char_length,
        "precision": precision,
        "scale": scale,
        "nullable": str(row[5]).strip().upper() == "YES" if row[5] else True,
        "default": default_raw,
        "auto_increment": is_identity,
        "comment": str(row[9]).strip() if len(row) > 9 and row[9] else "",  # MS_Description (D3)
        "ordinal": int(row[8]) if row[8] is not None else 0,
    }


class SQLServerSchemaExtractor:
    """Extrae el esquema SQL Server hacia CanonicalTable usando INFORMATION_SCHEMA.

    Usa duck-typing sobre el manager (SyncDatabaseManager compatible):
    requiere ``execute_custom_many(sql, params) → Rows``.

    Los parámetros SQL siguen el estilo ``%(name)s`` (Python DB-API 2.0 para
    pymssql). Para pyodbc se necesita un manager wrapper que adapte el estilo.

    El parámetro ``schema`` corresponde a TABLE_SCHEMA en SQL Server (ej. ``'dbo'``).
    Para filtrar por base de datos, asegurarse de que la conexión ya apunta
    a la BD correcta (USE database).
    """

    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def _query(self, sql: str, params: dict[str, Any]) -> list[Any]:
        return list(self._manager.execute_custom_many(sql, params))

    def extract(self, schema: str) -> list[CanonicalTable]:
        """Extrae todas las tablas (BASE TABLE) del schema SQL Server como IR canónico."""
        params = {"schema": schema}
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

            columns = self._extract_columns(columns_by_table.for_object(table_name))
            pk_cols = self._extract_pk(pks_by_table.for_object(table_name))
            fk_list = self._extract_fks(schema, fks_by_table.for_object(table_name))
            idx_list = self._extract_indexes(indexes_by_table.for_object(table_name))

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
                    comment=str(t_row[1]).strip() if len(t_row) > 1 and t_row[1] else "",  # D3
                    warnings=[],
                )
            )

        return tables

    def extract_views(self, schema: str) -> list[CanonicalView]:
        """Extrae todas las vistas del schema SQL Server como IR canónico.

        El campo ``query`` de cada ``CanonicalView`` contiene la definición completa (``OBJECT_DEFINITION``, sin el
        truncado a 4000 caracteres de ``INFORMATION_SCHEMA.VIEWS``) sin su cabecera ``CREATE VIEW ... AS`` (H7).
        """
        rows = self._query(fetch_views_sql(), {"schema": schema})
        columns_by_view = (
            group_by_object(self._query(fetch_columns_for_schema_sql(), {"schema": schema})) if rows else ObjectRows()
        )
        views: list[CanonicalView] = []

        for row in rows:
            if not row:
                continue
            view_name = str(row[0]).strip()
            split = split_create_view_header(str(row[1])) if row[1] else None
            definition = split.query if split else ""

            view_warnings: list[MigrationWarning] = []
            if split is None:
                view_warnings.append(
                    MigrationWarning(
                        table=view_name,
                        column=None,
                        category="VIEW",
                        target_type="(no disponible)",
                        message=(
                            f"Vista '{view_name}': definición no disponible (WITH ENCRYPTION o sin permiso "
                            "VIEW DEFINITION); no se emite."
                        ),
                        severity="WARNING",
                    )
                )
            elif split.column_list:
                view_warnings.append(
                    MigrationWarning(
                        table=view_name,
                        column=None,
                        category="VIEW",
                        target_type="(columnas de la cabecera)",
                        message=(
                            f"Vista '{view_name}': la cabecera declara las columnas ({split.column_list}); la vista "
                            "migrada toma los nombres del SELECT. Revisar los alias."
                        ),
                        severity="WARNING",
                    )
                )

            columns = [str(r[0]).strip() for r in columns_by_view.for_object(view_name) if r and r[0]]
            views.append(
                CanonicalView(
                    name=view_name,
                    original_name=view_name,
                    schema=schema,
                    query=definition,
                    columns=columns,
                    comment="",
                    warnings=view_warnings,
                )
            )

        return views

    def extract_routines(self, schema: str) -> list[CanonicalRoutine]:
        """Extrae todas las rutinas del schema SQL Server como IR canónico.

        Usa ``sys.objects`` para el inventario (procedures + funciones escalares
        e inline/multi-statement table-valued) y ``sys.sql_modules`` para el
        cuerpo DDL completo de cada rutina.
        """
        schema_name = schema or "dbo"
        raw_rows = self._query(build_sqlserver_routines_query(), {"schema_name": schema_name})
        # D1: el código de todas las rutinas en una consulta (antes una por rutina)
        bodies = (
            {
                str(row[0]).strip(): str(row[1]).strip()
                for row in self._query(fetch_routine_bodies_for_schema_sql(), {"schema_name": schema_name})
                if row and len(row) > 1 and row[1]
            }
            if raw_rows
            else {}
        )
        routines: list[CanonicalRoutine] = []

        for row in raw_rows:
            if not row or len(row) < 2:
                continue
            routine_name = str(row[0]).strip()
            routine_type = str(row[1]).strip()  # "PROCEDURE" | "FUNCTION"
            body = bodies.get(routine_name, "")

            warnings: list[MigrationWarning] = []
            if not body:
                warnings.append(
                    MigrationWarning(
                        table=routine_name,
                        column=None,
                        category="ROUTINE",
                        target_type="(no body)",
                        message=f"Body de '{routine_name}' no disponible en sys.sql_modules; emitir stub.",
                        severity="WARNING",
                    )
                )

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
                )
            )

        return routines

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
                    source_type=parsed["data_type"],
                    target_type="",  # el transformer lo rellena
                    nullable=parsed["nullable"],
                    default=parsed["default"],
                    comment=parsed["comment"],
                    ordinal=parsed["ordinal"],
                    char_length=parsed["char_length"],
                    precision=parsed["precision"],
                    scale=parsed["scale"],
                    auto_increment=parsed["auto_increment"],
                )
            )

        return columns

    def _extract_pk(self, rows: list[tuple[Any, ...]]) -> list[str]:
        return [str(r[0]).strip() for r in rows if r and r[0]]

    def _extract_fks(self, schema: str, rows: list[tuple[Any, ...]]) -> list[CanonicalFK]:
        fk_map: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "name": "",
                "columns": [],
                "ref_schema": "",
                "ref_table": "",
                "ref_columns": [],
                "on_delete": "NO ACTION",
                "on_update": "NO ACTION",
            }
        )

        for r in sorted(rows, key=lambda x: (str(x[0]), int(x[5]) if x[5] is not None else 0)):
            fk_name = str(r[0]).strip()
            entry = fk_map[fk_name]
            entry["name"] = fk_name
            entry["columns"].append(str(r[1]).strip())
            entry["ref_schema"] = str(r[2]).strip() if r[2] else schema
            entry["ref_table"] = str(r[3]).strip()
            entry["ref_columns"].append(str(r[4]).strip())
            entry["on_delete"] = str(r[6]).strip() if r[6] else "NO ACTION"
            entry["on_update"] = str(r[7]).strip() if r[7] else "NO ACTION"

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
                    is_external=entry["ref_schema"].upper() != schema.upper(),
                )
            )

        return result

    def _extract_indexes(self, rows: list[tuple[Any, ...]]) -> list[CanonicalIndex]:
        idx_map: dict[str, dict[str, Any]] = defaultdict(lambda: {"name": "", "columns": [], "unique": False})

        for r in sorted(rows, key=lambda x: (str(x[0]), int(x[3]) if x[3] is not None else 0)):
            idx_name = str(r[0]).strip()
            entry = idx_map[idx_name]
            entry["name"] = idx_name
            entry["columns"].append(str(r[1]).strip())
            entry["unique"] = bool(r[2])

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
    "SQLServerSchemaExtractor",
]
