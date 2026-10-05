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

from ._paramstyle import ParamStyle, expand_lists, to_driver
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


class DbapiCatalogExecutor:
    """:class:`CatalogExecutor` sobre una conexión DB-API 2.0 (driver nativo: managers, JDBC de HSQLDB…).

    Traduce el SQL de catálogo (``:nombre``) al ``paramstyle`` del driver con :func:`_paramstyle.to_driver`.

    Args:
        connection: Conexión DB-API abierta (no se cierra aquí).
        paramstyle: ``paramstyle`` del módulo del driver (``named``, ``pyformat``, ``format``, ``qmark``, ``numeric``).
    """

    def __init__(self, connection: Any, paramstyle: ParamStyle) -> None:
        self.connection = connection
        self.paramstyle = paramstyle

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        driver_sql, args = to_driver(sql, params, self.paramstyle)
        cursor = self.connection.cursor()
        try:
            if args is None:
                cursor.execute(driver_sql)
            else:
                cursor.execute(driver_sql, args)
            return [tuple(row) for row in cursor.fetchall()]
        finally:
            cursor.close()


_MAX_ASSEMBLED = 32


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
        # Último SchemaSnapshot armado por (schema, kinds, tablas): se reutiliza mientras la caché devuelva los mismos
        # datos, para no reconstruir su índice por tabla en cada llamada (``get_columns(t)`` en bucle sería O(n²))
        self._assembled: dict[tuple[str, frozenset[Kind], frozenset[str] | None], SchemaSnapshot] = {}

    def _assemble(
        self, schema: str, data: dict[Kind, tuple[Any, ...]], selected: frozenset[str] | None
    ) -> SchemaSnapshot:
        key = (schema, frozenset(data), selected)
        previous = self._assembled.get(key)
        if previous is not None and all(previous.data[kind] is items for kind, items in data.items()):
            return previous
        snapshot = SchemaSnapshot(engine=self.dialect.name, schema=schema, data=data, tables_filter=selected)
        if len(self._assembled) >= _MAX_ASSEMBLED:
            self._assembled.clear()
        self._assembled[key] = snapshot
        return snapshot

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
        self._assembled.clear()


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
        self._version_resolved = False

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

    def _resolve_dialect(self) -> None:
        """Resuelve la variante del dialecto según la versión del servidor (p.ej. Oracle 11g vs 12c+).

        Ejecutado una sola vez al acceder al dialecto por primera vez. Si el dialecto implementa
        ``VersionedCatalogDialect``, consulta la versión del servidor y usa ``for_server_version()``
        para obtener la variante correcta. Si no implementa el protocolo, se usa tal cual.
        """
        if self._version_resolved:
            return
        self._version_resolved = True

        # Verificar si el dialecto implementa VersionedCatalogDialect (protocolo opcional)
        if not hasattr(self.dialect, "server_version_sql") or not hasattr(self.dialect, "for_server_version"):
            return  # Dialecto no versioned; usar tal cual

        version_sql = self.dialect.server_version_sql()
        rows = self.executor.fetch_all(version_sql, {})
        if not rows or not rows[0] or not rows[0][0]:
            return  # No se pudo leer versión; usar variante por defecto (12c+)

        # Parsear versión: "11.2.0.4.0" → (11, 2, 0, 4, 0)
        version_str = str(rows[0][0]).strip()
        try:
            version_tuple = tuple(int(x) for x in version_str.split("."))
        except (ValueError, AttributeError):
            return  # Formato inesperado; usar variante por defecto

        # Obtener la variante correcta según la versión
        resolved_dialect = self.dialect.for_server_version(version_tuple)
        self.dialect = resolved_dialect

    def current_schema(self) -> str:
        self._resolve_dialect()  # Lazy resolution
        if self._default_schema is None:
            rows = self.executor.fetch_all(self.dialect.current_schema_sql(), {})
            self._default_schema = str(rows[0][0])
        return self._default_schema

    def _load(self, kind: Kind, schema: str, tables: frozenset[str] | None) -> tuple[Any, ...]:
        self._resolve_dialect()
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
        return self._assemble(schema, data, selected)


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
        self._version_resolved = False

    async def current_schema(self) -> str:
        await self._resolve_dialect()  # Lazy resolution
        if self._default_schema is None:
            rows = await self.executor.fetch_all(self.dialect.current_schema_sql(), {})
            self._default_schema = str(rows[0][0])
        return self._default_schema

    async def _resolve_dialect(self) -> None:
        """Resuelve la variante del dialecto según la versión del servidor (p.ej. Oracle 11g vs 12c+).

        Ejecutado una sola vez al acceder al dialecto por primera vez. Si el dialecto implementa
        ``VersionedCatalogDialect``, consulta la versión del servidor y usa ``for_server_version()``
        para obtener la variante correcta. Si no implementa el protocolo, se usa tal cual.
        """
        if self._version_resolved:
            return
        self._version_resolved = True

        # Verificar si el dialecto implementa VersionedCatalogDialect (protocolo opcional)
        if not hasattr(self.dialect, "server_version_sql") or not hasattr(self.dialect, "for_server_version"):
            return  # Dialecto no versioned; usar tal cual

        version_sql = self.dialect.server_version_sql()
        rows = await self.executor.fetch_all(version_sql, {})
        if not rows or not rows[0] or not rows[0][0]:
            return  # No se pudo leer versión; usar variante por defecto (12c+)

        # Parsear versión: "11.2.0.4.0" → (11, 2, 0, 4, 0)
        version_str = str(rows[0][0]).strip()
        try:
            version_tuple = tuple(int(x) for x in version_str.split("."))
        except (ValueError, AttributeError):
            return  # Formato inesperado; usar variante por defecto

        # Obtener la variante correcta según la versión
        resolved_dialect = self.dialect.for_server_version(version_tuple)
        self.dialect = resolved_dialect

    async def _load(self, kind: Kind, schema: str, tables: frozenset[str] | None) -> tuple[Any, ...]:
        await self._resolve_dialect()
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
        return self._assemble(schema, data, selected)


__all__: list[str] = [
    "FILTER_MAX_TABLES",
    "AsyncCatalogSource",
    "CatalogSource",
    "DbapiCatalogExecutor",
    "SqlAlchemyCatalogExecutor",
]
