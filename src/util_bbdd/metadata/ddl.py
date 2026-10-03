"""Texto DDL a partir del modelo neutro de ``metadata/`` (vistas, routines y tablas de MySQL/MariaDB; E2 de ADR-003)."""

from __future__ import annotations

from collections.abc import Sequence

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


__all__: list[str] = ["mysql_table_ddl", "routine_ddl", "view_ddl"]
