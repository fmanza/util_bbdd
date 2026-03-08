"""
Modelos de datos unificados para queries y tipos de BD.

Definiciones de estructuras que representan consultas, tipos de BD, y resultados
de resolución de queries con el nuevo modelo unificado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QueryDefinition:
    """Define una consulta SQL con metadatos normalizados.

    Atributos:
        name: Nombre de la query (ej: "obtener_tablas")
        db_type: Tipo de base de datos (ej: "mariadb")
        sql_template: Template SQL con placeholders {param}
        required_params: Lista de parámetros requeridos
        optional_params: Lista de parámetros opcionales
        docstring: Descripción de la query
        metadata: Metadatos adicionales (category, result_type, etc.)
    """

    name: str
    db_type: str
    sql_template: str
    required_params: list[str]
    optional_params: list[str] = field(default_factory=list)
    docstring: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validación después de inicialización."""
        if not self.name:
            raise ValueError("QueryDefinition.name cannot be empty")
        if not self.db_type:
            raise ValueError("QueryDefinition.db_type cannot be empty")
        if not self.sql_template:
            raise ValueError("QueryDefinition.sql_template cannot be empty")


@dataclass
class DatabaseTypeDefinition:
    """Define capacidades de un motor de base de datos.

    Atributos:
        name: Nombre legible (ej: "MariaDB")
        db_type: Clave del motor (ej: "mariadb")
        version_range: Rango de versiones soportadas (ej: "5.5.0+")
        default_port: Puerto por defecto para conexiones
        drivers: Lista de drivers disponibles (ej: ["mariadb", "mysql"])
        supported_features: Características soportadas (ej: ["Transacciones ACID"])
        required_params: Parámetros de conexión requeridos
        optional_params: Parámetros de conexión opcionales
        connection_param_schema: Esquema detallado de parámetros de conexión
    """

    name: str
    db_type: str
    version_range: str
    default_port: int
    drivers: list[str]
    supported_features: list[str]
    required_params: list[str]
    optional_params: list[str]
    connection_param_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedQuery:
    """Resultado de resolver una query con parámetros validados.

    Atributos:
        query_definition: QueryDefinition original
        final_sql: SQL final con parámetros interpolados
        validated: True si pasó todas las validaciones
        warnings: Lista de warnings de validación
        metadata: Metadatos adicionales (elapsed_ms, origin_resolver, etc.)
    """

    query_definition: QueryDefinition
    final_sql: str
    validated: bool
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validación después de inicialización."""
        if not self.final_sql:
            raise ValueError("ResolvedQuery.final_sql cannot be empty")
