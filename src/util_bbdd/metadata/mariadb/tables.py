"""Helpers puros para metadata y DDL de tablas MariaDB."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# SQL para migrate/extractors — queries de extracción de esquema MariaDB
# ---------------------------------------------------------------------------


# ─── migrate/extractors: una consulta por schema y tipo de objeto (D1, 0.21.0) ─────────────
# La primera columna es siempre el nombre de la tabla (o vista); el resto, en el mismo orden que leen los
# extractores. 200 tablas: 823 consultas (1,06 s MariaDB / 0,84 s MySQL en el banco) → 8.


def fetch_fk_for_schema_sql() -> str:
    """SQL de las columnas de las claves foráneas de todas las tablas de un schema MariaDB (uso: migrate/extractors).

    Sin las reglas ``ON DELETE``/``ON UPDATE``: se leen aparte con :func:`fetch_fk_rules_for_schema_sql` y se unen en
    Python. Unir ``KEY_COLUMN_USAGE`` con ``REFERENTIAL_CONSTRAINTS`` en SQL es cuadrático en el nº de FK
    (H-16, sesión 2026-10-03-metadata-centralization: 5000 tablas, MySQL 15,7 s y MariaDB 4,5 s; las dos consultas por
    separado, 52 ms y 183 ms).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA,
             REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, ORDINAL_POSITION).
    """
    return (
        "SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, "
        "REFERENCED_COLUMN_NAME, ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = %(schema)s "
        "AND REFERENCED_TABLE_NAME IS NOT NULL "
        "ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION"
    )


def fetch_fk_rules_for_schema_sql() -> str:
    """SQL de las reglas ``ON DELETE``/``ON UPDATE`` de todas las FK de un schema MariaDB (uso: migrate/extractors).

    Complementa :func:`fetch_fk_for_schema_sql` (ver H-16 allí). Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE, UPDATE_RULE).
    """
    return (
        "SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE, UPDATE_RULE "
        "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = %(schema)s"
    )


def fetch_table_storage_engine_sql() -> str:
    """SQL con el motor de almacenamiento (``InnoDB``, ``MyISAM``, ``Aria``…) de una tabla. Vale también para MySQL.

    Lo usa ``BulkCrud.maintenance_scope``: ``DISABLE KEYS`` solo tiene efecto en MyISAM/Aria y en InnoDB provocaría un
    commit implícito.

    Parámetros: ``:schema`` (``None`` = ``DATABASE()``) y ``:tbl``.

    Returns:
        str: SQL con una fila y el nombre del motor.
    """
    return (
        "SELECT ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = COALESCE(:schema, DATABASE()) AND TABLE_NAME = :tbl"
    )
