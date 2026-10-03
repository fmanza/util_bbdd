"""Las peticiones de metadatos de los managers resuelven la plantilla de su motor en ``data/sql_queries.json``.

H-10 (sesión 2026-10-03-metadata-centralization): ``create_view`` y ``create_rutina`` de PostgreSQL y ``create_rutina``
de HSQLDB usan ``{esquema}``, pero ``add_context_params`` solo lo añadía en Oracle y SQL Server, así que
``get_view_ddl()``/``get_routine_ddl()`` fallaban siempre con ``QueryValidationError`` en esos motores.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from util_bbdd.managers._metadata_context import MetadataContextResolver
from util_bbdd.managers._metadata_request import MetadataFetchRequest, MetadataRequestBuilder
from util_bbdd.query.registry import QueryRegistry
from util_bbdd.query.resolver import QueryResolver

ENGINES = ("oracle", "postgresql", "sqlserver", "hsqldb", "sqlite", "mariadb", "mysql")
CONTEXT = "APP_SCHEMA"


def _add_context(db_type: str) -> Callable[[dict[str, Any], str | None], dict[str, Any]]:
    def add(params: dict[str, Any], context: str | None) -> dict[str, Any]:
        return MetadataContextResolver.add_context_params(db_type=db_type, params=params, context=context)

    return add


def _requests(db_type: str) -> list[MetadataFetchRequest]:
    add = _add_context(db_type)
    table_rows = [
        MetadataFetchRequest(query_name=name, params=add({"tabla": "T1"}, CONTEXT), error_message="", table_name="T1")
        for name in ("indices", "claves_primarias", "claves_foraneas", "claves_unicas")
    ]
    return [
        MetadataRequestBuilder.routines(CONTEXT),
        MetadataRequestBuilder.table_ddl(CONTEXT, "T1", add),
        MetadataRequestBuilder.view_ddl(CONTEXT, "V1", add),
        MetadataRequestBuilder.columns(CONTEXT, "T1"),
        MetadataRequestBuilder.routine_parameters(CONTEXT, "R1", "FUNCTION"),
        MetadataRequestBuilder.routine_ddl(CONTEXT, "R1", "FUNCTION", add),
        *table_rows,
    ]


@pytest.mark.parametrize("db_type", ENGINES)
def test_every_manager_metadata_request_resolves_for_its_engine(db_type: str) -> None:
    registry = QueryRegistry()
    resolver = QueryResolver(registry).bind(db_type)
    available = set(registry.get_available_queries(db_type))
    for request in _requests(db_type):
        if request.query_name not in available:
            continue
        resolved = resolver.resolve(request.query_name, dict(request.params))
        assert "{" not in resolved.final_sql, f"{db_type}.{request.query_name}: marcador sin sustituir"


@pytest.mark.parametrize(("db_type", "query_name"), [("postgresql", "create_view"), ("postgresql", "create_rutina")])
def test_postgresql_ddl_queries_use_the_metadata_context_as_schema(db_type: str, query_name: str) -> None:
    builder = MetadataRequestBuilder.view_ddl if query_name == "create_view" else None
    add = _add_context(db_type)
    request = (
        builder(CONTEXT, "V1", add) if builder else MetadataRequestBuilder.routine_ddl(CONTEXT, "R1", "FUNCTION", add)
    )
    resolved = QueryResolver(QueryRegistry()).bind(db_type).resolve(request.query_name, dict(request.params))
    assert CONTEXT in resolved.final_sql
