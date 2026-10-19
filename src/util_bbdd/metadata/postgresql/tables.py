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


def fetch_unique_indexes_sql() -> str:
    """SQL con los índices únicos válidos de una tabla, su constraint (PK/UNIQUE) si la respaldan y su DDL (v3.3.0).

    Para ``disable_indexes="all"``: los que respaldan una constraint se borran y recrean con
    ``pg_get_constraintdef``; el resto, con ``pg_get_indexdef``. Excluye los índices de otras constraints (exclusión).

    Parámetros: ``:tbl`` y ``:schema`` (``None`` = ``current_schema()``).

    ``columns[]`` son las columnas de la clave (sin las de ``INCLUDE`` y sin los elementos que son expresiones);
    ``key_sql[]``, cada elemento de la clave tal como lo escribe ``pg_get_indexdef(oid, n, true)`` (columna citada o
    expresión, p. ej. ``lower((email)::text)``), para buscar duplicados.

    Returns:
        str: SQL para (index_name, constraint_name, contype, indexdef, constraintdef, columns[], key_sql[]).
    """
    return (
        "SELECT ic.relname, con.conname, con.contype, pg_get_indexdef(i.indexrelid), "
        "  CASE WHEN con.oid IS NULL THEN NULL ELSE pg_get_constraintdef(con.oid) END, "
        "  ARRAY(SELECT a.attname FROM unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) "
        "        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum "
        "        WHERE k.ord <= i.indnkeyatts ORDER BY k.ord), "
        "  ARRAY(SELECT pg_get_indexdef(i.indexrelid, k, true) FROM generate_series(1, i.indnkeyatts) AS k ORDER BY k) "
        "FROM pg_index i "
        "JOIN pg_class ic ON ic.oid = i.indexrelid "
        "JOIN pg_class tc ON tc.oid = i.indrelid "
        "JOIN pg_namespace n ON n.oid = tc.relnamespace "
        "LEFT JOIN pg_constraint con ON con.conindid = i.indexrelid AND con.conrelid = i.indrelid "
        "  AND con.contype IN ('p', 'u') "
        "WHERE tc.relname = :tbl AND n.nspname = COALESCE(:schema, current_schema()) "
        "  AND i.indisunique AND i.indisvalid "
        "  AND NOT EXISTS (SELECT 1 FROM pg_constraint x WHERE x.conindid = i.indexrelid AND x.contype NOT IN ('p', 'u') "
        "                  AND x.conrelid = i.indrelid) "
        "ORDER BY ic.relname"
    )


def fetch_inbound_foreign_keys_sql() -> str:
    """SQL con las FK (de otras tablas o de la misma) que referencian una tabla, con su DDL (v3.3.0).

    Para ``disable_indexes="all"``: PostgreSQL no deja borrar la PK/UNIQUE de la que dependen; se borran antes y se
    recrean después (``NOT VALID`` + ``VALIDATE CONSTRAINT`` si estaban validadas). Sin los clones de particiones.

    Parámetros: ``:tbl`` y ``:schema`` (``None`` = ``current_schema()``).

    Returns:
        str: SQL para (constraint_name, child_schema, child_table, constraintdef, convalidated).
    """
    return (
        "SELECT con.conname, cn.nspname, ct.relname, pg_get_constraintdef(con.oid), con.convalidated "
        "FROM pg_constraint con "
        "JOIN pg_class ct ON ct.oid = con.conrelid "
        "JOIN pg_namespace cn ON cn.oid = ct.relnamespace "
        "JOIN pg_class tc ON tc.oid = con.confrelid "
        "JOIN pg_namespace n ON n.oid = tc.relnamespace "
        "WHERE con.contype = 'f' AND con.conparentid = 0 "
        "  AND tc.relname = :tbl AND n.nspname = COALESCE(:schema, current_schema()) "
        "ORDER BY cn.nspname, ct.relname, con.conname"
    )


def fetch_constraint_exists_sql() -> str:
    """SQL que devuelve una fila si existe la constraint ``:name`` en la tabla ``:tbl`` (texto para ``to_regclass``).

    Lo usa la restauración de ``disable_indexes="all"`` (v3.4.1): tras un rollback que deshizo el ``DROP CONSTRAINT``,
    la PK/UNIQUE o FK ya existe y no se recrea.

    Returns:
        str: SQL con una fila si existe.
    """
    return "SELECT 1 FROM pg_constraint WHERE conname = :name AND conrelid = to_regclass(:tbl)"


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
