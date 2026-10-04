"""Inventario de almacenamiento por motor: ficheros de datos y espacio temporal (E2 de ADR-003).

SQL de servidor (no de catálogo de schema) con ``:nombre`` como el resto de ``metadata/``; lo ejecutan los managers
sobre su ejecutor de catálogo (:meth:`SyncDatabaseManager.get_storage_rows` / ``get_storage_inventory``) y lo
presenta ``doc``. Consultas por motor:

- ``ficheros_fisicos``: ficheros o tablas con su tamaño (``:schema`` en MySQL/MariaDB, ``:tablespace`` en Oracle y
  PostgreSQL).
- ``temp_tablespaces``: espacio temporal (``:tablespace`` en Oracle).
- ``temp_storage_variables`` (MySQL/MariaDB), ``sqlite_file_summary`` (SQLite) y ``user_tablespaces`` (Oracle:
  tablespaces por defecto y temporal del usuario).

HSQLDB no tiene inventario (``{"primary": []}``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from ._paramstyle import placeholders

FetchAll = Callable[[str, Mapping[str, Any]], Sequence[Sequence[Any]]]
AsyncFetchAll = Callable[[str, Mapping[str, Any]], Awaitable[Sequence[Sequence[Any]]]]

_STORAGE_SQL: dict[str, dict[str, str]] = {
    "mariadb": {
        "ficheros_fisicos": (
            "SELECT CONVERT(t.table_schema USING utf8mb4) AS db, CONVERT(t.table_name USING utf8mb4) AS objeto, "
            "CONVERT(t.engine USING utf8mb4) AS motor, ROUND(t.data_length/1024/1024, 2) AS datos_mb, "
            "ROUND(t.index_length/1024/1024, 2) AS indices_mb, ROUND((t.data_length+t.index_length)/1024/1024, "
            "2) AS total_mb FROM information_schema.tables t WHERE t.table_schema = :schema ORDER BY total_mb "
            "DESC"
        ),
        "temp_tablespaces": (
            "SELECT CONVERT(TABLESPACE_NAME USING utf8mb4) AS tablespace, CONVERT(FILE_NAME USING utf8mb4) AS "
            "archivo, ROUND(EXTENT_SIZE / 1024 / 1024, 2) AS extent_mb, ROUND(INITIAL_SIZE / 1024 / 1024, 2) AS "
            "initial_mb, ROUND(MAXIMUM_SIZE / 1024 / 1024, 2) AS max_mb FROM information_schema.FILES WHERE "
            "FILE_TYPE = 'TEMPORARY' ORDER BY TABLESPACE_NAME, FILE_NAME"
        ),
        "temp_storage_variables": "SHOW VARIABLES LIKE 'innodb_temp_data_file_path'",
    },
    "mysql": {
        "ficheros_fisicos": (
            "SELECT CONVERT(t.table_schema USING utf8mb4) AS db, CONVERT(t.table_name USING utf8mb4) AS objeto, "
            "CONVERT(t.engine USING utf8mb4) AS motor, ROUND(t.data_length/1024/1024, 2) AS datos_mb, "
            "ROUND(t.index_length/1024/1024, 2) AS indices_mb, ROUND((t.data_length+t.index_length)/1024/1024, "
            "2) AS total_mb FROM information_schema.tables t WHERE t.table_schema = :schema ORDER BY total_mb "
            "DESC"
        ),
        "temp_tablespaces": (
            "SELECT CONVERT(TABLESPACE_NAME USING utf8mb4) AS tablespace, CONVERT(FILE_NAME USING utf8mb4) AS "
            "archivo, ROUND(EXTENT_SIZE / 1024 / 1024, 2) AS extent_mb, ROUND(INITIAL_SIZE / 1024 / 1024, 2) AS "
            "initial_mb, ROUND(MAXIMUM_SIZE / 1024 / 1024, 2) AS max_mb FROM information_schema.FILES WHERE "
            "FILE_TYPE = 'TEMPORARY' ORDER BY TABLESPACE_NAME, FILE_NAME"
        ),
        "temp_storage_variables": "SHOW VARIABLES LIKE 'innodb_temp_data_file_path'",
    },
    "oracle": {
        "ficheros_fisicos": (
            "SELECT tablespace_name AS tablespace, file_name AS archivo, bytes/1024/1024 AS tamano_mb, status AS "
            "estado, 'DATAFILE' AS file_type, autoextensible AS autoextensible, maxbytes/1024/1024 AS max_mb "
            "FROM dba_data_files WHERE tablespace_name = UPPER(:tablespace) ORDER BY 1, 3 DESC"
        ),
        "temp_tablespaces": (
            "SELECT tablespace_name AS tablespace, file_name AS archivo, bytes/1024/1024 AS tamano_mb, status AS "
            "estado, 'TEMPFILE' AS file_type, autoextensible AS autoextensible, maxbytes/1024/1024 AS max_mb "
            "FROM dba_temp_files WHERE tablespace_name = UPPER(:tablespace) ORDER BY 1, 3 DESC"
        ),
    },
    "postgresql": {
        "ficheros_fisicos": (
            "SELECT spcname AS tablespace, CASE WHEN spcname = 'pg_default' THEN "
            "current_setting('data_directory') WHEN spcname = 'pg_global' THEN current_setting('data_directory') "
            "|| '/global' ELSE COALESCE(NULLIF(pg_tablespace_location(oid), ''), "
            "current_setting('data_directory') || '/pg_tblspc/' || oid::text) END AS filesystem_path, "
            "pg_size_pretty(pg_tablespace_size(oid)) AS total_size FROM pg_tablespace WHERE spcname = :tablespace"
        ),
        "temp_tablespaces": (
            "SELECT CASE WHEN COALESCE(BTRIM(current_setting('temp_tablespaces', true)), '') <> '' THEN "
            "current_setting('temp_tablespaces', true) ELSE COALESCE(ts.spcname, 'pg_default') END AS "
            "temp_tablespaces FROM pg_database d LEFT JOIN pg_tablespace ts ON ts.oid = d.dattablespace WHERE "
            "d.datname = current_database()"
        ),
    },
    "sqlserver": {
        "ficheros_fisicos": (
            "SELECT DB_NAME() AS [database_name], df.name AS [logical_name], df.type_desc AS [file_type], "
            "df.physical_name AS [physical_file], CAST(df.size AS bigint) * 8 / 1024 AS [size_mb], CASE "
            "df.max_size WHEN -1 THEN NULL WHEN 0 THEN CAST(df.size AS bigint) * 8 / 1024 ELSE CAST(df.max_size "
            "AS bigint) * 8 / 1024 END AS [max_size_mb], df.is_percent_growth AS [is_percent_growth], CASE "
            "df.is_percent_growth WHEN 1 THEN CONCAT(df.growth, ' %') ELSE CONCAT(CAST(df.growth AS bigint) * 8 "
            "/ 1024, ' MB') END AS [growth_setting] FROM sys.database_files AS df ORDER BY df.type_desc, "
            "[size_mb] DESC"
        ),
        "temp_tablespaces": (
            "SELECT DB_NAME(database_id) AS [database_name], name AS [logical_name], type_desc AS [file_type], "
            "physical_name AS [physical_file], CAST(size AS bigint) * 8 / 1024 AS [size_mb], CASE max_size WHEN "
            "-1 THEN NULL WHEN 0 THEN CAST(size AS bigint) * 8 / 1024 ELSE CAST(max_size AS bigint) * 8 / 1024 "
            "END AS [max_size_mb], is_percent_growth AS [is_percent_growth], CASE is_percent_growth WHEN 1 THEN "
            "CONCAT(growth, ' %') ELSE CONCAT(CAST(growth AS bigint) * 8 / 1024, ' MB') END AS [growth_setting] "
            "FROM sys.master_files WHERE DB_NAME(database_id) = 'tempdb' ORDER BY [file_type], [size_mb] DESC"
        ),
    },
    "sqlite": {
        "ficheros_fisicos": "PRAGMA database_list",
        "temp_tablespaces": "PRAGMA temp_store",
        "sqlite_file_summary": (
            "SELECT (SELECT page_count FROM pragma_page_count) AS page_count, (SELECT page_size FROM "
            "pragma_page_size) AS page_size, ((SELECT page_count FROM pragma_page_count) * (SELECT page_size "
            "FROM pragma_page_size)) AS size_bytes"
        ),
    },
}
_STORAGE_SQL["oracle"]["user_tablespaces"] = "SELECT default_tablespace, temporary_tablespace FROM user_users"

# Motores en los que el inventario necesita un tablespace
_NEEDS_TABLESPACE: dict[str, str] = {"oracle": "Oracle", "postgresql": "PostgreSQL"}
# Consultas de get_storage_inventory() por motor y clave del resultado
_INVENTORY: dict[str, tuple[tuple[str, str], ...]] = {
    "sqlserver": (("primary", "ficheros_fisicos"), ("temp_tablespaces", "temp_tablespaces")),
    "oracle": (("primary", "ficheros_fisicos"), ("temp_tablespaces", "temp_tablespaces")),
    "mariadb": (("primary", "ficheros_fisicos"), ("temp_tablespaces", "temp_tablespaces")),
    "mysql": (("primary", "ficheros_fisicos"), ("temp_tablespaces", "temp_tablespaces")),
    "postgresql": (("primary", "ficheros_fisicos"), ("temp_tablespaces", "temp_tablespaces")),
    "sqlite": (
        ("primary", "ficheros_fisicos"),
        ("sqlite_file_summary", "sqlite_file_summary"),
        ("temp_tablespaces", "temp_tablespaces"),
    ),
    "hsqldb": (),
}


def storage_query(engine: str, name: str) -> str | None:
    """SQL de la consulta ``name`` de almacenamiento del motor; ``None`` si el motor no la tiene."""
    return _STORAGE_SQL.get(engine, {}).get(name)


def storage_query_params(engine: str, name: str) -> tuple[str, ...]:
    """Parámetros (``:nombre``) que usa la consulta, sin repetir; vacío si el motor no la tiene."""
    sql = storage_query(engine, name)
    return tuple(dict.fromkeys(placeholders(sql))) if sql else ()


def _plan(engine: str, schema: str, tablespace: str | None) -> list[tuple[str, str, dict[str, Any]]]:
    if engine not in _INVENTORY:
        raise ValueError(f"Inventario de almacenamiento no soportado para '{engine}'")
    if engine in _NEEDS_TABLESPACE and not tablespace:
        raise ValueError(f"Para {_NEEDS_TABLESPACE[engine]} debe proporcionar 'tablespace'")
    params = {"schema": schema, "tablespace": tablespace}
    return [(key, _STORAGE_SQL[engine][name], params) for key, name in _INVENTORY[engine]]


def read_storage_inventory(
    fetch_all: FetchAll, engine: str, schema: str, tablespace: str | None = None
) -> dict[str, list[tuple[Any, ...]]]:
    """Inventario de almacenamiento: ``{"primary": filas, "temp_tablespaces": filas, …}``.

    Raises:
        ValueError: Motor sin inventario o sin ``tablespace`` donde hace falta (Oracle, PostgreSQL).
    """
    plan = _plan(engine, schema, tablespace)
    if not plan:
        return {"primary": []}
    return {key: [tuple(row) for row in fetch_all(sql, params)] for key, sql, params in plan}


async def aread_storage_inventory(
    fetch_all: AsyncFetchAll, engine: str, schema: str, tablespace: str | None = None
) -> dict[str, list[tuple[Any, ...]]]:
    """Versión async de :func:`read_storage_inventory`."""
    plan = _plan(engine, schema, tablespace)
    if not plan:
        return {"primary": []}
    return {key: [tuple(row) for row in await fetch_all(sql, params)] for key, sql, params in plan}


__all__: list[str] = [
    "aread_storage_inventory",
    "read_storage_inventory",
    "storage_query",
    "storage_query_params",
]
