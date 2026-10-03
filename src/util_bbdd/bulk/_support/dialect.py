"""Constantes y DDL de dialecto compartidos por ``bulk`` y ``dump``."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Table

from ...metadata import facts

# Dialectos de SQLAlchemy de la familia MySQL: comparten SQL de sesión (FOREIGN_KEY_CHECKS), casing de identificadores
# y estrategias de carga.
MYSQL_FAMILY: frozenset[str] = frozenset({"mysql", "mariadb"})

# Desactivar / reactivar la integridad de una tabla a nivel de catálogo (R12). SQL Server: comprobación de FK y CHECK;
# PostgreSQL: triggers, incluidos los internos de las FK. MySQL/MariaDB lo hace por sesión (FOREIGN_KEY_CHECKS) y cada
# consumidor mantiene su sentencia. Las políticas (transacción, orden, validación posterior) son de cada consumidor:
# ``BulkCrud.maintenance_scope``, ``ParallelBulkLoader`` y ``dump.ConstraintManager``.
_TABLE_INTEGRITY_SQL: dict[str, tuple[str, str]] = {
    "mssql": ("NOCHECK CONSTRAINT ALL", "WITH CHECK CHECK CONSTRAINT ALL"),
    "postgresql": ("DISABLE TRIGGER ALL", "ENABLE TRIGGER ALL"),
}


def disable_table_integrity_sql(dialect: str, quoted_table: str) -> str:
    """``ALTER TABLE`` que desactiva la integridad de ``quoted_table`` (ya citada) en SQL Server o PostgreSQL."""
    return f"ALTER TABLE {quoted_table} {_TABLE_INTEGRITY_SQL[dialect][0]}"


def enable_table_integrity_sql(dialect: str, quoted_table: str) -> str:
    """``ALTER TABLE`` que reactiva la integridad de ``quoted_table`` (ya citada) en SQL Server o PostgreSQL."""
    return f"ALTER TABLE {quoted_table} {_TABLE_INTEGRITY_SQL[dialect][1]}"


def can_disable_pg_triggers(conn: Any, table: Table) -> bool:
    """PostgreSQL: ``True`` si el usuario actual puede desactivar los triggers de ``table`` (superusuario o propietario)."""
    return facts.can_disable_triggers(conn, table.schema, table.name)


__all__: list[str] = [
    "MYSQL_FAMILY",
    "can_disable_pg_triggers",
    "disable_table_integrity_sql",
    "enable_table_integrity_sql",
]
