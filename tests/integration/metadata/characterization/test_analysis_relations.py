"""``analysis``: el índice de relaciones entrantes desde el snapshot (C2) = el de ``get_foreign_keys`` tabla a tabla."""

from __future__ import annotations

import os

from collections.abc import Iterator

import pytest

from util_bbdd import SyncDatabaseManager
from util_bbdd.analysis.base import DatabaseRelationshipGraphBase

from ._schemas import PREFIX, GoldenTarget, build, drop, targets

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", params=targets(), ids=lambda t: t.engine)
def target(request: pytest.FixtureRequest) -> Iterator[GoldenTarget]:
    t: GoldenTarget = request.param
    if t.url_env and not os.environ.get(t.url_env):
        pytest.skip(f"{t.url_env} no definida")
    build(t)
    try:
        yield t
    finally:
        drop(t)


def _relations(index: dict, *, with_names: bool) -> set[tuple[str, ...]]:
    return {
        (r.source_table.lower(), r.target_table.lower(), r.source_column.lower(), r.target_column.lower())
        + ((r.constraint_name.lower(),) if with_names else ())
        for relations in index.values()
        for r in relations
        if r.source_table.lower().startswith(PREFIX)
    }


def test_parent_index_from_snapshot_matches_per_table(target: GoldenTarget) -> None:
    db_type, params = target.manager_args()
    with SyncDatabaseManager(db_type, params, use_pool=False) as mgr:
        graph = DatabaseRelationshipGraphBase(mgr)
        batched = graph._build_parent_relations_index("ctx")
        graph._relations_snapshot = lambda: None  # type: ignore[method-assign]  # fuerza el camino tabla a tabla
        legacy = graph._build_parent_relations_index("ctx")
    # SQLite no da nombres de FK por PRAGMA (vacíos en el snapshot): allí solo se comparan tablas y columnas
    with_names = target.engine != "sqlite"
    new, old = _relations(batched, with_names=with_names), _relations(legacy, with_names=with_names)
    assert new, "el schema de prueba tiene FK"
    assert new <= old
    # H-20: el SQL heredado de PostgreSQL y SQL Server no empareja columnas por posición en FK compuestas
    # (producto cartesiano); el snapshot sí. Lo sobrante del camino tabla a tabla son solo esos cruces.
    assert all(r[0] == "zz_gold_ref_composite" and r[2] != r[3] for r in old - new)
    assert bool(old - new) == (target.engine in {"postgresql", "sqlserver"})
