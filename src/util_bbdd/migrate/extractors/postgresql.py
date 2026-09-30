"""Extractor de metadatos PostgreSQL hacia IR canónico.

Consulta INFORMATION_SCHEMA y catálogos de sistema (pg_catalog) para extraer
tablas, columnas, PKs, FKs, índices y vistas. Usa duck-typing sobre el
manager (SyncDatabaseManager compatible): requiere
``execute_custom_many(sql, params) → Rows``.

Parámetros SQL: estilo ``%(name)s`` (Python DB-API 2.0 para psycopg2/psycopg3).

Detección de auto_increment: columnas SERIAL/BIGSERIAL/SMALLSERIAL aparecen
como INTEGER/BIGINT/SMALLINT con COLUMN_DEFAULT = ``nextval('...')``
en INFORMATION_SCHEMA. Se detecta comprobando que COLUMN_DEFAULT comienza
con ``nextval(`` (case-insensitive).

Comentarios de columna (pg_description): omitidos en v1.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ...metadata.postgresql.routines import fetch_routines_sql as fetch_pg_routines_sql
from ...metadata.postgresql.tables import (
    fetch_columns_for_schema_sql,
    fetch_fk_for_schema_sql,
    fetch_indexes_for_schema_sql,
    fetch_pk_for_schema_sql,
    fetch_tables_for_extract_sql as fetch_tables_sql,
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
from ._schema_rows import ObjectRows, group_by_object


def _parse_raw_column(row: Any) -> dict[str, Any] | None:
    """Parsea una fila de INFORMATION_SCHEMA.COLUMNS PostgreSQL (8 elementos).

    Columnas esperadas (en orden):
        0: COLUMN_NAME
        1: DATA_TYPE              (lowercase multi-palabra, ej. 'character varying')
        2: CHARACTER_MAXIMUM_LENGTH  (None para text, json, bytea, etc.)
        3: NUMERIC_PRECISION
        4: NUMERIC_SCALE
        5: IS_NULLABLE               ('YES'/'NO')
        6: COLUMN_DEFAULT            (ej. "nextval('seq'::regclass)" para SERIAL)
        7: ORDINAL_POSITION

    Nota: DATA_TYPE se normaliza a UPPERCASE para consistencia con otros extractores.
    auto_increment se detecta cuando COLUMN_DEFAULT comienza con 'nextval('.
    char_length=None indica tipo sin límite explícito (ej. TEXT, JSON).
    """
    if not isinstance(row, (tuple, list)) or len(row) < 8:
        return None

    # Normalizar a UPPERCASE: 'character varying' → 'CHARACTER VARYING'
    data_type = str(row[1]).strip().upper() if row[1] else "CHARACTER VARYING"

    try:
        char_length = int(row[2]) if row[2] is not None else None
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

    default_raw = str(row[6]).strip() if row[6] is not None else None
    # SERIAL/BIGSERIAL/SMALLSERIAL → COLUMN_DEFAULT = "nextval('schema.seq'::regclass)"
    auto_increment = bool(default_raw and default_raw.lower().startswith("nextval("))

    return {
        "name": str(row[0]).strip() if row[0] else "",
        "data_type": data_type,
        "char_length": char_length,
        "precision": precision,
        "scale": scale,
        "nullable": str(row[5]).strip().upper() == "YES" if row[5] else True,
        "default": default_raw,
        "auto_increment": auto_increment,
        "comment": str(row[8]).strip() if len(row) > 8 and row[8] else "",  # col_description (D3)
        "ordinal": int(row[7]) if row[7] is not None else 0,
    }


class PostgreSQLSchemaExtractor:
    """Extrae el esquema PostgreSQL hacia CanonicalTable usando INFORMATION_SCHEMA.

    Usa duck-typing sobre el manager (SyncDatabaseManager compatible):
    requiere ``execute_custom_many(sql, params) → Rows``.

    Los parámetros SQL siguen el estilo ``%(name)s`` (psycopg2/psycopg3).

    El parámetro ``schema`` corresponde a TABLE_SCHEMA en PostgreSQL
    (ej. ``'public'``). Para filtrar por base de datos, asegurarse de que
    la conexión ya apunta a la BD correcta.

    Índices no-PK: extraídos via ``pg_catalog.pg_index`` con
    ``generate_subscripts`` para preservar el orden de columnas en índices
    compuestos (PG 8.4+).
    """

    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def _query(self, sql: str, params: dict[str, Any]) -> list[Any]:
        return list(self._manager.execute_custom_many(sql, params))

    def extract(self, schema: str) -> list[CanonicalTable]:
        """Extrae todas las tablas (BASE TABLE) del schema PostgreSQL como IR canónico."""
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
        """Extrae todas las vistas del schema PostgreSQL como IR canónico.

        El campo ``query`` de cada ``CanonicalView`` contiene VIEW_DEFINITION
        de INFORMATION_SCHEMA.VIEWS.
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
            definition = str(row[1]).strip() if row[1] else ""

            columns = [str(r[0]).strip() for r in columns_by_view.for_object(view_name) if r and r[0]]
            views.append(
                CanonicalView(
                    name=view_name,
                    original_name=view_name,
                    schema=schema,
                    query=definition,
                    columns=columns,
                    comment=str(row[2]).strip() if len(row) > 2 and row[2] else "",  # E2 (0.22.0)
                    warnings=[],
                )
            )

        return views

    def extract_routines(self, schema: str) -> list[CanonicalRoutine]:
        """Extrae todas las rutinas del schema PostgreSQL como IR canónico."""
        rows = self._query(fetch_pg_routines_sql(schema), {"schema": schema})
        return [r for row in rows if (r := self._parse_routine_row(row, schema)) is not None]

    def _parse_routine_row(self, row: Any, schema: str) -> CanonicalRoutine | None:
        """Parsea una fila de pg_proc a CanonicalRoutine."""
        if not row or len(row) < 4:
            return None
        routine_name = str(row[0]).strip() if row[0] else ""
        routine_type = str(row[1]).strip().upper() if row[1] else ""
        if routine_type not in ("FUNCTION", "PROCEDURE"):
            return None
        body = str(row[3]).strip() if row[3] else ""
        return_type = str(row[4]).strip() if len(row) > 4 and row[4] else ""
        warnings: list[MigrationWarning] = []
        if not body:
            warnings.append(
                MigrationWarning(
                    table=routine_name,
                    column=None,
                    category="ROUTINE",
                    target_type="(no body)",
                    message=f"Body de '{routine_name}' no disponible; emitir stub.",
                    severity="WARNING",
                )
            )
        return CanonicalRoutine(
            name=routine_name,
            original_name=routine_name,
            schema=schema,
            routine_type=routine_type,
            body=body,
            return_type=return_type,
            comment="",
            warnings=warnings,
        )

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
                    is_external=entry["ref_schema"].lower() != schema.lower(),
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
    "PostgreSQLSchemaExtractor",
]
