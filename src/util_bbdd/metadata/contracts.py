"""Contratos compartidos para proveedores de metadatos sync/async.

``SyncMetadataProvider``/``AsyncMetadataProvider``: contrato por tabla de los managers (se sustituye en el grupo C1).

``MetadataSource``/``AsyncMetadataSource``, ``CatalogDialect`` y ``CatalogExecutor``: contrato por lotes de ADR-003.
Un ``CatalogDialect`` sabe **qué** leer de un motor (una consulta por tipo de objeto, con ``:nombre``) y cómo convertir
sus filas al modelo neutro; un ``CatalogExecutor`` sabe **cómo** ejecutarla (driver nativo de los managers o
SQLAlchemy). ``MetadataSource`` los une con la caché y es lo único que ven los consumidores.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..results import Row, Rows
from .model import ALL_KINDS, Kind, SchemaSnapshot

__all__: list[str] = [
    "Row",
    "Rows",
    "SyncMetadataProvider",
    "AsyncMetadataProvider",
    "AsyncCatalogExecutor",
    "AsyncMetadataSource",
    "CatalogDialect",
    "CatalogExecutor",
    "CatalogQuery",
    "MetadataSource",
]


@dataclass(frozen=True, slots=True)
class CatalogQuery:
    """Consulta de un tipo de objeto para todo un schema.

    Attributes:
        sql: SQL con ``:schema`` (y ``:tables`` dentro de ``IN (...)`` si ``filterable``).
        filterable: Si admite limitar la lectura a unas tablas con ``:tables``.
    """

    sql: str
    filterable: bool = False


@runtime_checkable
class CatalogDialect(Protocol):
    """Qué leer del catálogo de un motor y cómo convertirlo al modelo neutro (``metadata/<motor>/catalog.py``)."""

    name: str
    sqlalchemy_names: frozenset[str]

    def current_schema_sql(self) -> str:
        """SQL sin parámetros que devuelve el schema por defecto de la conexión."""
        ...

    def query(self, kind: Kind, *, filtered: bool = False) -> CatalogQuery | None:
        """Consulta de ``kind``; ``None`` si el motor no tiene ese tipo de objeto."""
        ...

    def parse(self, kind: Kind, rows: Sequence[Sequence[Any]], schema: str) -> tuple[Any, ...]:
        """Filas de :meth:`query` → objetos del modelo (``metadata.model``)."""
        ...


@runtime_checkable
class CatalogExecutor(Protocol):
    """Ejecuta SQL de catálogo con parámetros ``:nombre`` y devuelve todas las filas como tuplas."""

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]: ...


@runtime_checkable
class AsyncCatalogExecutor(Protocol):
    """Variante async de :class:`CatalogExecutor`."""

    async def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]: ...


@runtime_checkable
class MetadataSource(Protocol):
    """Lectura de metadatos por lotes: una consulta por schema y tipo de objeto, con caché (ADR-003)."""

    def snapshot(
        self,
        schema: str | None = None,
        *,
        kinds: Collection[Kind] = ALL_KINDS,
        tables: Collection[str] | None = None,
    ) -> SchemaSnapshot: ...

    def invalidate(self, schema: str | None = None, *, kinds: Collection[Kind] | None = None) -> None: ...


@runtime_checkable
class AsyncMetadataSource(Protocol):
    """Variante async de :class:`MetadataSource` (``invalidate`` no hace E/S y es síncrono)."""

    async def snapshot(
        self,
        schema: str | None = None,
        *,
        kinds: Collection[Kind] = ALL_KINDS,
        tables: Collection[str] | None = None,
    ) -> SchemaSnapshot: ...

    def invalidate(self, schema: str | None = None, *, kinds: Collection[Kind] | None = None) -> None: ...


@runtime_checkable
class SyncMetadataProvider(Protocol):
    """Contrato de lectura de metadatos en modo síncrono."""

    def get_tables(self) -> Rows: ...
    def get_views(self) -> Rows: ...
    def get_routines(self) -> Rows: ...
    def get_columns(self, tabla: str) -> Rows: ...
    def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> Rows: ...
    def get_indices(self, tabla: str) -> Rows: ...
    def get_primary_keys(self, tabla: str) -> Rows: ...
    def get_foreign_keys(self, tabla: str) -> Rows: ...
    def get_unique_constraints(self, tabla: str) -> Rows: ...


@runtime_checkable
class AsyncMetadataProvider(Protocol):
    """Contrato de lectura de metadatos en modo asíncrono."""

    async def get_tables(self) -> Rows: ...
    async def get_views(self) -> Rows: ...
    async def get_routines(self) -> Rows: ...
    async def get_columns(self, tabla: str) -> Rows: ...
    async def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> Rows: ...
    async def get_indices(self, tabla: str) -> Rows: ...
    async def get_primary_keys(self, tabla: str) -> Rows: ...
    async def get_foreign_keys(self, tabla: str) -> Rows: ...
    async def get_unique_constraints(self, tabla: str) -> Rows: ...
