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

from ...metadata.sqlserver._adapter_helpers import (
    build_sqlserver_routine_body_query,
    build_sqlserver_routines_query,
)
from ...metadata.sqlserver.tables import (
    fetch_columns_sql,
    fetch_fk_sql,
    fetch_indexes_sql,
    fetch_pk_sql,
    fetch_tables_sql,
    fetch_view_columns_sql,
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
        table_rows = self._query(fetch_tables_sql(), {"schema": schema})
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
        rows = self._query(fetch_views_sql(), {"schema": schema})
        views: list[CanonicalView] = []

        for row in rows:
            if not row:
                continue
            view_name = str(row[0]).strip()
            definition = str(row[1]).strip() if row[1] else ""

            view_warnings: list[MigrationWarning] = []
            # VIEW_DEFINITION en INFORMATION_SCHEMA.VIEWS está truncada a 4000 chars
            # en SQL Server < 2019. Si coincide exactamente con ese límite, posible truncación.
            if len(definition) == 4000:
                view_warnings.append(
                    MigrationWarning(
                        table=view_name,
                        column=None,
                        oracle_type="VIEW_DEFINITION",
                        target_type="(truncada)",
                        message=(
                            f"Vista '{view_name}': VIEW_DEFINITION tiene exactamente 4000 chars; "
                            "posible truncación en SQL Server < 2019. "
                            "Verificar con sys.sql_modules.definition."
                        ),
                        severity="WARNING",
                    )
                )

            columns = self._extract_view_columns(schema, view_name)
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

    def _extract_view_columns(self, schema: str, view_name: str) -> list[str]:
        rows = self._query(fetch_view_columns_sql(), {"schema": schema, "view_name": view_name})
        return [str(r[0]).strip() for r in rows if r and r[0]]

    def extract_routines(self, schema: str) -> list[CanonicalRoutine]:
        """Extrae todas las rutinas del schema SQL Server como IR canónico.

        Usa ``sys.procedures`` para el inventario y ``sys.sql_modules``
        para el cuerpo DDL completo de cada rutina.

        Nota: ``sys.procedures`` no incluye funciones escalares/table-valued
        almacenadas en ``sys.objects`` con type 'FN'/'TF'. Estas quedan fuera
        del inventario v1 por limitación del helper existente.
        """
        schema_name = schema or "dbo"
        raw_rows = self._query(build_sqlserver_routines_query(), {"schema_name": schema_name})
        routines: list[CanonicalRoutine] = []

        for row in raw_rows:
            if not row or len(row) < 2:
                continue
            routine_name = str(row[0]).strip()
            routine_type = str(row[1]).strip()  # "PROCEDURE" | "FUNCTION"
            body_rows = self._query(
                build_sqlserver_routine_body_query(),
                {"schema_name": schema_name, "routine_name": routine_name},
            )
            body = str(body_rows[0][0]).strip() if body_rows and body_rows[0] and body_rows[0][0] else ""

            warnings: list[MigrationWarning] = []
            if not body:
                warnings.append(
                    MigrationWarning(
                        table=routine_name,
                        column=None,
                        oracle_type=routine_type,
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

    def _extract_columns(self, schema: str, table: str) -> list[CanonicalColumn]:
        rows = self._query(fetch_columns_sql(), {"schema": schema, "table_name": table})
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
        rows = self._query(fetch_pk_sql(), {"schema": schema, "table_name": table})
        return [str(r[0]).strip() for r in rows if r and r[0]]

    def _extract_fks(self, schema: str, table: str) -> list[CanonicalFK]:
        rows = self._query(fetch_fk_sql(), {"schema": schema, "table_name": table})

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
        rows = self._query(fetch_indexes_sql(), {"schema": schema, "table_name": table})

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
