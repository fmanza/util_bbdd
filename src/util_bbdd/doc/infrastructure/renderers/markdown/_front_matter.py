"""Registro estructurado de cada objeto para el front matter (y, en el grupo C, para ``catalog.json``).

Sale del snapshot por lotes (ADR-003), no de las filas posicionales de las secciones: claves estables, sin depender de
las cabeceras de ``headers_config.json``. ``id`` es estable entre generaciones (``<kind>:<schema>.<nombre>``) para que
el código y otros documentos puedan referirse al objeto; ``hash`` cambia si cambia su estructura.
"""

from __future__ import annotations

import hashlib
import json

from collections.abc import Collection
from typing import Any, Protocol

from .....metadata.model import Kind, SchemaSnapshot

#: Tipos de objeto que el registro necesita del snapshot
RECORD_KINDS: frozenset[Kind] = frozenset({Kind.COLUMNS, Kind.PRIMARY_KEYS, Kind.FOREIGN_KEYS, Kind.UNIQUES})

#: Claves del registro que van al front matter de cada página (las columnas y el comentario, a ``catalog.json``)
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

    def object_id(self, kind: str, name: str, schema: str | None = None) -> str:
        """Id estable ``<kind>:<schema>.<nombre>``."""
        return f"{kind}:{schema or self.schema}.{name}"

    def table(self, name: str, comment: str) -> dict[str, Any]:
        """Registro de una tabla: columnas, PK, FK salientes (con su destino) y entrantes."""
        primary_key = self._snapshot.primary_key(name)
        record: dict[str, Any] = {
            "id": self.object_id("table", name),
            "kind": "table",
            "engine": self.engine,
            "schema": self.schema,
            "name": name,
            "title": name,
            "comment": comment,
            "columns": [
                {"name": c.name, "type": c.data_type, "nullable": c.nullable} for c in self._snapshot.columns(name)
            ],
            "pk": list(primary_key.columns) if primary_key else [],
            "fk_out": [
                {
                    "name": fk.name,
                    "columns": list(fk.columns),
                    "ref": self.object_id("table", fk.ref_table, fk.ref_schema or None),
                    "ref_columns": list(fk.ref_columns),
                }
                for fk in sorted(self._snapshot.foreign_keys(name), key=lambda fk: (fk.name, fk.columns))
            ],
            "fk_in": self._incoming.get(name.lower(), []),
            "uniques": sorted([list(u.columns) for u in self._snapshot.uniques(name)]),
        }
        return _with_hash(record)

    def view(self, name: str, comment: str) -> dict[str, Any]:
        """Registro de una vista: columnas."""
        record: dict[str, Any] = {
            "id": self.object_id("view", name),
            "kind": "view",
            "engine": self.engine,
            "schema": self.schema,
            "name": name,
            "title": name,
            "comment": comment,
            "columns": [
                {"name": c.name, "type": c.data_type, "nullable": c.nullable} for c in self._snapshot.columns(name)
            ],
        }
        return _with_hash(record)

    def routine(self, name: str, routine_type: str, comment: str) -> dict[str, Any]:
        """Registro de una rutina (``kind`` = tipo en minúsculas: ``procedure``, ``function``…)."""
        kind = routine_type.lower()
        record: dict[str, Any] = {
            "id": self.object_id(kind, name),
            "kind": kind,
            "engine": self.engine,
            "schema": self.schema,
            "name": name,
            "title": name,
            "comment": comment,
        }
        return _with_hash(record)


def _with_hash(record: dict[str, Any]) -> dict[str, Any]:
    """Añade ``hash``: sha256 del registro en JSON canónico (sin el propio hash)."""
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**record, "hash": f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"}


__all__: list[str] = ["FRONT_MATTER_KEYS", "RECORD_KINDS", "ObjectRecords", "SnapshotSource", "front_matter_data"]
