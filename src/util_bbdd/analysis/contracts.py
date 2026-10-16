"""Contrato que ``analysis`` exige de la fuente de metadatos de relaciones.

``analysis/`` no importa ``managers/``: depende de este Protocol (Regla #6). Lo cumplen estructuralmente
``SyncDatabaseManager``, el adaptador documental (``SyncDatabaseManagerAdapter``) y la sesión documental. Desde E2
(ADR-003) todo se lee del snapshot del schema (``get_schema_metadata``): una consulta por tipo de objeto, cacheada en la
fuente.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Protocol

from ..metadata.model import ALL_KINDS, Kind, SchemaSnapshot

__all__: list[str] = ["RelationshipGraphSource"]


class RelationshipGraphSource(Protocol):
    """Lo que un generador de grafos de relaciones necesita: el motor, el contexto y el catálogo por lotes."""

    @property
    def db_type(self) -> str: ...

    def get_query_context_database(self) -> str:
        """Schema (o base de datos) del que se dibujan las relaciones."""
        ...

    def get_schema_metadata(self, schema: str | None = None, *, kinds: Collection[Kind] = ALL_KINDS) -> SchemaSnapshot:
        """Metadatos por lotes (como ``SyncDatabaseManager.get_schema_metadata``)."""
        ...
