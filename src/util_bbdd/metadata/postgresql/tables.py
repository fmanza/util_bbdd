"""Helpers puros para metadata y DDL de tablas PostgreSQL."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# SQL para migrate/extractors — queries de extracción de esquema PostgreSQL
# (Opción P-A: aliases _for_extract para funciones con nombre conflictivo)
# Parámetros estilo %(name)s (DB-API 2.0 / psycopg2/psycopg3).
# ---------------------------------------------------------------------------


# ─── migrate/extractors: una consulta por schema y tipo de objeto (D1, 0.21.0) ─────────────
# La primera columna es siempre el nombre de la tabla (o vista); el resto, en el mismo orden que leen los extractores.
# Filas ordenadas por tabla y, dentro de cada una, por el orden propio del objeto (posición, constraint, índice).
# PK y FK sobre pg_catalog: en INFORMATION_SCHEMA la consulta de FK de un schema de 200 tablas tarda ~1,4 s.

_FK_RULE_SQL: str = (
    "CASE {col} WHEN 'a' THEN 'NO ACTION' WHEN 'r' THEN 'RESTRICT' WHEN 'c' THEN 'CASCADE' "
    "WHEN 'n' THEN 'SET NULL' WHEN 'd' THEN 'SET DEFAULT' END"
)


def fetch_can_disable_triggers_sql() -> str:
    """SQL que devuelve si el usuario actual puede ejecutar ``ALTER TABLE … DISABLE TRIGGER ALL`` en una tabla.

    Puede si es superusuario o propietario de la tabla. Lo usan ``BulkCrud.maintenance_scope`` y
    ``ParallelBulkLoader`` (desactivación previa al pool de workers) para no intentar un DDL que fallaría.

    Parámetros: ``:schema`` (``None`` = ``current_schema()``) y ``:tbl``.

    Returns:
        str: SQL con una fila y una columna booleana.
    """
    return (
        "SELECT current_setting('is_superuser') = 'on' "
        "OR EXISTS ("
        "  SELECT 1 FROM pg_tables "
        "  WHERE schemaname = COALESCE(:schema, current_schema()) "
        "  AND tablename = :tbl AND tableowner = current_user"
        ")"
    )


def fetch_can_create_temp_tables_sql() -> str:
    """SQL que devuelve si el usuario actual puede crear tablas temporales en la base de datos actual (privilegio TEMP).

    Lo usa el UPDATE por tabla temporal de ``bulk`` (``update_via_staging``) antes de intentarlo: en PostgreSQL un
    ``CREATE`` fallido deja la transacción abortada y no se podría seguir con el UPDATE por fila.

    Returns:
        str: SQL con una fila y una columna booleana.
    """
    return "SELECT has_database_privilege(current_database(), 'TEMP')"


def fetch_secondary_nonunique_indexes_sql() -> str:
    """SQL con los índices secundarios no únicos de una tabla y su DDL (``pg_get_indexdef``).

    Excluye los de PK, los únicos y los que respaldan una constraint. Lo usa ``dump.IndexManager`` para eliminarlos antes
    de la carga y recrearlos después con el DDL guardado.

    Parámetros: ``:tbl`` y ``:schema`` (``None`` = ``current_schema()``).

    Returns:
        str: SQL para (index_name, ddl).
    """
    return (
        "SELECT ic.relname AS index_name, pg_get_indexdef(i.indexrelid) AS ddl "
        "FROM pg_index i "
        "JOIN pg_class ic ON ic.oid = i.indexrelid "
        "JOIN pg_class tc ON tc.oid = i.indrelid "
        "JOIN pg_namespace n ON n.oid = tc.relnamespace "
        "WHERE tc.relname = :tbl "
        "  AND n.nspname = COALESCE(:schema, current_schema()) "
        "  AND NOT i.indisprimary AND NOT i.indisunique "
        "  AND NOT EXISTS (SELECT 1 FROM pg_constraint con WHERE con.conindid = i.indexrelid)"
    )


def fetch_fk_definition_sql() -> str:
    """SQL con la definición de una FK desde el catálogo: tabla referenciada y columnas de la hija y de la referenciada.

    La tabla referenciada sale como ``regclass`` (ya citada y con esquema si hace falta) y las columnas citadas con
    ``quote_ident``, en el orden de la constraint. Lo usa ``dump.ConstraintManager`` para buscar filas huérfanas tras
    reactivar los triggers (PD-04).

    Parámetros: ``:tbl`` (nombre de tabla citado, convertible a ``regclass``) y ``:name`` (nombre de la FK).

    Returns:
        str: SQL para (tabla_referenciada, columnas_hija[], columnas_referenciadas[]).
    """
    return """
        SELECT c.confrelid::regclass::text,
          (SELECT array_agg(quote_ident(a.attname) ORDER BY k.ord)
             FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum),
          (SELECT array_agg(quote_ident(a.attname) ORDER BY k.ord)
             FROM unnest(c.confkey) WITH ORDINALITY AS k(attnum, ord)
             JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.attnum)
        FROM pg_constraint c
        WHERE c.conrelid = CAST(:tbl AS regclass) AND c.conname = :name AND c.contype = 'f'
    """


__all__: list[str] = [
    "fetch_can_disable_triggers_sql",
    "fetch_secondary_nonunique_indexes_sql",
    "fetch_fk_definition_sql",
]
