"""MatplotlibRelationshipGraph sobre un catálogo falso (backend Agg; se salta sin matplotlib/networkx)."""

from __future__ import annotations

import math

from collections.abc import Collection
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("networkx")

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import util_bbdd.analysis.matplotlib_graph as module  # noqa: E402

from util_bbdd.analysis.matplotlib_graph import MatplotlibRelationshipGraph  # noqa: E402
from util_bbdd.metadata.model import ALL_KINDS, ForeignKeyMeta, Kind, SchemaSnapshot, TableMeta  # noqa: E402

PARENT = "customers"
CHILDREN = ("orders", "../../evil/Ta ble")


class _Source:
    """Dos tablas hijas con FK a ``customers`` y una tabla sin relaciones."""

    db_type = "postgresql"

    def get_query_context_database(self) -> str:
        return "demo"

    def get_schema_metadata(self, schema: str | None = None, *, kinds: Collection[Kind] = ALL_KINDS) -> SchemaSnapshot:
        data: dict[Kind, tuple[Any, ...]] = {
            Kind.TABLES: (TableMeta(PARENT), *(TableMeta(child) for child in CHILDREN), TableMeta("lonely")),
            Kind.FOREIGN_KEYS: tuple(
                ForeignKeyMeta(child, f"fk_{index}", ("customer_id",), "demo", PARENT, ("id",))
                for index, child in enumerate(CHILDREN)
            ),
        }
        return SchemaSnapshot("postgresql", "demo", {kind: data.get(kind, ()) for kind in kinds})


@pytest.fixture
def graph() -> MatplotlibRelationshipGraph:
    return MatplotlibRelationshipGraph(_Source(), max_depth=1, direction="both")


def test_radial_layout_puts_the_root_in_the_centre(graph: MatplotlibRelationshipGraph) -> None:
    import networkx as nx

    g = nx.DiGraph()
    g.add_nodes_from([PARENT, "a", "b", "c"])

    pos = graph._create_radial_layout(g, PARENT)

    assert pos[PARENT] == (0.0, 0.0)
    assert all(math.isclose(math.hypot(*pos[node]), 3.0) for node in ("a", "b", "c"))


def test_paginated_graph_writes_one_svg_per_page_with_safe_names(
    graph: MatplotlibRelationshipGraph, tmp_path: Path
) -> None:
    files = graph.generate_matplotlib_graph_paginated(PARENT, tmp_path / "out", format="svg", max_subnodes=1)

    assert [f.name for f in files] == ["matplotlib_customers_page1.svg", "matplotlib_customers_page2.svg"]
    assert all(f.parent == (tmp_path / "out").resolve() and f.stat().st_size > 0 for f in files)
    assert "orders" in "".join(f.read_text(encoding="utf-8") for f in files)

    hostile = graph.generate_matplotlib_graph_paginated(CHILDREN[1], tmp_path / "out", format="svg")
    assert [f.name for f in hostile] == ["matplotlib_evil-ta-ble.svg"]  # S-04: no sale de output_dir


def test_all_tables_skips_tables_without_relations(graph: MatplotlibRelationshipGraph, tmp_path: Path) -> None:
    results = graph.generate_all_tables_graphs(tmp_path / "all", format="svg")

    assert set(results) == {PARENT, *CHILDREN}
    assert all(result["status"] == "success" and result["count"] == 1 for result in results.values())


def test_requires_matplotlib_and_networkx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "MATPLOTLIB_AVAILABLE", False)

    with pytest.raises(ImportError, match="Matplotlib/NetworkX"):
        MatplotlibRelationshipGraph(_Source())
