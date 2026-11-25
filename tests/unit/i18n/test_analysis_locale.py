"""Idioma de los textos fijos de los diagramas de ``analysis`` (5.10.0): pies, títulos, leyendas y avisos.

Los nombres de tablas y columnas no se traducen; con ``translator`` en inglés no queda texto en español.
"""

from __future__ import annotations

import shutil
import sqlite3

from collections.abc import Iterator
from pathlib import Path

import pytest

from _leftovers import spanish_hits

from util_bbdd import SyncDatabaseManager
from util_bbdd._core.i18n import Translator
from util_bbdd.analysis import MermaidRelationshipGraph

pytestmark = pytest.mark.unit

needs_dot = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz (dot) no está en el PATH")


@pytest.fixture
def manager(tmp_path: Path) -> Iterator[SyncDatabaseManager]:
    path = tmp_path / "demo.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, a1 TEXT, a2 TEXT, a3 TEXT, a4 TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id));
        CREATE TABLE items (id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(id));
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    con.close()
    with SyncDatabaseManager("sqlite", {"database": str(path)}, use_pool=False) as db:
        yield db


def _graphviz(manager: SyncDatabaseManager, translator: Translator | None = None, **kwargs: object) -> object:
    pytest.importorskip("graphviz")
    from util_bbdd.analysis import GraphvizRelationshipGraphExt

    return GraphvizRelationshipGraphExt(manager, translator=translator, **kwargs)  # type: ignore[arg-type]


def _svg_text(groups: dict[str, list[dict[str, object]]]) -> str:
    return "\n".join(
        bytes(item["bytes"]).decode("utf-8")  # type: ignore[call-overload]
        for key in ("outgoing", "incoming", "isolated")
        for item in groups[key]
    )


@needs_dot
def test_graphviz_level_graphs_in_english(manager: SyncDatabaseManager) -> None:
    graph = _graphviz(manager, Translator("en"), max_depth=1, column_mode="all", max_columns=1)

    related = graph.pipe_level_graphs_ext("items", format="svg")  # type: ignore[attr-defined]
    isolated = graph.pipe_level_graphs_ext("settings", format="svg", show_columns=False)  # type: ignore[attr-defined]

    assert [item["title"] for item in related["outgoing"]] == ["Level 1"]
    assert [item["title"] for item in isolated["isolated"]] == ["Table without relationships"]
    text = _svg_text(related) + _svg_text(isolated)
    assert "Visible depth: 1" in text and "Hidden outgoing: 1 level(s)" in text
    assert "more column(s)" in text
    assert spanish_hits(text) == [] and not any(w in text for w in ("Profundidad", "Nivel", "oculta", "columna"))


@needs_dot
def test_graphviz_defaults_to_spanish(manager: SyncDatabaseManager) -> None:
    graph = _graphviz(manager)

    related = graph.pipe_level_graphs_ext("orders", format="svg")  # type: ignore[attr-defined]
    isolated = graph.pipe_level_graphs_ext("settings", format="svg")  # type: ignore[attr-defined]

    assert [item["title"] for item in related["incoming"]] == ["Nivel 1"]
    assert [item["title"] for item in isolated["isolated"]] == ["Tabla sin relaciones"]
    assert "Profundidad visible: 1" in _svg_text(related)


@needs_dot
def test_graphviz_no_visible_columns_message(manager: SyncDatabaseManager) -> None:
    for locale, expected in (("es", "Sin columnas visibles"), ("en", "No visible columns")):
        graph = _graphviz(manager, Translator(locale), column_mode="relations")  # type: ignore[arg-type]
        assert expected in _svg_text(graph.pipe_level_graphs_ext("settings", format="svg"))  # type: ignore[attr-defined]


def test_mermaid_warnings_in_each_language(manager: SyncDatabaseManager) -> None:
    kwargs = {"max_chars": 80, "max_entities": 2}
    spanish = MermaidRelationshipGraph(manager, **kwargs).render_er("orders")  # type: ignore[arg-type]
    english = MermaidRelationshipGraph(manager, translator=Translator("en"), **kwargs).render_er("orders")  # type: ignore[arg-type]

    assert any(w.startswith("Diagrama partido") for w in spanish.warnings)
    assert any(w.startswith("Diagram split") for w in english.warnings)
    assert spanish_hits("\n".join(english.warnings + english.blocks)) == []


def test_matplotlib_title_and_legend_in_english(manager: SyncDatabaseManager, tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    pytest.importorskip("networkx")
    import matplotlib

    matplotlib.use("Agg")
    from util_bbdd.analysis import MatplotlibRelationshipGraph

    with matplotlib.rc_context({"svg.fonttype": "none"}):
        files = MatplotlibRelationshipGraph(manager, translator=Translator("en")).generate_matplotlib_graph_paginated(
            "orders", tmp_path, format="svg"
        )

    svg = "".join(f.read_text(encoding="utf-8") for f in files)
    assert "Multi-level relationships - Table: orders" in svg
    assert "Main Table" in svg and "FK Relationship" in svg
    assert spanish_hits(svg) == []
