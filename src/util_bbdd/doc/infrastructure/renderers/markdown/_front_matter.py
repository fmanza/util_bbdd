"""Registro estructurado de cada objeto: lo publican el front matter de su página y ``catalog.json`` (ADR-006).

Sale del snapshot por lotes (ADR-003), no de las filas posicionales de las secciones: claves estables, sin depender de
las cabeceras de ``headers_config.json``. ``id`` es estable entre generaciones (``<kind>:<schema>.<nombre>``) para que
el código y otros documentos puedan referirse al objeto; ``hash`` cambia si cambia su estructura. Los dos son iguales
en el front matter y en ``catalog.json``.
"""

from __future__ import annotations

import hashlib
import json

from collections.abc import Collection
from typing import Any, Protocol

from .....metadata.model import ColumnMeta, Kind, RoutineMeta, SchemaSnapshot, ViewMeta

#: Tipos de objeto que el registro necesita del snapshot
RECORD_KINDS: frozenset[Kind] = frozenset(
    {
        Kind.COLUMNS,
        Kind.PRIMARY_KEYS,
        Kind.FOREIGN_KEYS,
        Kind.UNIQUES,
        Kind.INDEXES,
        Kind.VIEWS,
        Kind.ROUTINES,
    }
)

#: Claves del registro que van al front matter de cada página (columnas, índices y definiciones, a ``catalog.json``)
FRONT_MATTER_KEYS: tuple[str, ...] = (
    "id",
    "kind",
    "engine",
    "schema",
    "name",
    "title",
    "pk",
    "fk_out",
    "fk_in",
    "hash",
)


def front_matter_data(record: dict[str, Any]) -> dict[str, Any]:
    """Subconjunto del registro que se publica en el front matter."""
    return {key: record[key] for key in FRONT_MATTER_KEYS if key in record}


class SnapshotSource(Protocol):
    """Lo que se exige del ``data_provider``: la lectura por lotes de la sesión de documentación."""

    def get_schema_metadata(self, schema: str | None = None, *, kinds: Collection[Kind] = ...) -> SchemaSnapshot: ...


def sha256_text(text: str | None) -> str | None:
    """``sha256:<hex>`` de un texto (``None`` si no hay texto)."""
    if text is None:
        return None
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


class ObjectRecords:
    """Registros de tablas, vistas y rutinas a partir de un único snapshot.

    Args:
        snapshot: Snapshot con :data:`RECORD_KINDS` cargados.
    """

    def __init__(self, snapshot: SchemaSnapshot) -> None:
        self._snapshot = snapshot
        self.engine: str = snapshot.engine
        self.schema: str = snapshot.schema
        # FK entrantes por tabla referenciada (en minúsculas): ids de las tablas hijas, ordenados
        incoming: dict[str, set[str]] = {}
        for fk in snapshot.all_foreign_keys():
            incoming.setdefault(fk.ref_table.lower(), set()).add(self.object_id("table", fk.table))
        self._incoming: dict[str, list[str]] = {table: sorted(ids) for table, ids in incoming.items()}
        self._views: dict[str, ViewMeta] = {view.name.lower(): view for view in snapshot.views()}
        self._routines: dict[tuple[str, str], list[RoutineMeta]] = {}
        for routine in snapshot.routines():
            self._routines.setdefault((routine.routine_type.upper(), routine.name.lower()), []).append(routine)

    def object_id(self, kind: str, name: str, schema: str | None = None) -> str:
        """Id estable ``<kind>:<schema>.<nombre>``."""
        return f"{kind}:{schema or self.schema}.{name}"

    def _base(self, kind: str, name: str, comment: str) -> dict[str, Any]:
        return {
            "id": self.object_id(kind, name),
            "kind": kind,
            "engine": self.engine,
            "schema": self.schema,
            "name": name,
            "title": name,
            "comment": comment,
        }

    @staticmethod
    def _column(column: ColumnMeta) -> dict[str, Any]:
        return {
            "name": column.name,
            "ordinal": column.ordinal,
            "type": column.data_type,
            "nullable": column.nullable,
            "default": column.default,
            "comment": column.comment,
            "identity": column.identity,
            "generated": column.generated,
        }

    def table(self, name: str, comment: str) -> dict[str, Any]:
        """Registro de una tabla: columnas, PK, FK salientes (con su destino y acciones) y entrantes, únicas e índices."""
        snapshot = self._snapshot
        primary_key = snapshot.primary_key(name)
        record = self._base("table", name, comment)
        record |= {
            "columns": [self._column(c) for c in sorted(snapshot.columns(name), key=lambda c: c.ordinal)],
            "pk": {"name": primary_key.name, "columns": list(primary_key.columns)} if primary_key else None,
            "fk_out": [
                {
                    "name": fk.name,
                    "columns": list(fk.columns),
                    "ref": self.object_id("table", fk.ref_table, fk.ref_schema or None),
                    "ref_columns": list(fk.ref_columns),
                    "on_delete": fk.on_delete,
                    "on_update": fk.on_update,
                }
                for fk in sorted(snapshot.foreign_keys(name), key=lambda fk: (fk.name, fk.columns))
            ],
            "fk_in": self._incoming.get(name.lower(), []),
            "uniques": [
                {"name": u.name, "columns": list(u.columns)}
                for u in sorted(snapshot.uniques(name), key=lambda u: (u.name, u.columns))
            ],
            "indexes": [
                {
                    "name": i.name,
                    "columns": list(i.columns),
                    "unique": i.unique,
                    "primary": i.primary,
                    "method": i.method,
                }
                for i in sorted(snapshot.indexes(name), key=lambda i: (i.name, i.columns))
            ],
        }
        return _with_hash(record)

    def view(self, name: str, comment: str) -> dict[str, Any]:
        """Registro de una vista: columnas y hash de su definición."""
        view = self._views.get(name.lower())
        record = self._base("view", name, comment)
        record |= {
            "columns": [self._column(c) for c in sorted(self._snapshot.columns(name), key=lambda c: c.ordinal)],
            "definition_hash": sha256_text(view.definition if view else None),
        }
        return _with_hash(record)

    def routine(self, name: str, routine_type: str, comment: str) -> dict[str, Any]:
        """Registro de una rutina (``kind`` = tipo en minúsculas): firmas y hash de las definiciones.

        Las sobrecargas (mismo tipo y nombre) se reúnen en un registro, como su página.
        """
        overloads = sorted(self._routines.get((routine_type.upper(), name.lower()), []), key=lambda r: r.signature)
        record = self._base(routine_type.lower(), name, comment)
        record |= {
            "signatures": [r.signature for r in overloads],
            "definition_hash": sha256_text("\n".join(r.definition or "" for r in overloads)) if overloads else None,
        }
        return _with_hash(record)


def _with_hash(record: dict[str, Any]) -> dict[str, Any]:
    """Añade ``hash``: sha256 del registro en JSON canónico (sin el propio hash)."""
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**record, "hash": sha256_text(canonical)}


__all__: list[str] = [
    "FRONT_MATTER_KEYS",
    "RECORD_KINDS",
    "ObjectRecords",
    "SnapshotSource",
    "front_matter_data",
    "sha256_text",
]
