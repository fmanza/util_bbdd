"""Tipos y type aliases comunes para util_bbdd.

Este módulo centraliza todas las definiciones de tipos utilizadas
en la librería para garantizar consistencia en toda la base de código.
"""

from typing import Any

# Tipos de resultados
RowOrNone = tuple[Any, ...] | None
"""Tupla de una fila o None si no hay resultados."""

Rows = list[tuple[Any, ...]]
"""Lista de tuplas representando filas de resultados."""

# Contexto de esquema/base de datos
SchemaContext = str
"""Nombre del esquema/base de datos para queries de metadatos."""

# Sentencias DDL
DDLStatement = str
"""Sentencia DDL (CREATE TABLE, CREATE VIEW, etc.)."""

# Parámetros de query
QueryParams = dict[str, Any]
"""Parámetros de una consulta parametrizada."""

# Configuración de conexión
ConnectionConfig = dict[str, Any]
"""Configuración de conexión a base de datos."""

# Identificador de conexión
ConnectionID = int
"""Identificador único de una conexión."""

# Callback tipos
ConnectionProvider = type[None]  # Actual: Callable[[], Any]
"""Función que proporciona una conexión."""

ConnectionReleaser = type[None]  # Actual: Callable[[Any], None]
"""Función que libera/devuelve una conexión."""

__all__: list[str] = [
    "RowOrNone",
    "Rows",
    "SchemaContext",
    "DDLStatement",
    "QueryParams",
    "ConnectionConfig",
    "ConnectionID",
    "ConnectionProvider",
    "ConnectionReleaser",
]
