"""Lecturas de metadatos de los managers sobre el snapshot de ``metadata/`` (E2 de ADR-003).

Los ``get_*`` de los managers devuelven modelos neutros (``TableMeta``, ``ColumnMeta``, ``ForeignKeyMeta``…) iguales en
todos los motores, en lugar de tuplas con forma distinta por motor leídas con una consulta por tabla. Cada tipo de
objeto se lee una vez para todo el schema (``get_schema_metadata``) y se sirve desde la caché del manager hasta
``clear_cache()``.

Los nombres de tabla, vista y routine se buscan sin distinguir mayúsculas (Oracle ``EMP`` frente a ``emp``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .._core.exceptions import QueryNotFoundError
from ..metadata.ddl import mysql_table_ddl, native_table_ddl, native_table_ddl_sql, routine_ddl, view_ddl
from ..metadata.model import (
    ColumnMeta,
    DatabaseMeta,
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
from ..metadata.storage import aread_storage_inventory, read_storage_inventory, storage_query


def _routines(snapshot: SchemaSnapshot, name: str, routine_type: str) -> list[RoutineMeta]:
    wanted_type = str(routine_type or "").upper()
    folded = name.casefold()
    return [r for r in snapshot.routines() if r.name.casefold() == folded and r.routine_type == wanted_type]


def _view(snapshot: SchemaSnapshot, name: str) -> ViewMeta | None:
    folded = name.casefold()
    return next((v for v in snapshot.views() if v.name.casefold() == folded), None)


_MYSQL = frozenset({"mysql", "mariadb"})


def _columns_charset(engine: str, columns: tuple[ColumnMeta, ...]) -> list[tuple[str, str | None, str | None]]:
    """``(columna, charset, collation)`` de las columnas con collation propia (en MySQL/MariaDB, el charset es el
    prefijo de la collation: ``utf8mb4_bin`` → ``utf8mb4``)."""
    return [
        (c.name, c.collation.split("_", 1)[0] if engine in _MYSQL else None, c.collation)
        for c in columns
        if c.collation
    ]


def _ddl_cache(manager: Any) -> dict[tuple[str, str], str]:
    cache: dict[tuple[str, str], str] = manager.__dict__.setdefault("_table_ddl_cache", {})
    return cache


def _storage_sql(engine: str, query_name: str) -> str:
    sql = storage_query(engine, query_name)
    if sql is None:
        raise QueryNotFoundError(f"El motor '{engine}' no tiene la consulta de almacenamiento '{query_name}'")
    return sql


def _charset(database: DatabaseMeta | None) -> dict[str, Any]:
    if database is None:
        return {}
    return {key: value for key, value in (("charset", database.charset), ("collation", database.collation)) if value}


class SyncCatalogFacade:
    """``get_*`` de metadatos de ``SyncDatabaseManager`` (la clase aporta ``get_schema_metadata``)."""

    db_type: str
    get_schema_metadata: Callable[..., SchemaSnapshot]
    metadata_source: Any

    def _snapshot(self, *kinds: Kind, schema: str | None = None) -> SchemaSnapshot:
        return self.get_schema_metadata(schema, kinds=frozenset(kinds))

    def get_tables(self) -> list[TableMeta]:
        """Tablas del schema del contexto de metadatos (nombre, comentario y, en MySQL/MariaDB, collation)."""
        return list(self._snapshot(Kind.TABLES).tables())

    def get_views(self) -> list[ViewMeta]:
        """Vistas del schema con su definición."""
        return list(self._snapshot(Kind.VIEWS).views())

    def get_routines(self) -> list[RoutineMeta]:
        """Funciones y procedures del schema (en Oracle, también packages y sus miembros ``PKG.MIEMBRO``)."""
        return list(self._snapshot(Kind.ROUTINES).routines())

    def get_columns(self, tabla: str) -> list[ColumnMeta]:
        """Columnas de una tabla o vista, en orden."""
        return list(self._snapshot(Kind.COLUMNS).columns(tabla))

    def get_primary_keys(self, tabla: str) -> PrimaryKeyMeta | None:
        """Clave primaria de la tabla (columnas en orden de la clave) o ``None``."""
        return self._snapshot(Kind.PRIMARY_KEYS).primary_key(tabla)

    def get_foreign_keys(self, tabla: str) -> list[ForeignKeyMeta]:
        """Claves foráneas de la tabla (columnas emparejadas por posición)."""
        return list(self._snapshot(Kind.FOREIGN_KEYS).foreign_keys(tabla))

    def get_unique_constraints(self, tabla: str) -> list[UniqueMeta]:
        """Restricciones ``UNIQUE`` de la tabla."""
        return list(self._snapshot(Kind.UNIQUES).uniques(tabla))

    def get_indices(self, tabla: str) -> list[IndexMeta]:
        """Índices de la tabla (incluido el de la PK, marcado ``primary``)."""
        return list(self._snapshot(Kind.INDEXES).indexes(tabla))

    def get_view_ddl(self, vista: str) -> str:
        """``CREATE VIEW`` de la vista (``""`` si no existe o no se puede leer su definición)."""
        return view_ddl(_view(self._snapshot(Kind.VIEWS), vista), vista)

    def get_routine_ddl(self, rutina: str, tipo_rutina: str) -> str:
        """Definición completa de la routine; con sobrecargas, la primera."""
        found = _routines(self._snapshot(Kind.ROUTINES), rutina, tipo_rutina)
        return routine_ddl(found[0] if found else None)

    def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> list[RoutineParameterMeta]:
        """Parámetros de la routine en orden (con sobrecargas, los de todas, cada uno con su ``routine``)."""
        snapshot = self._snapshot(Kind.ROUTINES, Kind.ROUTINE_PARAMETERS)
        return [p for r in _routines(snapshot, rutina, tipo_rutina) for p in snapshot.routine_parameters(r.key)]

    def get_database_metadata(self) -> DatabaseMeta | None:
        """Versión del servidor, juego de caracteres y collation por defecto."""
        return self._snapshot(Kind.DATABASE).database()

    def get_database_version(self) -> str:
        """Versión del servidor (``"Unknown"`` si no se puede leer)."""
        database = self.get_database_metadata()
        return database.version if database else "Unknown"

    def get_database_charset_collation(self) -> dict[str, Any]:
        """``{"charset": …, "collation": …}`` de la base de datos (claves presentes solo si el motor las da)."""
        return _charset(self.get_database_metadata())

    def get_ddl(self, tabla: str, *, schema: str | None = None) -> str:
        """``CREATE TABLE`` de la tabla (``""`` si no existe); cacheado hasta ``clear_cache()``.

        MySQL/MariaDB lo construyen desde el snapshot (columnas y PK); el resto lo lee del motor tabla a tabla
        (``metadata.ddl``).

        Args:
            tabla: Tabla.
            schema: Schema de la tabla; por defecto el contexto de metadatos del manager (4.1.0).
        """
        if self.db_type in _MYSQL:
            snapshot = self._snapshot(Kind.COLUMNS, Kind.PRIMARY_KEYS, schema=schema)
            return mysql_table_ddl(tabla, snapshot.columns(tabla), snapshot.primary_key(tabla))
        source = self.metadata_source
        schema = source.dialect.normalize_name(schema) if schema else source.current_schema()
        cache = _ddl_cache(self)
        if (schema, tabla) not in cache:
            sql = native_table_ddl_sql(self.db_type)
            rows = source.executor.fetch_all(sql, {"schema": schema, "table_name": tabla}) if sql else []
            cache[(schema, tabla)] = native_table_ddl(rows)
        return cache[(schema, tabla)]

    def get_columns_charset_collation(
        self, tabla: str, *, schema: str | None = None
    ) -> list[tuple[str, str | None, str | None]]:
        """``(columna, charset, collation)`` de las columnas con collation distinta de la de la base de datos.

        Args:
            tabla: Tabla.
            schema: Schema de la tabla; por defecto el contexto de metadatos del manager (4.1.0).
        """
        return _columns_charset(self.db_type, self._snapshot(Kind.COLUMNS, schema=schema).columns(tabla))

    def get_storage_rows(self, query_name: str, **params: Any) -> list[tuple[Any, ...]]:
        """Filas de una consulta de almacenamiento de ``metadata.storage`` (``schema`` por defecto: el del contexto).

        Raises:
            QueryNotFoundError: Si el motor no tiene esa consulta.
        """
        sql = _storage_sql(self.db_type, query_name)
        source = self.metadata_source
        params.setdefault("schema", source.current_schema())
        return [tuple(row) for row in source.executor.fetch_all(sql, params)]

    def get_storage_inventory(self, tablespace: str | None = None) -> dict[str, Any]:
        """Inventario de almacenamiento (``primary``, ``temp_tablespaces``…; ver ``metadata.storage``).

        Raises:
            ValueError: Sin ``tablespace`` en Oracle o PostgreSQL.
        """
        source = self.metadata_source
        return read_storage_inventory(source.executor.fetch_all, self.db_type, source.current_schema(), tablespace)


class AsyncCatalogFacade:
    """``get_*`` de metadatos de ``AsyncDatabaseManager`` (la clase aporta ``get_schema_metadata``)."""

    db_type: str
    get_schema_metadata: Callable[..., Awaitable[SchemaSnapshot]]
    metadata_source: Any

    async def _snapshot(self, *kinds: Kind, schema: str | None = None) -> SchemaSnapshot:
        return await self.get_schema_metadata(schema, kinds=frozenset(kinds))

    async def get_tables(self) -> list[TableMeta]:
        """Ver :meth:`SyncCatalogFacade.get_tables`."""
        return list((await self._snapshot(Kind.TABLES)).tables())

    async def get_views(self) -> list[ViewMeta]:
        """Ver :meth:`SyncCatalogFacade.get_views`."""
        return list((await self._snapshot(Kind.VIEWS)).views())

    async def get_routines(self) -> list[RoutineMeta]:
        """Ver :meth:`SyncCatalogFacade.get_routines`."""
        return list((await self._snapshot(Kind.ROUTINES)).routines())

    async def get_columns(self, tabla: str) -> list[ColumnMeta]:
        """Ver :meth:`SyncCatalogFacade.get_columns`."""
        return list((await self._snapshot(Kind.COLUMNS)).columns(tabla))

    async def get_primary_keys(self, tabla: str) -> PrimaryKeyMeta | None:
        """Ver :meth:`SyncCatalogFacade.get_primary_keys`."""
        return (await self._snapshot(Kind.PRIMARY_KEYS)).primary_key(tabla)

    async def get_foreign_keys(self, tabla: str) -> list[ForeignKeyMeta]:
        """Ver :meth:`SyncCatalogFacade.get_foreign_keys`."""
        return list((await self._snapshot(Kind.FOREIGN_KEYS)).foreign_keys(tabla))

    async def get_unique_constraints(self, tabla: str) -> list[UniqueMeta]:
        """Ver :meth:`SyncCatalogFacade.get_unique_constraints`."""
        return list((await self._snapshot(Kind.UNIQUES)).uniques(tabla))

    async def get_indices(self, tabla: str) -> list[IndexMeta]:
        """Ver :meth:`SyncCatalogFacade.get_indices`."""
        return list((await self._snapshot(Kind.INDEXES)).indexes(tabla))

    async def get_view_ddl(self, vista: str) -> str:
        """Ver :meth:`SyncCatalogFacade.get_view_ddl`."""
        return view_ddl(_view(await self._snapshot(Kind.VIEWS), vista), vista)

    async def get_routine_ddl(self, rutina: str, tipo_rutina: str) -> str:
        """Ver :meth:`SyncCatalogFacade.get_routine_ddl`."""
        found = _routines(await self._snapshot(Kind.ROUTINES), rutina, tipo_rutina)
        return routine_ddl(found[0] if found else None)

    async def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> list[RoutineParameterMeta]:
        """Ver :meth:`SyncCatalogFacade.get_routine_parameters`."""
        snapshot = await self._snapshot(Kind.ROUTINES, Kind.ROUTINE_PARAMETERS)
        return [p for r in _routines(snapshot, rutina, tipo_rutina) for p in snapshot.routine_parameters(r.key)]

    async def get_database_metadata(self) -> DatabaseMeta | None:
        """Ver :meth:`SyncCatalogFacade.get_database_metadata`."""
        return (await self._snapshot(Kind.DATABASE)).database()

    async def get_database_version(self) -> str:
        """Ver :meth:`SyncCatalogFacade.get_database_version`."""
        database = await self.get_database_metadata()
        return database.version if database else "Unknown"

    async def get_database_charset_collation(self) -> dict[str, Any]:
        """Ver :meth:`SyncCatalogFacade.get_database_charset_collation`."""
        return _charset(await self.get_database_metadata())

    async def get_ddl(self, tabla: str, *, schema: str | None = None) -> str:
        """Ver :meth:`SyncCatalogFacade.get_ddl`."""
        if self.db_type in _MYSQL:
            snapshot = await self._snapshot(Kind.COLUMNS, Kind.PRIMARY_KEYS, schema=schema)
            return mysql_table_ddl(tabla, snapshot.columns(tabla), snapshot.primary_key(tabla))
        source = self.metadata_source
        schema = source.dialect.normalize_name(schema) if schema else await source.current_schema()
        cache = _ddl_cache(self)
        if (schema, tabla) not in cache:
            sql = native_table_ddl_sql(self.db_type)
            rows = await source.executor.fetch_all(sql, {"schema": schema, "table_name": tabla}) if sql else []
            cache[(schema, tabla)] = native_table_ddl(rows)
        return cache[(schema, tabla)]

    async def get_columns_charset_collation(
        self, tabla: str, *, schema: str | None = None
    ) -> list[tuple[str, str | None, str | None]]:
        """Ver :meth:`SyncCatalogFacade.get_columns_charset_collation`."""
        return _columns_charset(self.db_type, (await self._snapshot(Kind.COLUMNS, schema=schema)).columns(tabla))

    async def get_storage_rows(self, query_name: str, **params: Any) -> list[tuple[Any, ...]]:
        """Ver :meth:`SyncCatalogFacade.get_storage_rows`."""
        sql = _storage_sql(self.db_type, query_name)
        source = self.metadata_source
        params.setdefault("schema", await source.current_schema())
        return [tuple(row) for row in await source.executor.fetch_all(sql, params)]

    async def get_storage_inventory(self, tablespace: str | None = None) -> dict[str, Any]:
        """Ver :meth:`SyncCatalogFacade.get_storage_inventory`."""
        source = self.metadata_source
        return await aread_storage_inventory(
            source.executor.fetch_all, self.db_type, await source.current_schema(), tablespace
        )


__all__: list[str] = ["AsyncCatalogFacade", "SyncCatalogFacade"]
