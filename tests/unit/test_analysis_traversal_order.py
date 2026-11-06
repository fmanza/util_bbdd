"""Recorrido del grafo de relaciones en orden estable entre procesos (condición C1, 5.3.0).

``_build_level_data`` y ``_collect_next_level_tables`` recorrían la frontera de cada nivel desde un ``set``: el orden de
las aristas de ``GraphDocument`` dependía de ``PYTHONHASHSEED`` (como los ciclos de G47). La documentación Markdown
necesita la misma salida en cada generación para versionarla con git.
"""

from __future__ import annotations

import os
import subprocess
import sys

from pathlib import Path
from typing import cast

import pytest

from _catalog_fakes import FakeCatalogManager, build_catalog

from util_bbdd.analysis.base import DatabaseRelationshipGraphBase
from util_bbdd.managers import SyncDatabaseManager

pytestmark = pytest.mark.unit

# Centro con 4 padres y 4 hijas; cada una con su propia tabla en el nivel 2 (varias tablas por frontera)
TABLES = ["centro", *(f"padre_{c}" for c in "dbca"), *(f"hija_{c}" for c in "dbca"), *(f"n2_{c}" for c in "dbcahgfe")]
FKS = {
    "centro": [(f"fk_centro_{c}", f"padre_{c}_id", f"padre_{c}", "id") for c in "dbca"],
    **{f"hija_{c}": [(f"fk_hija_{c}", "centro_id", "centro", "id")] for c in "dbca"},
    **{f"padre_{c}": [(f"fk_padre_{c}", "n2_id", f"n2_{c}", "id")] for c in "dbca"},
    **{f"n2_{c}": [(f"fk_n2_{c}", "hija_id", f"hija_{d}", "id")] for c, d in zip("hgfe", "dbca", strict=True)},
}

_SCRIPT = f"""
import sys
sys.path.insert(0, {str(Path(__file__).parent)!r})
from _catalog_fakes import FakeCatalogManager, build_catalog
from util_bbdd.analysis.base import DatabaseRelationshipGraphBase
graph = DatabaseRelationshipGraphBase(FakeCatalogManager(data=build_catalog(tables={TABLES!r}, fk_by_table={FKS!r})))
doc = graph.build_graph_document("centro", max_depth=2, direction="both")
print([(e.relation.source_table, e.relation.target_table, e.depth, e.direction.value) for e in doc.edges])
print(list(doc.nodes), doc.total_incoming_levels, doc.total_outgoing_levels)
"""


def _graph() -> DatabaseRelationshipGraphBase:
    manager = FakeCatalogManager(data=build_catalog(tables=TABLES, fk_by_table=FKS))
    return DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))


def test_level_edges_follow_sorted_frontier() -> None:
    doc = _graph().build_graph_document("centro", max_depth=2, direction="both")

    level2_out = [e.relation.target_table for e in doc.edges if e.depth == 2 and e.direction.value == "outgoing"]
    level2_in = [e.relation.source_table for e in doc.edges if e.depth == 2 and e.direction.value == "incoming"]
    assert level2_out == [f"n2_{c}" for c in "abcd"]
    # n2_e → hija_a, n2_g → hija_b, n2_f → hija_c, n2_h → hija_d: el orden de la frontera (hija_a…hija_d)
    assert level2_in == ["n2_e", "n2_g", "n2_f", "n2_h"]


def test_graph_document_is_the_same_with_any_hash_seed() -> None:
    outputs = set()
    for seed in ("1", "2", "3", "4", "5", "6"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", _SCRIPT], env=env, capture_output=True, text=True, check=True, timeout=60
        )
        outputs.add(result.stdout.strip())

    assert len(outputs) == 1
