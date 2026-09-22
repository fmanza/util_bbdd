"""Contrato que ``analysis`` exige de la fuente de metadatos de relaciones.

``analysis/`` no importa ``managers/``: depende de este Protocol (Regla #6). Lo cumplen estructuralmente
``SyncDatabaseManager`` y el adaptador documental (``SyncDatabaseManagerAdapter``). Los parámetros son posicionales
(``/``) porque el manager llama ``tabla`` al argumento que el adaptador llama ``table_name``, y mypy no compara nombres.
"""

from __future__ import annotations

from typing import Protocol

from .._core.types import Rows
from ..metadata.cache import RelationshipMetadataCache

__all__: list[str] = ["RelationshipGraphSource"]


class RelationshipGraphSource(Protocol):
    """Lo que un generador de grafos de relaciones necesita para leer tablas, claves y la caché de relaciones."""

    @property
    def db_type(self) -> str: ...

    @property
    def relationship_cache(self) -> RelationshipMetadataCache: ...

    def get_query_context_database(self) -> str: ...

    def get_tables(self) -> Rows: ...

    def get_columns(self, table_name: str, /) -> Rows: ...

    def get_primary_keys(self, table_name: str, /) -> Rows: ...

    def get_foreign_keys(self, table_name: str, /) -> Rows: ...

    def get_unique_constraints(self, table_name: str, /) -> Rows: ...
