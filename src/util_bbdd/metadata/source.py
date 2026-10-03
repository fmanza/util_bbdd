"""``CatalogSource``: lectura de metadatos por lotes con caché (implementación de ``MetadataSource``, ADR-003).

Cada tipo de objeto (:class:`~util_bbdd.metadata.model.Kind`) se lee con **una** consulta por schema y se guarda en la
:class:`~util_bbdd.metadata.snapshot_cache.SnapshotCache`; los consumidores que preguntan tabla a tabla leen del
snapshot sin volver al catálogo. Con ``tables=`` se limita la lectura a unas pocas tablas (``bulk`` con una tabla en un
schema de miles); por encima de :data:`FILTER_MAX_TABLES` se lee el schema completo.

Example:
    >>> source = CatalogSource.from_engine(engine)
    >>> snapshot = source.snapshot("ventas", kinds={Kind.TABLES, Kind.COLUMNS, Kind.FOREIGN_KEYS})
    >>> {fk.ref_table for fk in snapshot.all_foreign_keys()}
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from functools import partial
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from ._paramstyle import expand_lists
from .catalog_registry import get_catalog_dialect
from .contracts import AsyncCatalogExecutor, CatalogDialect, CatalogExecutor
from .model import ALL_KINDS, TABLE_SCOPED_KINDS, Kind, SchemaSnapshot
from .snapshot_cache import CacheKey, SnapshotCache

#: Por encima de este nº de tablas pedidas, se lee el schema completo (una consulta) en vez de filtrar con ``IN``.
FILTER_MAX_TABLES = 50


def _table_of(item: Any) -> str:
    return str(getattr(item, "table", None) or item.name)


class SqlAlchemyCatalogExecutor:
    """:class:`CatalogExecutor` sobre un ``Engine`` (una conexión por consulta) o una ``Connection`` abierta."""

    def __init__(self, bind: Engine | Connection) -> None:
        self.bind = bind

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        expanded, flat = expand_lists(sql, params)
        statement = text(expanded)
        if isinstance(self.bind, Connection):
            return [tuple(row) for row in self.bind.execute(statement, flat).all()]
        with self.bind.connect() as conn:
            return [tuple(row) for row in conn.execute(statement, flat).all()]


class _SourceBase:
    def __init__(
        self,
        dialect: CatalogDialect,
        *,
        source_id: str,
        cache: SnapshotCache | None = None,
        default_schema: str | None = None,
    ) -> None:
        self.dialect = dialect
        self.source_id = source_id
        self.cache = cache if cache is not None else SnapshotCache()
        self._default_schema = default_schema

    def _plan(
        self, kinds: Collection[Kind], tables: Collection[str] | None
    ) -> tuple[list[Kind], frozenset[str] | None]:
        wanted = sorted(frozenset(kinds), key=lambda k: k.value)
        selected = frozenset(self.dialect.normalize_name(t) for t in tables) if tables is not None else None
        if selected is not None and len(selected) > FILTER_MAX_TABLES:
            selected = None
        return wanted, selected

    def _key(self, schema: str, kind: Kind, tables: frozenset[str] | None) -> CacheKey:
        return (self.source_id, schema, kind, tables)

    def _from_full(self, schema: str, kind: Kind, tables: frozenset[str]) -> tuple[Any, ...] | None:
        full = self.cache.get(self._key(schema, kind, None))
        if full is None:
            return None
        return tuple(item for item in full if _table_of(item) in tables)

    def _request(
        self, kind: Kind, schema: str, tables: frozenset[str] | None
    ) -> tuple[tuple[str, ...], dict[str, Any]] | None:
        """Consultas (la principal y las de ``extra``) y parámetros para leer ``kind``; ``None`` si el motor no lo tiene."""
        query = self.dialect.query(kind, filtered=tables is not None)
        if query is None:
            return None
        params: dict[str, Any] = {"schema": schema}
        if tables is not None and query.filterable:
            params["tables"] = sorted(tables)
        return (query.sql, *query.extra), params

    def _finish(
        self, kind: Kind, results: list[list[tuple[Any, ...]]], schema: str, tables: frozenset[str] | None
    ) -> tuple:
        rows: Any = results[0] if len(results) == 1 else results  # con ``extra``, parse recibe todas las listas
        items = self.dialect.parse(kind, rows, schema)
        query = self.dialect.query(kind, filtered=tables is not None)
        if tables is not None and query is not None and not query.filterable:
            items = tuple(item for item in items if _table_of(item) in tables)
        return items

    def invalidate(self, schema: str | None = None, *, kinds: Collection[Kind] | None = None) -> None:
        """Descarta lo leído (tras DDL propio: ``migrate``, ``dump``, ``bulk.maintenance_scope``)."""
        self.cache.invalidate(self.source_id, self.dialect.normalize_name(schema) if schema else None, kinds)


class CatalogSource(_SourceBase):
    """:class:`~util_bbdd.metadata.contracts.MetadataSource` síncrona.

    Args:
        dialect: Qué leer del motor (``get_catalog_dialect(db_type)``).
        executor: Cómo ejecutarlo (driver nativo de un manager o :class:`SqlAlchemyCatalogExecutor`).
        source_id: Identifica la base de datos en la caché (p. ej. la URL sin contraseña).
        cache: Caché compartible entre fuentes; por defecto una propia.
        default_schema: Schema cuando ``snapshot()`` no recibe uno; si es ``None`` se pregunta al motor.
    """

    def __init__(
        self,
        dialect: CatalogDialect,
        executor: CatalogExecutor,
        *,
        source_id: str,
        cache: SnapshotCache | None = None,
        default_schema: str | None = None,
    ) -> None:
        super().__init__(dialect, source_id=source_id, cache=cache, default_schema=default_schema)
        self.executor = executor

    @classmethod
    def from_engine(
        cls, engine: Engine, *, cache: SnapshotCache | None = None, default_schema: str | None = None
    ) -> CatalogSource:
        """Fuente sobre un ``Engine`` de SQLAlchemy (dialecto resuelto por ``engine.dialect.name``)."""
        return cls(
            get_catalog_dialect(engine.dialect.name),
            SqlAlchemyCatalogExecutor(engine),
            source_id=engine.url.render_as_string(hide_password=True),
            cache=cache,
            default_schema=default_schema,
        )

    def current_schema(self) -> str:
        if self._default_schema is None:
            rows = self.executor.fetch_all(self.dialect.current_schema_sql(), {})
            self._default_schema = str(rows[0][0])
        return self._default_schema

    def _load(self, kind: Kind, schema: str, tables: frozenset[str] | None) -> tuple[Any, ...]:
        request = self._request(kind, schema, tables)
        if request is None:
            return ()
        sqls, params = request
        return self._finish(kind, [self.executor.fetch_all(sql, params) for sql in sqls], schema, tables)

    def snapshot(
        self,
        schema: str | None = None,
        *,
        kinds: Collection[Kind] = ALL_KINDS,
        tables: Collection[str] | None = None,
    ) -> SchemaSnapshot:
        """Metadatos de ``schema`` para ``kinds``: una consulta por tipo de objeto no cacheado."""
        schema = self.dialect.normalize_name(schema) if schema else self.current_schema()
        wanted, selected = self._plan(kinds, tables)
        data: dict[Kind, tuple[Any, ...]] = {}
        for kind in wanted:
            scoped = selected if kind in TABLE_SCOPED_KINDS else None
            if scoped is not None:
                cached = self._from_full(schema, kind, scoped)
                if cached is not None:
                    data[kind] = cached
                    continue
            data[kind] = self.cache.get_or_load(
                self._key(schema, kind, scoped), partial(self._load, kind, schema, scoped)
            )
        return SchemaSnapshot(engine=self.dialect.name, schema=schema, data=data, tables_filter=selected)


class AsyncCatalogSource(_SourceBase):
    """:class:`~util_bbdd.metadata.contracts.AsyncMetadataSource`: igual que :class:`CatalogSource` con E/S async."""

    def __init__(
        self,
        dialect: CatalogDialect,
        executor: AsyncCatalogExecutor,
        *,
        source_id: str,
        cache: SnapshotCache | None = None,
        default_schema: str | None = None,
    ) -> None:
        super().__init__(dialect, source_id=source_id, cache=cache, default_schema=default_schema)
        self.executor = executor

    async def current_schema(self) -> str:
        if self._default_schema is None:
            rows = await self.executor.fetch_all(self.dialect.current_schema_sql(), {})
            self._default_schema = str(rows[0][0])
        return self._default_schema

    async def _load(self, kind: Kind, schema: str, tables: frozenset[str] | None) -> tuple[Any, ...]:
        request = self._request(kind, schema, tables)
        if request is None:
            return ()
        sqls, params = request
        return self._finish(kind, [await self.executor.fetch_all(sql, params) for sql in sqls], schema, tables)

    async def snapshot(
        self,
        schema: str | None = None,
        *,
        kinds: Collection[Kind] = ALL_KINDS,
        tables: Collection[str] | None = None,
    ) -> SchemaSnapshot:
        schema = self.dialect.normalize_name(schema) if schema else await self.current_schema()
        wanted, selected = self._plan(kinds, tables)
        data: dict[Kind, tuple[Any, ...]] = {}
        for kind in wanted:
            scoped = selected if kind in TABLE_SCOPED_KINDS else None
            if scoped is not None:
                cached = self._from_full(schema, kind, scoped)
                if cached is not None:
                    data[kind] = cached
                    continue
            data[kind] = await self.cache.aget_or_load(
                self._key(schema, kind, scoped), partial(self._load, kind, schema, scoped)
            )
        return SchemaSnapshot(engine=self.dialect.name, schema=schema, data=data, tables_filter=selected)


__all__: list[str] = ["FILTER_MAX_TABLES", "AsyncCatalogSource", "CatalogSource", "SqlAlchemyCatalogExecutor"]
