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


def fetch_nonunique_index_columns_sql() -> str:
    """SQL con las columnas de los índices no únicos de una tabla MariaDB/MySQL, en orden. Vale para los dos.

    ``SELECT *`` a propósito: MySQL 8 tiene ``EXPRESSION`` e ``IS_VISIBLE`` y MariaDB ``IGNORED``; quien la usa lee las
    columnas por nombre y trata las que falten. Lo usan ``bulk`` y ``dump`` (``facts.secondary_nonunique_indexes``) para
    elegir qué índices se pueden borrar y recrear durante una carga.

    Parámetros: ``:schema`` (``None`` = ``DATABASE()``) y ``:tbl``.

    Returns:
        str: SQL de ``information_schema.STATISTICS`` ordenado por índice y posición.
    """
    return (
        "SELECT * FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = COALESCE(:schema, DATABASE()) AND TABLE_NAME = :tbl AND NON_UNIQUE = 1 "
        "ORDER BY INDEX_NAME, SEQ_IN_INDEX"
    )


def fetch_unique_index_columns_sql() -> str:
    """SQL con las columnas de los índices únicos de una tabla MariaDB/MySQL, sin la PK (``disable_indexes="all"``).

    Mismas reglas de lectura que :func:`fetch_nonunique_index_columns_sql` (``SELECT *`` por las columnas de cada
    motor). La PK no: en InnoDB es el índice clustered.

    Parámetros: ``:schema`` (``None`` = ``DATABASE()``) y ``:tbl``.

    Returns:
        str: SQL de ``information_schema.STATISTICS`` ordenado por índice y posición.
    """
    return (
        "SELECT * FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = COALESCE(:schema, DATABASE()) AND TABLE_NAME = :tbl AND NON_UNIQUE = 0 "
        "AND INDEX_NAME <> 'PRIMARY' "
        "ORDER BY INDEX_NAME, SEQ_IN_INDEX"
    )


def fetch_table_fk_columns_sql() -> str:
    """SQL con las columnas de las FK en las que participa una tabla MariaDB/MySQL, como hija o como referenciada.

    InnoDB no deja borrar el índice que usa una FK (error 1553; MariaDB 11.4 sí con ``FOREIGN_KEY_CHECKS=0``, y la FK
    queda sin índice): ``facts.secondary_nonunique_indexes`` excluye los índices que empiezan por esas columnas.

    Parámetros: ``:schema`` (``None`` = ``DATABASE()``) y ``:tbl``.

    Returns:
        str: SQL para (TABLE_SCHEMA, TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA,
             REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, ORDINAL_POSITION, POSITION_IN_UNIQUE_CONSTRAINT).
    """
    return (
        "SELECT TABLE_SCHEMA, TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, "
        "REFERENCED_COLUMN_NAME, ORDINAL_POSITION, POSITION_IN_UNIQUE_CONSTRAINT "
        "FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE REFERENCED_TABLE_NAME IS NOT NULL AND ("
        "(TABLE_SCHEMA = COALESCE(:schema, DATABASE()) AND TABLE_NAME = :tbl) OR "
        "(REFERENCED_TABLE_SCHEMA = COALESCE(:schema, DATABASE()) AND REFERENCED_TABLE_NAME = :tbl)) "
        "ORDER BY TABLE_SCHEMA, TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION"
    )


def fetch_table_storage_engine_sql() -> str:
    """SQL con el motor de almacenamiento (``InnoDB``, ``MyISAM``, ``Aria``…) de una tabla. Vale también para MySQL.

    Lo usan ``BulkCrud.maintenance_scope`` y la estrategia común de índices (``bulk/_support/secondary_indexes.py``):
    ``DISABLE KEYS`` solo tiene efecto en MyISAM/Aria; en InnoDB se borran y recrean los índices.

    Parámetros: ``:schema`` (``None`` = ``DATABASE()``) y ``:tbl``.

    Returns:
        str: SQL con una fila y el nombre del motor.
    """
    return (
        "SELECT ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = COALESCE(:schema, DATABASE()) AND TABLE_NAME = :tbl"
    )
