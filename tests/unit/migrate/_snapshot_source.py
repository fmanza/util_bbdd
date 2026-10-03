"""Fuente de metadatos falsa para los tests de ``migrate`` (los extractores leen el snapshot de ``metadata/``, C3).

``FakeSource`` cumple lo que usan los extractores de una ``MetadataSource`` (``snapshot`` e ``invalidate``) y
``fake_manager`` la expone como ``metadata_source``, igual que ``SyncDatabaseManager``. Los ``col``/``fk``/``index``…
construyen modelos neutros con los valores habituales para no repetir campos en cada test.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import Any
from unittest.mock import MagicMock

from util_bbdd.metadata.model import (
    ALL_KINDS,
    ColumnMeta,
    ForeignKeyMeta,
    IndexMeta,
    Kind,
    PrimaryKeyMeta,
    RoutineMeta,
    SchemaSnapshot,
    TableMeta,
    ViewMeta,
)

_KIND_OF: dict[type, Kind] = {
    TableMeta: Kind.TABLES,
    ViewMeta: Kind.VIEWS,
    ColumnMeta: Kind.COLUMNS,
    PrimaryKeyMeta: Kind.PRIMARY_KEYS,
    ForeignKeyMeta: Kind.FOREIGN_KEYS,
    IndexMeta: Kind.INDEXES,
    RoutineMeta: Kind.ROUTINES,
}


class FakeSource:
    """``MetadataSource`` en memoria: devuelve los objetos dados, del tipo pedido, para cualquier schema."""

    def __init__(self, engine: str, objects: Iterable[Any] = ()) -> None:
        self.engine = engine
        self.data: dict[Kind, list[Any]] = {}
        self.reads: list[frozenset[Kind]] = []
        self.invalidations: list[str | None] = []
        self.add(*objects)

    def add(self, *objects: Any) -> FakeSource:
        for obj in objects:
            self.data.setdefault(_KIND_OF[type(obj)], []).append(obj)
        return self

    def snapshot(
        self, schema: str | None = None, *, kinds: Collection[Kind] = ALL_KINDS, tables: Collection[str] | None = None
    ) -> SchemaSnapshot:
        self.reads.append(frozenset(kinds))
        return SchemaSnapshot(self.engine, schema or "", {k: tuple(self.data.get(k, ())) for k in kinds})

    def invalidate(self, schema: str | None = None, *, kinds: Collection[Kind] | None = None) -> None:
        self.invalidations.append(schema)


def fake_manager(engine: str, *objects: Any) -> MagicMock:
    """Manager simulado cuyo ``metadata_source`` es una :class:`FakeSource` con ``objects``."""
    manager = MagicMock()
    manager.metadata_source = FakeSource(engine, objects)
    return manager


def table(name: str, comment: str | None = None) -> TableMeta:
    return TableMeta(name, comment)


def col(
    table_name: str, name: str, ordinal: int, data_type: str, base_type: str | None = None, **kw: Any
) -> ColumnMeta:
    """Columna nulable con ``base_type`` = ``data_type`` sin modificadores salvo que se indique."""
    kw.setdefault("nullable", True)
    return ColumnMeta(table_name, name, ordinal, data_type, base_type or data_type.split("(")[0], **kw)


def pk(table_name: str, *columns: str, name: str | None = None) -> PrimaryKeyMeta:
    return PrimaryKeyMeta(table_name, name or f"pk_{table_name}", columns)


def fk(
    table_name: str,
    name: str,
    columns: tuple[str, ...],
    ref_table: str,
    ref_columns: tuple[str, ...],
    *,
    ref_schema: str = "s",
    on_delete: str = "NO ACTION",
    on_update: str = "NO ACTION",
) -> ForeignKeyMeta:
    return ForeignKeyMeta(table_name, name, columns, ref_schema, ref_table, ref_columns, on_delete, on_update)


def index(table_name: str, name: str, *columns: str, unique: bool = False, primary: bool = False) -> IndexMeta:
    return IndexMeta(table_name, name, columns, unique, primary)


def view(name: str, definition: str | None, comment: str | None = None, *, materialized: bool = False) -> ViewMeta:
    return ViewMeta(name, definition, comment, materialized)


def routine(name: str, routine_type: str, definition: str | None = None, **kw: Any) -> RoutineMeta:
    return RoutineMeta(name, routine_type, definition=definition, **kw)


__all__: list[str] = ["FakeSource", "col", "fake_manager", "fk", "index", "pk", "routine", "table", "view"]
