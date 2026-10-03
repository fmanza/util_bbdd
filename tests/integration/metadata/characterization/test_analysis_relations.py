"""``analysis`` y ``get_foreign_keys``: relaciones del schema de prueba desde el snapshot (C2, E2).

Hasta E2 se comparaba con el camino tabla a tabla de ``get_foreign_keys``, cuyo SQL de PostgreSQL y SQL Server cruzaba
las columnas de las FK compuestas (H-20). Desde E2 ``get_foreign_keys`` también sale del snapshot: ambos se fijan contra
las relaciones que declara el schema.
"""

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


EXPECTED: set[tuple[str, ...]] = {
    (f"{PREFIX}child", f"{PREFIX}parent", "parent_id", "id", f"fk_{PREFIX}child_parent"),
    (f"{PREFIX}ref_composite", f"{PREFIX}composite", "a", "a", f"fk_{PREFIX}ref_composite"),
    (f"{PREFIX}ref_composite", f"{PREFIX}composite", "b", "b", f"fk_{PREFIX}ref_composite"),
}


def test_parent_index_from_snapshot(target: GoldenTarget) -> None:
    db_type, params = target.manager_args()
    with SyncDatabaseManager(db_type, params, use_pool=False) as mgr:
        index = DatabaseRelationshipGraphBase(mgr)._build_parent_relations_index("ctx")
    # SQLite no da nombres de FK por PRAGMA (vacíos en el snapshot): allí solo se comparan tablas y columnas
    with_names = target.engine != "sqlite"
    expected = EXPECTED if with_names else {r[:4] for r in EXPECTED}
    assert _relations(index, with_names=with_names) == expected


def test_get_foreign_keys_pairs_composite_columns(target: GoldenTarget) -> None:
    """H-20: las columnas de una FK compuesta se emparejan por posición (antes, producto cartesiano en PG/SQL Server)."""
    db_type, params = target.manager_args()
    with SyncDatabaseManager(db_type, params, use_pool=False) as mgr:
        (fk,) = mgr.get_foreign_keys(f"{PREFIX}ref_composite")
    assert fk.ref_table.lower() == f"{PREFIX}composite"
    assert [c.lower() for c in fk.columns] == ["a", "b"]
    assert [c.lower() for c in fk.ref_columns] == ["a", "b"]
