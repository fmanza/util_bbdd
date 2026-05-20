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

from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
)

# ── SQL queries INFORMATION_SCHEMA / sys.* ────────────────────────────────────

_FETCH_TABLES_SQL = (
    "SELECT TABLE_NAME "
    "FROM INFORMATION_SCHEMA.TABLES "
    "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_TYPE = 'BASE TABLE' "
    "ORDER BY TABLE_NAME"
)

_FETCH_COLUMNS_SQL = (
    "SELECT c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH, "
    "c.NUMERIC_PRECISION, c.NUMERIC_SCALE, c.IS_NULLABLE, c.COLUMN_DEFAULT, "
    "COLUMNPROPERTY(OBJECT_ID(c.TABLE_SCHEMA + '.' + c.TABLE_NAME), c.COLUMN_NAME, 'IsIdentity') AS IS_IDENTITY, "
    "c.ORDINAL_POSITION "
    "FROM INFORMATION_SCHEMA.COLUMNS c "
    "WHERE c.TABLE_SCHEMA = %(schema)s AND c.TABLE_NAME = %(table_name)s "
    "ORDER BY c.ORDINAL_POSITION"
)

_FETCH_PK_SQL = (
    "SELECT kcu.COLUMN_NAME "
    "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
    "JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
    "  ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
    "  AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA "
    "WHERE kcu.TABLE_SCHEMA = %(schema)s AND kcu.TABLE_NAME = %(table_name)s "
    "  AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY' "
    "ORDER BY kcu.ORDINAL_POSITION"
)

_FETCH_FK_SQL = (
    "SELECT kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME, "
    "kcu2.TABLE_SCHEMA AS REF_SCHEMA, kcu2.TABLE_NAME AS REF_TABLE, "
    "kcu2.COLUMN_NAME AS REF_COLUMN, kcu.ORDINAL_POSITION, "
    "rc.DELETE_RULE, rc.UPDATE_RULE "
    "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
    "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
    "  ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME "
    "  AND kcu.TABLE_SCHEMA = rc.CONSTRAINT_SCHEMA "
    "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2 "
    "  ON kcu2.CONSTRAINT_NAME = rc.UNIQUE_CONSTRAINT_NAME "
    "  AND kcu2.TABLE_SCHEMA = rc.UNIQUE_CONSTRAINT_SCHEMA "
    "  AND kcu2.ORDINAL_POSITION = kcu.ORDINAL_POSITION "
    "WHERE kcu.TABLE_SCHEMA = %(schema)s AND kcu.TABLE_NAME = %(table_name)s "
    "ORDER BY kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
)

_FETCH_INDEXES_SQL = (
    "SELECT i.name AS INDEX_NAME, c.name AS COLUMN_NAME, i.is_unique, "
    "ic.key_ordinal AS SEQ_IN_INDEX "
    "FROM sys.indexes i "
    "JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id "
    "JOIN sys.columns c ON c.object_id = i.object_id AND c.column_id = ic.column_id "
    "JOIN sys.tables t ON t.object_id = i.object_id "
    "JOIN sys.schemas s ON s.schema_id = t.schema_id "
    "WHERE s.name = %(schema)s AND t.name = %(table_name)s "
    "  AND i.is_primary_key = 0 AND i.type > 0 "
    "ORDER BY i.name, ic.key_ordinal"
)

_FETCH_VIEWS_SQL = (
    "SELECT TABLE_NAME, VIEW_DEFINITION "
    "FROM INFORMATION_SCHEMA.VIEWS "
    "WHERE TABLE_SCHEMA = %(schema)s "
    "ORDER BY TABLE_NAME"
)

_FETCH_VIEW_COLUMNS_SQL = (
    "SELECT COLUMN_NAME "
    "FROM INFORMATION_SCHEMA.COLUMNS "
    "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(view_name)s "
    "ORDER BY ORDINAL_POSITION"
)


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
        "comment": "",  # SQL Server usa sys.extended_properties; se omite en v1
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
        table_rows = self._query(_FETCH_TABLES_SQL, {"schema": schema})
        tables: list[CanonicalTable] = []

        for t_row in table_rows:
            if not t_row:
                continue
            table_name = str(t_row[0]).strip()

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
                    comment="",  # SQL Server extended_properties omitido en v1
                    warnings=[],
                )
            )

        return tables

    def extract_views(self, schema: str) -> list[CanonicalView]:
        """Extrae todas las vistas del schema SQL Server como IR canónico.

        El campo ``query`` de cada ``CanonicalView`` contiene VIEW_DEFINITION
        de INFORMATION_SCHEMA.VIEWS (puede estar truncado a 4000 chars en versiones
        anteriores a SQL Server 2019 si la definición supera ese límite).
        """
        rows = self._query(_FETCH_VIEWS_SQL, {"schema": schema})
        views: list[CanonicalView] = []

        for row in rows:
            if not row:
                continue
            view_name = str(row[0]).strip()
            definition = str(row[1]).strip() if row[1] else ""

            columns = self._extract_view_columns(schema, view_name)
            views.append(
                CanonicalView(
                    name=view_name,
                    original_name=view_name,
                    schema=schema,
                    query=definition,
                    columns=columns,
                    comment="",
                    warnings=[],
                )
            )

        return views

    def _extract_view_columns(self, schema: str, view_name: str) -> list[str]:
        rows = self._query(_FETCH_VIEW_COLUMNS_SQL, {"schema": schema, "view_name": view_name})
        return [str(r[0]).strip() for r in rows if r and r[0]]

    def _extract_columns(self, schema: str, table: str) -> list[CanonicalColumn]:
        rows = self._query(_FETCH_COLUMNS_SQL, {"schema": schema, "table_name": table})
        columns: list[CanonicalColumn] = []

        for row in rows:
            parsed = _parse_raw_column(row)
            if parsed is None:
                continue

            columns.append(
                CanonicalColumn(
                    name=parsed["name"],
                    original_name=parsed["name"],
                    # oracle_type almacena el tipo fuente (SQL Server DATA_TYPE);
                    # el nombre del campo es histórico (primera implementación Oracle→MariaDB)
                    oracle_type=parsed["data_type"],
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

    def _extract_pk(self, schema: str, table: str) -> list[str]:
        rows = self._query(_FETCH_PK_SQL, {"schema": schema, "table_name": table})
        return [str(r[0]).strip() for r in rows if r and r[0]]

    def _extract_fks(self, schema: str, table: str) -> list[CanonicalFK]:
        rows = self._query(_FETCH_FK_SQL, {"schema": schema, "table_name": table})

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

    def _extract_indexes(self, schema: str, table: str) -> list[CanonicalIndex]:
        rows = self._query(_FETCH_INDEXES_SQL, {"schema": schema, "table_name": table})

        idx_map: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"name": "", "columns": [], "unique": False}
        )

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
