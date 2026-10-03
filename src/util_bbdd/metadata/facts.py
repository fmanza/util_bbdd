"""Hechos puntuales del catálogo y del servidor que necesita ``bulk`` antes de una operación (grupo C5 de ADR-003).

No son metadatos de un schema (eso es :class:`~util_bbdd.metadata.CatalogSource`): son preguntas sobre una tabla o
sobre la sesión —la secuencia de una columna ``serial``, el tipo de una identity de Oracle, el motor de almacenamiento
de MySQL/MariaDB, si una tabla de SQL Server tiene índice clustered, el nivel de compatibilidad, si el usuario puede
crear tablas temporales o desactivar triggers— que se hacen una vez por operación sobre la conexión del llamador
(en su transacción). Aquí vive su SQL para que los consumidores no importen ``metadata.<motor>``.

Todas reciben una ``Connection`` de SQLAlchemy y devuelven ``None``/``False`` cuando el dato no existe.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from .mariadb.tables import fetch_table_storage_engine_sql
from .oracle.tables import fetch_identity_generation_sql
from .postgresql.tables import fetch_can_create_temp_tables_sql, fetch_can_disable_triggers_sql
from .sqlserver.common import fetch_compatibility_level_sql
from .sqlserver.indexes import fetch_clustered_index_count_sql


def serial_sequence(conn: Any, table_ref: str, column: str) -> str | None:
    """PostgreSQL: secuencia vinculada a una columna ``serial``/identity (``pg_get_serial_sequence``) o ``None``.

    Args:
        table_ref: Tabla citada como identificador SQL (``"Esquema"."Tabla"``): la función la analiza como tal.
    """
    value = conn.execute(text("SELECT pg_get_serial_sequence(:tbl, :col)"), {"tbl": table_ref, "col": column}).scalar()
    return None if value is None else str(value)


def identity_generation(conn: Any, table: str, column: str, owner: str | None = None) -> tuple[Any, Any] | None:
    """Oracle: ``(generation_type, default_on_null)`` de una columna identity, o ``None`` si no lo es.

    Args:
        table: Nombre de la tabla como en el catálogo (mayúsculas si no se creó entre comillas).
        column: Nombre de la columna, ídem.
        owner: Owner como en el catálogo; ``None`` = el del usuario de la sesión (vistas ``USER_*``).
    """
    params = {"tbl": table, "col": column}
    if owner:
        params["owner"] = owner
    row = conn.execute(text(fetch_identity_generation_sql(with_owner=bool(owner))), params).fetchone()
    return None if row is None else (row[0], row[1])


def storage_engine(conn: Any, schema: str | None, table: str) -> str | None:
    """MySQL/MariaDB: motor de almacenamiento de una tabla (``InnoDB``, ``MyISAM``, ``Aria``…); ``schema=None`` = el actual."""
    value = conn.execute(text(fetch_table_storage_engine_sql()), {"schema": schema, "tbl": table}).scalar()
    return None if value is None else str(value)


def clustered_index_count(conn: Any, table: str) -> int:
    """SQL Server: índices clustered de una tabla (0 = heap). ``table`` como lo admite ``OBJECT_ID`` (con esquema)."""
    return int(conn.execute(text(fetch_clustered_index_count_sql()), {"tbl": table}).scalar() or 0)


def compatibility_level(conn: Any) -> Any:
    """SQL Server: nivel de compatibilidad de la base de datos actual (p. ej. ``160``)."""
    return conn.execute(text(fetch_compatibility_level_sql())).scalar()


def can_create_temp_tables(conn: Any) -> bool:
    """PostgreSQL: si el usuario puede crear tablas temporales en la base de datos actual (privilegio ``TEMP``)."""
    return bool(conn.execute(text(fetch_can_create_temp_tables_sql())).scalar())


def can_disable_triggers(conn: Any, schema: str | None, table: str) -> bool:
    """PostgreSQL: si el usuario puede ``ALTER TABLE … DISABLE TRIGGER ALL`` (superusuario o propietario)."""
    return bool(conn.execute(text(fetch_can_disable_triggers_sql()), {"schema": schema, "tbl": table}).scalar())


__all__: list[str] = [
    "can_create_temp_tables",
    "can_disable_triggers",
    "clustered_index_count",
    "compatibility_level",
    "identity_generation",
    "serial_sequence",
    "storage_engine",
]
