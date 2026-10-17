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
from .model import (
    ALL_KINDS,
    ColumnMeta,
    ForeignKeyMeta,
    IndexMeta,
    Kind,
    PrimaryKeyMeta,
    RoutineMeta,
    RoutineParameterMeta,
    SchemaSnapshot,
    TableMeta,
    UniqueMeta,
    ViewMeta,
)

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
    "VersionedCatalogDialect",
]


@dataclass(frozen=True, slots=True)
class CatalogQuery:
    """Consulta de un tipo de objeto para todo un schema.

    Attributes:
        sql: SQL con ``:schema`` (y ``:tables`` dentro de ``IN (...)`` si ``filterable``).
        filterable: Si admite limitar la lectura a unas tablas con ``:tables``.
        extra: Consultas adicionales del mismo tipo de objeto, con los mismos parámetros. Con ``extra``,
            ``CatalogDialect.parse`` recibe una lista con las filas de ``sql`` y de cada consulta de ``extra``, en ese
            orden. Para motores en los que unir vistas del catálogo en SQL es caro (MySQL/MariaDB, H-16).
    """

    sql: str
    filterable: bool = False
    extra: tuple[str, ...] = ()


@runtime_checkable
class CatalogDialect(Protocol):
    """Qué leer del catálogo de un motor y cómo convertirlo al modelo neutro (``metadata/<motor>/catalog.py``)."""

    name: str
    sqlalchemy_names: frozenset[str]

    def current_schema_sql(self) -> str:
        """SQL sin parámetros que devuelve el schema por defecto de la conexión."""
        ...

    def normalize_name(self, name: str) -> str:
        """Nombre de schema o tabla como lo guarda el catálogo (Oracle: ``scott`` → ``SCOTT``; entre comillas, literal).

        Args:
            name: Nombre tal como lo escribe el usuario.
        """
        ...

    def query(self, kind: Kind, *, filtered: bool = False) -> CatalogQuery | None:
        """Consulta de ``kind``; ``None`` si el motor no tiene ese tipo de objeto.

        Args:
            kind: Tipo de objeto a leer.
            filtered: Variante limitada a unas tablas (la fuente la pide cuando ``snapshot()`` recibe ``tables``).
        """
        ...

    def parse(self, kind: Kind, rows: Sequence[Sequence[Any]], schema: str) -> tuple[Any, ...]:
        """Filas de :meth:`query` → objetos del modelo (``metadata.model``).

        Args:
            kind: Tipo de objeto de las filas.
            rows: Filas devueltas por la consulta de :meth:`query`.
            schema: Schema leído (para los objetos que lo incluyen, como las claves foráneas).
        """
        ...


@runtime_checkable
class VersionedCatalogDialect(CatalogDialect, Protocol):
    """``CatalogDialect`` cuyo SQL depende de la versión del servidor (Oracle 11g sin ``ALL_TAB_IDENTITY_COLS``).

    Opcional: ``CatalogSource`` pregunta la versión una vez por fuente con :meth:`server_version_sql` y usa el dialecto
    que devuelva :meth:`for_server_version`. Los dialectos que no lo implementan se usan tal cual.
    """

    def server_version_sql(self) -> str:
        """SQL sin parámetros que devuelve la versión del servidor como texto (``11.2.0.4.0``)."""
        ...

    def for_server_version(self, version: tuple[int, ...]) -> CatalogDialect:
        """Dialecto para esa versión (``self`` si no hay variante)."""
        ...


@runtime_checkable
class CatalogExecutor(Protocol):
    """Ejecuta SQL de catálogo con parámetros ``:nombre`` y devuelve todas las filas como tuplas."""

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        """Ejecuta ``sql`` con ``params`` y devuelve todas las filas."""
        ...


@runtime_checkable
class AsyncCatalogExecutor(Protocol):
    """Variante async de :class:`CatalogExecutor`."""

    async def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        """Ejecuta ``sql`` con ``params`` y devuelve todas las filas."""
        ...


@runtime_checkable
class MetadataSource(Protocol):
    """Lectura de metadatos por lotes: una consulta por schema y tipo de objeto, con caché (ADR-003)."""

    def snapshot(
        self,
        schema: str | None = None,
        *,
        kinds: Collection[Kind] = ALL_KINDS,
        tables: Collection[str] | None = None,
    ) -> SchemaSnapshot:
        """Metadatos de ``schema`` (``None``: el de la conexión) para ``kinds``, opcionalmente solo de ``tables``."""
        ...

    def invalidate(self, schema: str | None = None, *, kinds: Collection[Kind] | None = None) -> None:
        """Descarta lo leído de ``schema`` y ``kinds`` (``None``: todo); tras un DDL propio."""
        ...


@runtime_checkable
class AsyncMetadataSource(Protocol):
    """Variante async de :class:`MetadataSource` (``invalidate`` no hace E/S y es síncrono)."""

    async def snapshot(
        self,
        schema: str | None = None,
        *,
        kinds: Collection[Kind] = ALL_KINDS,
        tables: Collection[str] | None = None,
    ) -> SchemaSnapshot:
        """Como :meth:`MetadataSource.snapshot`."""
        ...

    def invalidate(self, schema: str | None = None, *, kinds: Collection[Kind] | None = None) -> None:
        """Como :meth:`MetadataSource.invalidate`."""
        ...


@runtime_checkable
class SyncMetadataProvider(Protocol):
    """Contrato de lectura de metadatos en modo síncrono.

    Semántica de cada método: la de su homónimo en :class:`~util_bbdd.SyncDatabaseManager`, que lo cumple.
    """

    def get_tables(self) -> list[TableMeta]: ...
    def get_views(self) -> list[ViewMeta]: ...
    def get_routines(self) -> list[RoutineMeta]: ...
    def get_columns(self, tabla: str) -> list[ColumnMeta]: ...
    def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> list[RoutineParameterMeta]: ...
    def get_indices(self, tabla: str) -> list[IndexMeta]: ...
    def get_primary_keys(self, tabla: str) -> PrimaryKeyMeta | None: ...
    def get_foreign_keys(self, tabla: str) -> list[ForeignKeyMeta]: ...
    def get_unique_constraints(self, tabla: str) -> list[UniqueMeta]: ...


@runtime_checkable
class AsyncMetadataProvider(Protocol):
    """Contrato de lectura de metadatos en modo asíncrono.

    Semántica de cada método: la de su homónimo en :class:`~util_bbdd.AsyncDatabaseManager`, que lo cumple.
    """

    async def get_tables(self) -> list[TableMeta]: ...
    async def get_views(self) -> list[ViewMeta]: ...
    async def get_routines(self) -> list[RoutineMeta]: ...
    async def get_columns(self, tabla: str) -> list[ColumnMeta]: ...
    async def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> list[RoutineParameterMeta]: ...
    async def get_indices(self, tabla: str) -> list[IndexMeta]: ...
    async def get_primary_keys(self, tabla: str) -> PrimaryKeyMeta | None: ...
    async def get_foreign_keys(self, tabla: str) -> list[ForeignKeyMeta]: ...
    async def get_unique_constraints(self, tabla: str) -> list[UniqueMeta]: ...
