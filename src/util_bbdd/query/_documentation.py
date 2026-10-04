"""Helpers internos para documentar catálogos de queries SQL."""

from __future__ import annotations

import re

from typing import Any

PARAMETER_PATTERN = r"\{(\w+)\}"


def build_query_info(*, db_type: str, queries: dict[str, str]) -> dict[str, Any]:
    """Construye el resumen público del catálogo de queries de un motor."""
    query_details: dict[str, dict[str, Any]] = {}
    for name, query in queries.items():
        required_params = list(set(re.findall(PARAMETER_PATTERN, query)))
        query_details[name] = {
            "template": query,
            "required_parameters": required_params,
            "parameter_count": len(required_params),
        }

    return {
        "db_type": db_type,
        "total_queries": len(queries),
        "query_names": list(queries.keys()),
        "queries": query_details,
    }


def get_query_dependencies(query_template: str) -> dict[str, list[str]]:
    """Extrae dependencias básicas de una plantilla SQL."""
    dependencies: dict[str, list[str]] = {"tables": [], "views": [], "schemata": [], "columns": []}

    from_pattern = r"(?:FROM|JOIN)\s+(\w+)"
    tables = re.findall(from_pattern, query_template, re.IGNORECASE)
    dependencies["tables"] = list(set(tables))

    schema_pattern = r"(?:schema|database)\s*=\s*[\'\"]([^\'\"]+)[\'\"]"
    schemas = re.findall(schema_pattern, query_template, re.IGNORECASE)
    dependencies["schemata"] = list(set(schemas))

    return dependencies


def build_query_documentation(*, db_type: str, query_name: str, query_template: str) -> dict[str, Any]:
    """Construye la documentación pública de una query concreta."""
    return {
        "query_name": query_name,
        "db_type": db_type,
        "description": "Consulta SQL personalizada",
        "template": query_template,
        "parameters": list(set(re.findall(PARAMETER_PATTERN, query_template))),
        "dependencies": get_query_dependencies(query_template),
        "examples": [],
    }


__all__: list[str] = [
    "build_query_documentation",
    "build_query_info",
    "get_query_dependencies",
]
