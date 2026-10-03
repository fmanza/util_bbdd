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

from ..metadata.ddl import routine_ddl, view_ddl
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


def _routines(snapshot: SchemaSnapshot, name: str, routine_type: str) -> list[RoutineMeta]:
    wanted_type = str(routine_type or "").upper()
    folded = name.casefold()
    return [r for r in snapshot.routines() if r.name.casefold() == folded and r.routine_type == wanted_type]


def _view(snapshot: SchemaSnapshot, name: str) -> ViewMeta | None:
    folded = name.casefold()
    return next((v for v in snapshot.views() if v.name.casefold() == folded), None)


def _charset(database: DatabaseMeta | None) -> dict[str, Any]:
    if database is None:
        return {}
    return {key: value for key, value in (("charset", database.charset), ("collation", database.collation)) if value}


class SyncCatalogFacade:
    """``get_*`` de metadatos de ``SyncDatabaseManager`` (la clase aporta ``get_schema_metadata``)."""

    get_schema_metadata: Callable[..., SchemaSnapshot]

    def _snapshot(self, *kinds: Kind) -> SchemaSnapshot:
        return self.get_schema_metadata(kinds=frozenset(kinds))

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


class AsyncCatalogFacade:
    """``get_*`` de metadatos de ``AsyncDatabaseManager`` (la clase aporta ``get_schema_metadata``)."""

    get_schema_metadata: Callable[..., Awaitable[SchemaSnapshot]]

    async def _snapshot(self, *kinds: Kind) -> SchemaSnapshot:
        return await self.get_schema_metadata(kinds=frozenset(kinds))

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


__all__: list[str] = ["AsyncCatalogFacade", "SyncCatalogFacade"]
