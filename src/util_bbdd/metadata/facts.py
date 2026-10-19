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

from .mariadb.tables import (
    fetch_nonunique_index_columns_sql,
    fetch_table_fk_columns_sql,
    fetch_table_storage_engine_sql,
)
from .oracle.indexes import fetch_secondary_nonunique_indexes_sql as _oracle_secondary_indexes_sql
from .oracle.tables import fetch_identity_generation_sql
from .postgresql.tables import (
    fetch_can_create_temp_tables_sql,
    fetch_can_disable_triggers_sql,
    fetch_fk_definition_sql,
    fetch_secondary_nonunique_indexes_sql as _pg_secondary_indexes_sql,
)
from .sqlserver.common import fetch_compatibility_level_sql
from .sqlserver.indexes import (
    fetch_clustered_index_count_sql,
    fetch_secondary_nonunique_indexes_sql as _mssql_secondary_indexes_sql,
)


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


def secondary_nonunique_indexes(
    conn: Any, schema: str | None, table: str, dialect: str | None = None
) -> list[tuple[str, str | None]]:
    """Índices secundarios no únicos de una tabla que ``bulk`` y ``dump`` pueden desactivar: ``[(nombre, DDL o None)]``.

    - SQL Server: ``NONCLUSTERED`` no únicos, sin PK ni constraint y habilitados (DDL ``None``).
    - Oracle: ``NORMAL`` no únicos que no respaldan una constraint (DDL ``None``).
    - PostgreSQL: no únicos, sin PK ni constraint, con su ``pg_get_indexdef`` para recrearlos.
    - MariaDB/MySQL: BTREE no únicos de columnas completas en orden ascendente, visibles y sin comentario (sin
      prefijos ni expresiones), que no empiezan por las columnas de una FK de la tabla ni por las que referencia una FK
      de otra (InnoDB los necesita). DDL: la cláusula para ``ALTER TABLE … ADD`` (``INDEX `n` (`a`, `b`)``).
    - Resto: ``[]``.

    ``dialect`` (nombre de SQLAlchemy) evita leerlo de la conexión.
    """
    dialect = dialect or conn.dialect.name
    if dialect == "mssql":
        rows = conn.execute(text(_mssql_secondary_indexes_sql()), {"tbl": table, "schema": schema}).fetchall()
        return [(str(r[0]), None) for r in rows]
    if dialect == "oracle":
        params = {"tbl": table, "owner": schema} if schema else {"tbl": table}
        rows = conn.execute(text(_oracle_secondary_indexes_sql(with_owner=bool(schema))), params).fetchall()
        return [(str(r[0]), None) for r in rows]
    if dialect == "postgresql":
        rows = conn.execute(text(_pg_secondary_indexes_sql()), {"tbl": table, "schema": schema}).fetchall()
        return [(str(r[0]), str(r[1])) for r in rows]
    if dialect in ("mysql", "mariadb"):
        return _mysql_secondary_indexes(conn, schema, table)
    return []


def _mysql_secondary_indexes(conn: Any, schema: str | None, table: str) -> list[tuple[str, str | None]]:
    """MariaDB/MySQL: ver :func:`secondary_nonunique_indexes`."""
    params = {"schema": schema, "tbl": table}
    columns: dict[str, list[str]] = {}
    rejected: set[str] = set()
    for row in conn.execute(text(fetch_nonunique_index_columns_sql()), params):
        info = {str(key).upper(): value for key, value in row._mapping.items()}
        name = str(info["INDEX_NAME"])
        simple = (
            info.get("COLUMN_NAME") is not None  # MySQL 8: NULL en los índices funcionales
            and info.get("SUB_PART") is None
            and info.get("EXPRESSION") is None
            and str(info.get("INDEX_TYPE") or "").upper() == "BTREE"
            and str(info.get("COLLATION") or "A").upper() == "A"
            and str(info.get("IS_VISIBLE") or "YES").upper() == "YES"
            and str(info.get("IGNORED") or "NO").upper() == "NO"
            and not str(info.get("INDEX_COMMENT") or "")
        )
        if not simple:
            rejected.add(name)
        columns.setdefault(name, []).append(str(info.get("COLUMN_NAME")))
    fk_prefixes = _mysql_fk_column_lists(conn, params, table)
    prep = conn.dialect.identifier_preparer
    out: list[tuple[str, str | None]] = []
    for name, cols in columns.items():
        lowered = [c.lower() for c in cols]
        if name in rejected or any(lowered[: len(fk)] == fk for fk in fk_prefixes):
            continue
        out.append((name, f"INDEX {prep.quote(name)} ({', '.join(prep.quote(c) for c in cols)})"))
    return out


def _mysql_fk_column_lists(conn: Any, params: dict[str, Any], table: str) -> list[list[str]]:
    """Columnas (en minúsculas y en orden) de cada FK de la tabla y de cada FK de otra tabla que la referencia."""
    child: dict[tuple[str, str, str], list[str]] = {}
    parent: dict[tuple[str, str, str], list[tuple[int, str]]] = {}
    for row in conn.execute(text(fetch_table_fk_columns_sql()), params):
        key = (str(row[0]), str(row[1]), str(row[2]))
        if str(row[1]).lower() == table.lower():
            child.setdefault(key, []).append(str(row[3]).lower())
        if str(row[5]).lower() == table.lower():
            parent.setdefault(key, []).append((int(row[8] or row[7] or 0), str(row[6]).lower()))
    return list(child.values()) + [[col for _, col in sorted(cols)] for cols in parent.values()]


def foreign_key_definition(conn: Any, table_ref: str, name: str) -> Any:
    """PostgreSQL: ``(tabla referenciada, [columnas], [columnas referenciadas])`` de una FK, citados; o ``None``.

    Args:
        table_ref: Tabla citada (convertible a ``regclass``).
    """
    return conn.execute(text(fetch_fk_definition_sql()), {"tbl": table_ref, "name": name}).first()


__all__: list[str] = [
    "can_create_temp_tables",
    "can_disable_triggers",
    "clustered_index_count",
    "compatibility_level",
    "foreign_key_definition",
    "identity_generation",
    "secondary_nonunique_indexes",
    "serial_sequence",
    "storage_engine",
]
