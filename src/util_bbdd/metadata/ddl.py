"""DDL de tablas, vistas y routines (E2 de ADR-003).

Vistas, routines y tablas de MySQL/MariaDB salen del modelo neutro del snapshot. Las tablas del resto de motores se
leen tabla a tabla con el SQL de ``_NATIVE_TABLE_DDL_SQL`` (``DBMS_METADATA`` en Oracle, el ``CREATE`` guardado en
SQLite, reconstrucción en el catálogo en PostgreSQL, SQL Server y HSQLDB): el snapshot no guarda lo necesario para
reproducirlo igual (semilla de ``IDENTITY``, ``CLUSTERED``/``DESC`` de la PK, ``quote_ident``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .mariadb.common import format_mariadb_default, quote_mariadb_identifier
from .model import ColumnMeta, PrimaryKeyMeta, RoutineMeta, ViewMeta


def view_ddl(view: ViewMeta | None, name: str = "") -> str:
    """``CREATE VIEW … AS`` + la definición que guarda el motor (o la sentencia completa si ya la guarda así).

    PostgreSQL, Oracle y MySQL/MariaDB guardan el ``SELECT``; SQL Server y SQLite, la sentencia ``CREATE VIEW``.
    ``""`` si la vista no existe o su definición no está disponible (permisos, ``WITH ENCRYPTION``).
    """
    definition = (view.definition or "").strip() if view else ""
    if not definition or definition[:6].upper() == "CREATE":
        return definition
    return f"CREATE VIEW {view.name if view else name} AS\n{definition}"


def routine_ddl(routine: RoutineMeta | None) -> str:
    """Definición completa de una routine (``CREATE …``); ``""`` si no está disponible."""
    return (routine.definition or "").strip() if routine else ""


def mysql_table_ddl(table: str, columns: Sequence[ColumnMeta], primary_key: PrimaryKeyMeta | None) -> str:
    """``CREATE TABLE`` de MySQL/MariaDB con columnas (tipo, nulabilidad, default, ``AUTO_INCREMENT``,
    ``ON UPDATE``) y clave primaria; ``""`` si la tabla no tiene columnas.

    No incluye índices, claves foráneas ni opciones de tabla: para el DDL completo, ``SHOW CREATE TABLE``.
    """
    if not columns:
        return ""
    definitions = [_mysql_column(column) for column in columns]
    if primary_key and primary_key.columns:
        definitions.append(f"  PRIMARY KEY ({', '.join(quote_mariadb_identifier(c) for c in primary_key.columns)})")
    body = ",\n".join(definitions)
    return f"CREATE TABLE {quote_mariadb_identifier(table)} (\n{body}\n)"


def _mysql_column(column: ColumnMeta) -> str:
    parts = [quote_mariadb_identifier(column.name), column.data_type, "NULL" if column.nullable else "NOT NULL"]
    if column.default is not None:
        parts.append(f"DEFAULT {format_mariadb_default(column.default)}")
    if column.identity:
        parts.append("auto_increment")
    if column.on_update:
        parts.append(f"on update {column.on_update}")
    return "  " + " ".join(parts)


_NATIVE_TABLE_DDL_SQL: dict[str, str] = {
    "postgresql": (
        "SELECT 'CREATE TABLE ' || quote_ident(n.nspname) || '.' || quote_ident(c.relname) || E' (\\n' || "
        "string_agg('    ' || quote_ident(a.attname) || ' ' || format_type(a.atttypid, a.atttypmod) || CASE "
        "WHEN a.attnotnull THEN ' NOT NULL' ELSE '' END || CASE WHEN ad.adbin IS NOT NULL THEN ' DEFAULT ' "
        "|| pg_get_expr(ad.adbin, ad.adrelid) ELSE '' END, E',\\n' ORDER BY a.attnum) || E'\\n);' AS ddl FROM "
        "pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_attribute a ON a.attrelid = c.oid "
        "AND a.attnum > 0 AND NOT a.attisdropped LEFT JOIN pg_attrdef ad ON ad.adrelid = a.attrelid AND "
        "ad.adnum = a.attnum WHERE n.nspname = :schema AND c.relname = :table_name AND c.relkind = 'r' GROUP BY "
        "n.nspname, c.relname"
    ),
    "oracle": "SELECT DBMS_METADATA.GET_DDL('TABLE', :table_name, :schema) AS DDL FROM DUAL",
    "sqlserver": (
        "SELECT 'CREATE TABLE [' + s.name + '].[' + t.name + '] (' + STUFF((SELECT ', [' + c.name + '] ' + "
        "UPPER(ty.name) + CASE WHEN ty.name IN ('varchar','char','varbinary','binary') THEN '(' + CASE WHEN "
        "c.max_length = -1 THEN 'MAX' ELSE CAST(c.max_length AS VARCHAR(10)) END + ')' WHEN ty.name IN "
        "('nvarchar','nchar') THEN '(' + CASE WHEN c.max_length = -1 THEN 'MAX' ELSE CAST(c.max_length / 2 "
        "AS VARCHAR(10)) END + ')' WHEN ty.name IN ('decimal','numeric') THEN '(' + CAST(c.precision AS "
        "VARCHAR(10)) + ',' + CAST(c.scale AS VARCHAR(10)) + ')' WHEN ty.name IN "
        "('datetime2','time','datetimeoffset') THEN '(' + CAST(c.scale AS VARCHAR(10)) + ')' ELSE '' END + "
        "CASE WHEN ic.seed_value IS NOT NULL THEN ' IDENTITY(' + CAST(CAST(ic.seed_value AS BIGINT) AS "
        "VARCHAR(30)) + ',' + CAST(CAST(ic.increment_value AS BIGINT) AS VARCHAR(30)) + ')' ELSE '' END + "
        "CASE WHEN dc.definition IS NOT NULL THEN ' DEFAULT ' + dc.definition ELSE '' END + CASE WHEN "
        "c.is_nullable = 1 THEN ' NULL' ELSE ' NOT NULL' END FROM sys.columns c JOIN sys.types ty ON "
        "c.user_type_id = ty.user_type_id LEFT JOIN sys.identity_columns ic ON ic.object_id = c.object_id "
        "AND ic.column_id = c.column_id LEFT JOIN sys.default_constraints dc ON dc.parent_object_id = "
        "c.object_id AND dc.parent_column_id = c.column_id WHERE c.object_id = t.object_id ORDER BY "
        "c.column_id FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, '') + ISNULL((SELECT ', "
        "CONSTRAINT [' + kc.name + '] PRIMARY KEY ' + CASE WHEN i.type = 1 THEN 'CLUSTERED' ELSE "
        "'NONCLUSTERED' END + ' (' + STUFF((SELECT ', [' + cpk.name + ']' + CASE WHEN icpk.is_descending_key "
        "= 1 THEN ' DESC' ELSE ' ASC' END FROM sys.index_columns icpk JOIN sys.columns cpk ON cpk.object_id "
        "= icpk.object_id AND cpk.column_id = icpk.column_id WHERE icpk.object_id = kc.parent_object_id AND "
        "icpk.index_id = kc.unique_index_id AND icpk.key_ordinal > 0 ORDER BY icpk.key_ordinal FOR XML "
        "PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, '') + ')' FROM sys.key_constraints kc JOIN "
        "sys.indexes i ON i.object_id = kc.parent_object_id AND i.index_id = kc.unique_index_id WHERE "
        "kc.parent_object_id = t.object_id AND kc.type = 'PK'), '') + ISNULL((SELECT STUFF((SELECT ', "
        "CONSTRAINT [' + fk.name + '] FOREIGN KEY (' + STUFF((SELECT ', [' + cp.name + ']' FROM "
        "sys.foreign_key_columns fkc2 JOIN sys.columns cp ON cp.object_id = fkc2.parent_object_id AND "
        "cp.column_id = fkc2.parent_column_id WHERE fkc2.constraint_object_id = fk.object_id ORDER BY "
        "fkc2.constraint_column_id FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, '') + ') "
        "REFERENCES [' + rs.name + '].[' + rt.name + '] (' + STUFF((SELECT ', [' + cr.name + ']' FROM "
        "sys.foreign_key_columns fkc3 JOIN sys.columns cr ON cr.object_id = fkc3.referenced_object_id AND "
        "cr.column_id = fkc3.referenced_column_id WHERE fkc3.constraint_object_id = fk.object_id ORDER BY "
        "fkc3.constraint_column_id FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, '') + ')' + "
        "CASE fk.delete_referential_action WHEN 1 THEN ' ON DELETE CASCADE' WHEN 2 THEN ' ON DELETE SET "
        "NULL' WHEN 3 THEN ' ON DELETE SET DEFAULT' ELSE '' END + CASE fk.update_referential_action WHEN 1 "
        "THEN ' ON UPDATE CASCADE' WHEN 2 THEN ' ON UPDATE SET NULL' WHEN 3 THEN ' ON UPDATE SET DEFAULT' "
        "ELSE '' END FROM sys.foreign_keys fk JOIN sys.tables rt ON rt.object_id = fk.referenced_object_id "
        "JOIN sys.schemas rs ON rs.schema_id = rt.schema_id WHERE fk.parent_object_id = t.object_id ORDER BY "
        "fk.name FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 2, '')), '') + ')' AS ddl FROM "
        "sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id WHERE s.name = :schema AND t.name = "
        ":table_name"
    ),
    "sqlite": "SELECT sql AS ddl FROM sqlite_master WHERE type='table' AND name=:table_name",
    # B-04 (v0.41.1): LISTAGG exige WITHIN GROUP (que además fija el orden de las columnas); el '' de cada CASE va como
    # VARCHAR porque un CASE con literales de distinta longitud es CHAR y rellena con espacios. Solo tablas: el DDL de
    # las vistas sale del snapshot (view_ddl), y INFORMATION_SCHEMA.VIEWS no tiene la columna TEXT.
    "hsqldb": (
        "SELECT 'CREATE TABLE ' || TABLE_NAME || ' (' || LISTAGG(COLUMN_NAME || ' ' || DATA_TYPE || "
        "CASE WHEN CHARACTER_MAXIMUM_LENGTH IS NOT NULL THEN '(' || CHARACTER_MAXIMUM_LENGTH || ')' "
        "ELSE CAST('' AS VARCHAR(1)) END || "
        "CASE WHEN IS_NULLABLE = 'NO' THEN CAST(' NOT NULL' AS VARCHAR(9)) ELSE CAST('' AS VARCHAR(1)) END || "
        "CASE WHEN COLUMN_DEFAULT IS NOT NULL THEN ' DEFAULT ' || COLUMN_DEFAULT ELSE CAST('' AS VARCHAR(1)) END, "
        "', ') WITHIN GROUP (ORDER BY ORDINAL_POSITION) || ')' FROM INFORMATION_SCHEMA.COLUMNS WHERE "
        "TABLE_SCHEMA = :schema AND TABLE_NAME = :table_name GROUP BY TABLE_NAME"
    ),
}


#: Ejecuta SQL de catálogo con ``:nombre`` (``CatalogExecutor.fetch_all``).
FetchAll = Callable[[str, Mapping[str, Any]], Sequence[Sequence[Any]]]


def native_table_ddl_sql(engine: str) -> str | None:
    """SQL que devuelve el ``CREATE TABLE`` de una tabla; ``None`` si el motor no lo tiene.

    Parámetros ``:schema`` y ``:table_name`` (``:table`` no vale como bind en Oracle: ORA-01745).
    """
    return _NATIVE_TABLE_DDL_SQL.get(engine)


def native_table_ddl(rows: Sequence[Sequence[Any]]) -> str:
    """Texto del DDL leído con :func:`native_table_ddl_sql` (``""`` si la tabla no existe)."""
    value = rows[0][0] if rows and rows[0] else None
    return "" if value is None else str(value)


__all__: list[str] = [
    "FetchAll",
    "mysql_table_ddl",
    "native_table_ddl",
    "native_table_ddl_sql",
    "routine_ddl",
    "view_ddl",
]
