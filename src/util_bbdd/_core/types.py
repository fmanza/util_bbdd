"""Tipos y aliases comunes para util_bbdd.

Este módulo centraliza las definiciones compartidas de tipos para
mantener consistencia entre contratos internos y API pública.
"""

from collections.abc import Callable
from typing import Any

# Tipos de resultados
Row = tuple[Any, ...]
"""Tupla que representa una fila materializada."""

RowOrNone = Row | None
"""Tupla de una fila o None si no hay resultados."""

Rows = list[Row]
"""Lista de tuplas representando filas de resultados."""

QueryResult = RowOrNone | Rows
"""Resultado singular o múltiple usado en contratos internos."""

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
ConnectionProvider = Callable[[], Any]
"""Función que proporciona una conexión."""

ConnectionReleaser = Callable[[Any], None]
"""Función que libera/devuelve una conexión."""

__all__: list[str] = [
    "Row",
    "RowOrNone",
    "Rows",
    "QueryResult",
    "SchemaContext",
    "DDLStatement",
    "QueryParams",
    "ConnectionConfig",
    "ConnectionID",
    "ConnectionProvider",
    "ConnectionReleaser",
]
