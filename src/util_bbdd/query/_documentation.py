"""Helpers internos para documentar catálogos de queries SQL."""

from __future__ import annotations

import re

from typing import Any

PARAMETER_PATTERN = r"\{(\w+)\}"

_QUERY_DESCRIPTIONS: dict[str, str] = {
    "obtener_tablas": "Obtiene la lista de tablas de la base de datos",
    "columnas_tabla": "Obtiene información detallada de las columnas de una tabla",
    "create_table": "Genera el DDL (Data Definition Language) para crear una tabla",
    "obtener_rutinas": "Obtiene la lista de rutinas (procedures y funciones)",
    "parametros_rutina": "Obtiene la lista de parámetros de una rutina",
    "create_rutina": "Obtiene el DDL de una rutina (procedure/función)",
    "indices": "Obtiene la lista de índices de una tabla",
    "claves_primarias": "Obtiene las claves primarias de una tabla",
    "claves_foraneas": "Obtiene las claves foráneas (foreign keys) de una tabla",
    "claves_unicas": "Obtiene las restricciones únicas de una tabla",
    "ficheros_fisicos": "Obtiene inventario de ficheros físicos y tamaños",
    "sqlite_file_summary": "Obtiene resumen interno del fichero SQLite principal",
    "temp_tablespaces": "Obtiene configuración de tablespaces temporales",
    "temp_storage_variables": "Obtiene variables de configuración del almacenamiento temporal",
}


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
        "description": _QUERY_DESCRIPTIONS.get(query_name, "Consulta SQL personalizada"),
        "template": query_template,
        "parameters": list(set(re.findall(PARAMETER_PATTERN, query_template))),
        "dependencies": get_query_dependencies(query_template),
        "examples": get_query_examples(db_type=db_type, query_name=query_name),
    }


def get_query_examples(*, db_type: str, query_name: str) -> list[dict[str, Any]]:
    """Devuelve ejemplos de uso para una query documentable."""
    examples_factory: dict[str, list[dict[str, Any]]] = {
        "obtener_tablas": [
            {
                "description": "Obtener todas las tablas del schema public",
                "parameters": {"database": "public"},
            }
        ],
        "obtener_rutinas": [
            {
                "description": "Obtener procedures y funciones del schema public",
                "parameters": {"database": "public"},
            }
        ],
        "parametros_rutina": [
            {
                "description": "Obtener parámetros de la rutina calcular_totales",
                "parameters": {
                    "database": "public",
                    "rutina": "calcular_totales",
                    "tipo_rutina": "FUNCTION",
                },
            }
        ],
        "create_rutina": [
            {
                "description": "Generar DDL de la rutina actualizar_stock",
                "parameters": {"rutina": "actualizar_stock", "tipo_rutina": "PROCEDURE"},
            }
        ],
        "columnas_tabla": [
            {
                "description": "Obtener columnas de la tabla usuarios",
                "parameters": {"database": "public", "tabla": "usuarios"},
            }
        ],
        "create_table": [
            {
                "description": "Generar DDL de la tabla productos",
                "parameters": {"tabla": "productos"},
            }
        ],
        "sqlite_file_summary": [{"description": "Resumen de tamaño del fichero SQLite principal", "parameters": {}}],
        "temp_storage_variables": _get_temp_storage_variables_examples(db_type),
    }
    if query_name == "ficheros_fisicos":
        return [_get_storage_inventory_example(db_type)]
    if query_name == "temp_tablespaces":
        return [_get_temp_tablespaces_example(db_type)]
    return examples_factory.get(query_name, [])


def _get_storage_inventory_example(db_type: str) -> dict[str, Any]:
    """Devuelve el ejemplo de inventario físico apropiado para el motor."""
    examples_by_db: dict[str, dict[str, Any]] = {
        "oracle": {
            "description": "Inventario de ficheros para un tablespace Oracle",
            "parameters": {"tablespace": "USERS"},
        },
        "postgresql": {
            "description": "Tamaño y ruta de un tablespace PostgreSQL",
            "parameters": {"tablespace": "pg_default"},
        },
        "mariadb": {
            "description": "Tamaño por tabla en MariaDB",
            "parameters": {"database": "mi_bd"},
        },
        "mysql": {
            "description": "Tamaño por tabla en MySQL",
            "parameters": {"database": "mi_bd"},
        },
        "sqlite": {
            "description": "Listado de ficheros de bases adjuntas en SQLite",
            "parameters": {},
        },
    }
    return examples_by_db.get(
        db_type,
        {"description": "Inventario de ficheros físicos SQL Server", "parameters": {}},
    )


def _get_temp_tablespaces_example(db_type: str) -> dict[str, Any]:
    """Devuelve el ejemplo de inventario temporal según el motor."""
    examples_by_db: dict[str, dict[str, Any]] = {
        "mariadb": {
            "description": "Inventario de ficheros temporales desde information_schema.FILES en MariaDB",
            "parameters": {},
        },
        "mysql": {
            "description": "Inventario de ficheros temporales desde information_schema.FILES en MySQL",
            "parameters": {},
        },
        "postgresql": {
            "description": "Ver configuración de tablespaces temporales PostgreSQL",
            "parameters": {},
        },
    }
    return examples_by_db.get(
        db_type,
        {"description": "Consultar tablespaces temporales del motor", "parameters": {}},
    )


def _get_temp_storage_variables_examples(db_type: str) -> list[dict[str, Any]]:
    """Devuelve ejemplos para variables de almacenamiento temporal."""
    if db_type not in {"mariadb", "mysql"}:
        return []
    return [
        {
            "description": "Leer innodb_temp_data_file_path para documentar el almacenamiento temporal InnoDB",
            "parameters": {},
        }
    ]


__all__: list[str] = [
    "build_query_documentation",
    "build_query_info",
    "get_query_dependencies",
    "get_query_examples",
]
