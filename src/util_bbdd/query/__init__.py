"""Módulo query: Registro y resolución centralizada de queries SQL.

Proporciona abstracciones consolidadas para:
- Carga y acceso a queries (registry)
- Resolución y validación de queries (resolver)

Las queries se definen en `data/sql_queries.json` por tipo de BD.
"""

from .registry import QueryRegistry
from .resolver import QueryResolver

__all__: list[str] = [
    "QueryRegistry",
    "QueryResolver",
]
