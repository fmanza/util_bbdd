"""``CatalogSource`` contra servidores reales: dorado del snapshot y contraste con la extracción de ``migrate`` (A1+).

Para cada motor con ``CatalogDialect`` (``metadata.catalog_registry``):

- el snapshot completo del schema ``zz_gold_*`` se congela en ``tests/fixtures/metadata_golden/<motor>_snapshot.json``;
- se contrasta con el IR de ``migrate`` (otro camino de lectura): mismas columnas en orden con su nulabilidad, PK, FK
  con sus reglas e índices no-PK. Así el snapshot no solo es estable: coincide con lo que la librería ya leía;
- leer el schema completo cuesta una consulta por tipo de objeto, y una segunda lectura ninguna.

Mismos requisitos y regeneración que ``test_metadata_golden.py`` (``UTIL_BBDD_UPDATE_GOLDEN=1``).
"""

from __future__ import annotations

import dataclasses
import json
import os

from collections.abc import Iterator
from typing import Any

import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.catalog_registry import supported_catalog_engines
from util_bbdd.metadata.model import ALL_KINDS, SchemaSnapshot
from util_bbdd.metadata.source import CatalogSource

from ._schemas import PREFIX, GoldenTarget, build, drop, sqlite_path, targets
from .test_metadata_golden import _ORACLE_IDENTITY_SEQ, GOLDEN_DIR, _compare, _ir_snapshot

pytestmark = pytest.mark.integration


def _engine(target: GoldenTarget) -> Engine:
    if target.engine == "sqlite":
        return create_engine(f"sqlite:///{sqlite_path().as_posix()}")
    assert target.url_env
    return create_engine(os.environ[target.url_env])


@pytest.fixture(params=[t for t in targets() if t.engine in supported_catalog_engines()], ids=lambda t: t.engine)
def target(request: pytest.FixtureRequest) -> Iterator[GoldenTarget]:
    t: GoldenTarget = request.param
    if t.url_env and not os.environ.get(t.url_env):
        pytest.skip(f"{t.url_env} no definida")
    build(t)
    try:
        yield t
    finally:
        drop(t)


def _ours(item: Any) -> bool:
    routine = getattr(item, "routine", None)  # parámetros: cuenta su routine, no su nombre
    name = routine.name if routine is not None else getattr(item, "table", None) or item.name
    return str(name).lower().startswith(PREFIX)


def _serialize(snapshot: SchemaSnapshot) -> str:
    data = {
        kind.value: [dataclasses.asdict(item) for item in items if kind.value == "database" or _ours(item)]
        for kind, items in sorted(snapshot.data.items(), key=lambda kv: kv[0].value)
    }
    data.pop("database", None)  # versión del servidor: cambia con la imagen del contenedor
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True, default=str)
    return _ORACLE_IDENTITY_SEQ.sub("ISEQ$$_<n>", text)


def _comparable_from_snapshot(snapshot: SchemaSnapshot) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for table in snapshot.tables():
        if not _ours(table):
            continue
        name = table.name
        pk = snapshot.primary_key(name)
        out[name.lower()] = {
            "columns": [(c.name.lower(), c.nullable) for c in snapshot.columns(name)],
            "pk": [c.lower() for c in pk.columns] if pk else [],
            "fks": sorted(
                (
                    fk.name.lower(),
                    [c.lower() for c in fk.columns],
                    fk.ref_table.lower(),
                    [c.lower() for c in fk.ref_columns],
                    fk.on_delete.upper(),
                )
                for fk in snapshot.foreign_keys(name)
            ),  # fmt: skip
            "indexes": _without_pk_index(
                [(ix.name.lower(), [c.lower() for c in ix.columns], ix.unique) for ix in snapshot.indexes(name)],
                [c.lower() for c in pk.columns] if pk else [],
            ),
        }
    return out


def _without_pk_index(indexes: list[tuple[str, list[str], bool]], pk: list[str]) -> list[tuple[str, list[str], bool]]:
    """Índices sin el que respalda la PK: el IR de Oracle lo incluye y el de PostgreSQL no."""
    return sorted(ix for ix in indexes if not (ix[2] and ix[1] == pk))


def _comparable_from_ir(ir: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for t in ir["tables"]:
        out[t["name"].lower()] = {
            "columns": [(c["name"].lower(), c["nullable"]) for c in t["columns"]],
            "pk": [c.lower() for c in t["primary_key"]],
            "fks": sorted(
                (
                    f["name"].lower(),
                    [c.lower() for c in f["columns"]],
                    f["ref_table"].lower(),
                    [c.lower() for c in f["ref_columns"]],
                    f["on_delete"].upper(),
                )
                for f in t["foreign_keys"]
            ),  # fmt: skip
            "indexes": _without_pk_index(
                [(i["name"].lower(), [c.lower() for c in i["columns"]], i["unique"]) for i in t["indexes"]],
                [c.lower() for c in t["primary_key"]],
            ),
        }
    return out


def test_snapshot_matches_golden_and_migrate(target: GoldenTarget) -> None:
    engine = _engine(target)
    statements: list[str] = []

    def count(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        source = CatalogSource.from_engine(engine)
        snapshot = source.snapshot(target.schema)
        first_read = len(statements)
        source.snapshot(target.schema)
        assert len(statements) == first_read, "la segunda lectura debe salir de la caché"
        queries = [source.dialect.query(kind) for kind in ALL_KINDS]
        declared = sum(1 + len(q.extra) for q in queries if q is not None)  # una por tipo + las de ``extra``
        assert first_read == declared, f"{first_read} consultas; el dialecto declara {declared}"
    finally:
        event.remove(engine, "before_cursor_execute", count)
        engine.dispose()

    _compare(GOLDEN_DIR / f"{target.engine}_snapshot.json", _serialize(snapshot))

    if target.migrate_source:
        db_type, params = target.manager_args()
        with SyncDatabaseManager(db_type, params, use_pool=False) as mgr:
            ir = _ir_snapshot(target.engine, mgr, target.schema)
        assert _comparable_from_snapshot(snapshot) == _comparable_from_ir(ir)
