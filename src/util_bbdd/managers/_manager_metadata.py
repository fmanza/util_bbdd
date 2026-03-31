"""Helpers internos de metadata para managers sync y async."""

from __future__ import annotations

import logging

from typing import Any

from ..metadata import DatabaseMetadataCache, RelationshipMetadataCache


def get_query_context_database(*, db_type: str, database: str, conn_params: dict[str, Any]) -> str:
    """Resuelve el contexto schema/database para queries de metadata."""
    context_database: str = str(database or "").strip()

    if db_type == "oracle":
        oracle_user: str = str(conn_params.get("user", "")).strip()
        context_database = oracle_user or context_database
    elif db_type == "postgresql":
        explicit_context: str = str(conn_params.get("schema", "")).strip()
        context_database = explicit_context or context_database or "public"
    elif db_type == "hsqldb":
        explicit_context = str(conn_params.get("schema", "")).strip()
        context_database = explicit_context or context_database or "PUBLIC"
    elif db_type == "sqlserver":
        explicit_context = str(conn_params.get("schema", "")).strip()
        context_database = explicit_context or context_database or "dbo"

    return context_database


def get_query_context_label(db_type: str) -> str:
    """Devuelve la etiqueta descriptiva del contexto metadata."""
    return "owner/schema" if db_type == "oracle" else "database"


def add_metadata_context_params(*, db_type: str, params: dict[str, Any], context: str | None) -> dict[str, Any]:
    """Añade parámetros de contexto metadata según el motor."""
    if not context or db_type == "mariadb":
        return params
    if db_type in {"oracle", "sqlserver"}:
        params["esquema"] = context
    if db_type in {"postgresql", "hsqldb", "sqlserver"}:
        params["database"] = context
    return params


def clear_all_caches(
    *,
    db_cache: DatabaseMetadataCache,
    relationship_cache: RelationshipMetadataCache,
    logger: logging.Logger,
) -> None:
    """Limpia todas las cachés de metadata y relaciones."""
    db_cache.clear_all()
    relationship_cache.clear_all()
    logger.info("🧹 Todas las cachés de metadatos limpiadas completamente")


def clear_table_cache(
    *,
    db_cache: DatabaseMetadataCache,
    relationship_cache: RelationshipMetadataCache,
    logger: logging.Logger,
    context: str,
    table: str,
) -> None:
    """Limpia la caché asociada a una tabla o vista."""
    db_cache.clear_by_table(context, table)
    relationship_cache.clear_by_table(table)
    logger.info(f"🧹 Caché invalidada para tabla/vista {table} ({context})")


def clear_routine_cache(
    *,
    db_cache: DatabaseMetadataCache,
    logger: logging.Logger,
    context: str,
    routine: str,
    routine_type: str | None = None,
) -> None:
    """Limpia la caché asociada a una rutina concreta."""
    db_cache._routine_metadata_context_cache.pop(context, None)
    db_cache._routine_parameters_context_cache.pop(context, None)
    if routine_type:
        routine_key: tuple[str, str, str] = (context, routine, routine_type.upper())
        db_cache._routine_parameters_cache.pop(routine_key, None)
        db_cache._routine_ddl_cache.pop(routine_key, None)
    else:
        param_keys: list[tuple[str, str, str]] = [
            key for key in db_cache._routine_parameters_cache if key[0] == context and key[1] == routine
        ]
        ddl_keys: list[tuple[str, str, str]] = [
            key for key in db_cache._routine_ddl_cache if key[0] == context and key[1] == routine
        ]
        for cache_key in param_keys:
            db_cache._routine_parameters_cache.pop(cache_key, None)
        for cache_key in ddl_keys:
            db_cache._routine_ddl_cache.pop(cache_key, None)
    logger.info(f"🧹 Caché invalidada para rutina {routine} ({context})")


def clear_tuple_cache_by_context(cache: dict[tuple[Any, ...], Any], context: str) -> None:
    """Elimina entradas de caché cuya primera posición coincide con el contexto."""
    keys_to_remove: list[tuple[Any, ...]] = [key for key in cache if key and str(key[0]) == context]
    for cache_key in keys_to_remove:
        cache.pop(cache_key, None)


def clear_context_cache(*, db_cache: DatabaseMetadataCache, logger: logging.Logger, context: str) -> None:
    """Limpia todas las entradas de caché asociadas a un contexto."""
    context_caches: tuple[dict[str, Any], ...] = (
        db_cache._tables_cache,
        db_cache._views_cache,
        db_cache._routines_cache,
        db_cache._routine_metadata_context_cache,
        db_cache._routine_parameters_context_cache,
    )
    for context_cache in context_caches:
        context_cache.pop(context, None)

    tuple_caches: tuple[dict[tuple[Any, ...], Any], ...] = (
        db_cache._primary_keys_cache,
        db_cache._indices_cache,
        db_cache._foreign_keys_cache,
        db_cache._unique_constraints_cache,
        db_cache._columns_cache,
        db_cache._ddl_cache,
        db_cache._view_ddl_cache,
        db_cache._routine_parameters_cache,
        db_cache._routine_ddl_cache,
    )
    for tuple_cache in tuple_caches:
        clear_tuple_cache_by_context(tuple_cache, context)

    logger.info(f"🧹 Caché invalidada para contexto: {context}")


def cache_context_key(context_database: str) -> str:
    """Normaliza la clave de contexto para cachés."""
    return str(context_database or "")


def cache_table_key(context_database: str, table_name: str) -> tuple[str, str]:
    """Construye clave de caché por tabla."""
    return (cache_context_key(context_database), str(table_name or ""))


def cache_routine_key(context_database: str, routine_name: str, routine_type: str) -> tuple[str, str, str]:
    """Construye clave de caché por rutina."""
    return (
        cache_context_key(context_database),
        str(routine_name or ""),
        str(routine_type or "").upper(),
    )
