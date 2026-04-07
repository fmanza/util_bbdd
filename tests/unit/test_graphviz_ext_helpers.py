"""Tests unitarios de helpers del renderer Graphviz extendido."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from util_bbdd.analysis.base import (
    ColumnVisualizationMode,
    GraphDocument,
    GraphEdge,
    GraphLevel,
    GraphNode,
    HiddenLevelsSummary,
    LevelDirection,
    TableRelation,
    TableVisualType,
)
from util_bbdd.analysis.graphviz_ext import GraphvizRelationshipGraphExt


def _build_graph_instance() -> GraphvizRelationshipGraphExt:
    graph = object.__new__(GraphvizRelationshipGraphExt)
    graph.include_columns = True
    graph.show_data_types = True
    graph.max_columns = 2
    graph.orthogonal_edges = True
    graph.orthogonal_nodesep = 0.75
    graph.orthogonal_ranksep = 0.9
    graph.render_dpi = 300
    return graph


def test_create_configured_graph_uses_plain_shape_without_margin_for_html_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyDigraph:
        def __init__(self, **kwargs: str) -> None:
            self.kwargs = kwargs
            self.attr_calls: list[tuple[str, dict[str, str]]] = []

        def attr(self, scope: str, **kwargs: str) -> None:
            self.attr_calls.append((scope, kwargs))

    import util_bbdd.analysis.graphviz_ext as module

    monkeypatch.setattr(module, "GRAPHVIZ_AVAILABLE", True)
    monkeypatch.setattr(module, "graphviz", SimpleNamespace(Digraph=DummyDigraph))

    graph = _build_graph_instance()

    dot, is_raster, edge_label_font_size = graph._create_configured_graph(
        table_name="users",
        format="svg",
        show_columns=True,
    )

    assert dot.kwargs["engine"] == "dot"
    assert is_raster is False
    assert edge_label_font_size == "8"
    assert ("node", {"shape": "plain", "margin": "0", "fontname": "Arial", "fontsize": "10"}) in dot.attr_calls


def test_select_columns_for_table_caps_all_mode_to_configured_limit() -> None:
    graph = _build_graph_instance()
    graph.column_mode = ColumnVisualizationMode.ALL
    graph._get_table_columns_with_types = lambda table_name: [  # type: ignore[attr-defined]
        ("id", "integer"),
        ("customer_id", "integer"),
        ("created_at", "timestamp"),
    ]

    columns, hidden_count = graph._select_columns_for_table("users", {"customer_id"})

    assert columns == [("id", "integer"), ("customer_id", "integer")]
    assert hidden_count == 1


def test_build_table_html_label_truncates_text_and_reports_hidden_columns() -> None:
    graph = _build_graph_instance()
    graph.column_mode = ColumnVisualizationMode.ALL
    graph._get_table_columns_with_types = lambda table_name: [  # type: ignore[attr-defined]
        ("customer_identifier", "character varying(255)"),
        ("created_at", "timestamp without time zone"),
        ("status", "varchar(20)"),
    ]
    graph._is_primary_key = lambda table_name, column_name: False  # type: ignore[attr-defined]
    graph._is_unique_column = lambda table_name, column_name: False  # type: ignore[attr-defined]
    graph._get_table_label_styles = lambda is_raster: {  # type: ignore[attr-defined]
        "title_row_height": "40",
        "title_font_size": "10",
        "column_font_size": "9",
        "type_font_size": "8",
        "table_width": "240",
        "name_column_width": "160",
        "type_column_width": "80",
        "title_max_chars": "10",
        "column_name_max_chars": "8",
        "type_max_chars": "6",
    }

    html_label = graph._build_table_html_label(
        "table_name_demo",
        related_columns={"customer_identifier"},
        is_main=True,
        visual_type=TableVisualType.ASSOCIATION,
        is_raster=False,
    )

    assert 'WIDTH="240"' in html_label
    assert GraphvizRelationshipGraphExt.ASSOCIATION_TABLE_COLOR in html_label
    assert "table_n..." in html_label
    assert "custo..." in html_label
    assert "cha..." in html_label
    assert "... 1 columna(s) mas" in html_label


def test_get_table_label_styles_reduces_svg_baseline_but_preserves_raster_size() -> None:
    graph = _build_graph_instance()

    vector_styles = graph._get_table_label_styles(is_raster=False)
    raster_styles = graph._get_table_label_styles(is_raster=True)

    assert vector_styles["table_width"] == "180"
    assert vector_styles["name_column_width"] == "120"
    assert vector_styles["type_column_width"] == "60"
    assert vector_styles["title_max_chars"] == "21"
    assert vector_styles["column_name_max_chars"] == "18"
    assert vector_styles["type_max_chars"] == "13"

    assert raster_styles["table_width"] == "280"
    assert raster_styles["name_column_width"] == "185"
    assert raster_styles["type_column_width"] == "95"
    assert raster_styles["title_max_chars"] == "34"
    assert raster_styles["column_name_max_chars"] == "28"
    assert raster_styles["type_max_chars"] == "22"


def test_resolve_node_fill_color_uses_visual_type_palette() -> None:
    graph = _build_graph_instance()

    assert graph._resolve_node_fill_color(TableVisualType.ENTITY) == GraphvizRelationshipGraphExt.ENTITY_TABLE_COLOR
    assert (
        graph._resolve_node_fill_color(TableVisualType.ASSOCIATION)
        == GraphvizRelationshipGraphExt.ASSOCIATION_TABLE_COLOR
    )
    assert (
        graph._resolve_node_fill_color(TableVisualType.HIERARCHY) == GraphvizRelationshipGraphExt.HIERARCHY_TABLE_COLOR
    )


def test_build_table_html_label_keeps_root_accent_via_border_width() -> None:
    graph = _build_graph_instance()
    graph.column_mode = ColumnVisualizationMode.ALL
    graph._get_table_columns_with_types = lambda table_name: [("id", "integer")]  # type: ignore[attr-defined]
    graph._is_primary_key = lambda table_name, column_name: False  # type: ignore[attr-defined]
    graph._is_unique_column = lambda table_name, column_name: False  # type: ignore[attr-defined]

    root_label = graph._build_table_html_label(
        "users",
        related_columns={"id"},
        is_main=True,
        visual_type=TableVisualType.ENTITY,
        is_raster=False,
    )
    related_label = graph._build_table_html_label(
        "users",
        related_columns={"id"},
        is_main=False,
        visual_type=TableVisualType.ENTITY,
        is_raster=False,
    )

    assert 'TABLE BORDER="2"' in root_label
    assert 'BORDER="3"' in root_label
    assert 'TABLE BORDER="1"' in related_label
    assert 'BORDER="2"' in related_label


def test_graph_node_defaults_to_entity_visual_type() -> None:
    node = GraphNode(table_name="users")

    assert node.visual_type == TableVisualType.ENTITY


def test_build_edge_attributes_moves_cardinality_away_from_arrowheads() -> None:
    graph = _build_graph_instance()
    graph.show_constraint_name = False
    graph._determine_cardinality = lambda **kwargs: "1:N"  # type: ignore[attr-defined]

    edge = GraphEdge(
        relation=TableRelation(
            source_table="orders",
            target_table="customers",
            constraint_name="fk_orders_customers",
            source_column="customer_id",
            target_column="id",
        ),
        depth=1,
        direction=LevelDirection.OUTGOING,
    )

    attributes = graph._build_edge_attributes(edge=edge, edge_label_font_size="8")

    assert attributes["xlabel"] == "customer_id -> id"
    assert attributes["taillabel"] == "N"
    assert attributes["headlabel"] == "1"
    assert attributes["labelfontsize"] == "8"
    assert attributes["labeldistance"] == GraphvizRelationshipGraphExt.CARDINALITY_LABEL_DISTANCE
    assert attributes["labelangle"] == GraphvizRelationshipGraphExt.CARDINALITY_LABEL_ANGLE
    assert attributes["color"] == "#1D70B8"


def test_add_edges_to_graph_applies_cardinality_render_contract() -> None:
    class DummyDot:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict[str, str]]] = []

        def edge(self, source: str, target: str, **kwargs: str) -> None:
            self.calls.append((source, target, kwargs))

    graph = _build_graph_instance()
    graph.show_constraint_name = True
    graph._determine_cardinality = lambda **kwargs: "1:N"  # type: ignore[attr-defined]

    relation = TableRelation(
        source_table="orders",
        target_table="customers",
        constraint_name="fk_orders_customers",
        source_column="customer_id",
        target_column="id",
    )
    document = GraphDocument(
        root_table="orders",
        nodes={"orders": GraphNode(table_name="orders", is_root=True), "customers": GraphNode(table_name="customers")},
        levels=[],
        edges=[GraphEdge(relation=relation, depth=1, direction=LevelDirection.INCOMING)],
        relations=[relation],
        tables={"orders", "customers"},
        max_depth=1,
        direction=LevelDirection.BOTH,
        hidden_levels=HiddenLevelsSummary(),
        total_incoming_levels=1,
        total_outgoing_levels=1,
    )
    dot = DummyDot()

    graph._add_edges_to_graph(dot=dot, document=document, edge_label_font_size="8")

    assert len(dot.calls) == 1
    source, target, kwargs = dot.calls[0]
    assert source == "orders"
    assert target == "customers"
    assert kwargs["xlabel"] == "fk_orders_customers: customer_id -> id"
    assert kwargs["taillabel"] == "N"
    assert kwargs["headlabel"] == "1"
    assert kwargs["labeldistance"] == GraphvizRelationshipGraphExt.CARDINALITY_LABEL_DISTANCE
    assert kwargs["labelangle"] == GraphvizRelationshipGraphExt.CARDINALITY_LABEL_ANGLE
    assert kwargs["color"] == "#A61C00"


def test_generate_graphviz_level_graphs_ext_resolves_depth_by_group_direction(tmp_path: Path) -> None:
    graph = _build_graph_instance()

    def _build_doc(levels: list[GraphLevel]) -> GraphDocument:
        return GraphDocument(
            root_table="users",
            nodes={"users": GraphNode(table_name="users", is_root=True)},
            levels=levels,
            edges=[],
            relations=[],
            tables={"users"},
            max_depth=3,
            direction=LevelDirection.BOTH,
            hidden_levels=HiddenLevelsSummary(),
            total_incoming_levels=3,
            total_outgoing_levels=1,
        )

    outgoing_document = _build_doc(
        [
            GraphLevel(depth=1, direction=LevelDirection.OUTGOING, edges=[], tables={"users", "orders"}),
        ]
    )
    incoming_document_with_mixed_levels = _build_doc(
        [
            GraphLevel(depth=1, direction=LevelDirection.OUTGOING, edges=[], tables={"users", "orders"}),
            GraphLevel(depth=2, direction=LevelDirection.INCOMING, edges=[], tables={"users", "accounts"}),
        ]
    )
    root_document = _build_doc(
        [
            GraphLevel(depth=1, direction=LevelDirection.OUTGOING, edges=[], tables={"users", "orders"}),
            GraphLevel(depth=2, direction=LevelDirection.INCOMING, edges=[], tables={"users", "accounts"}),
        ]
    )

    graph._build_level_documents = lambda **kwargs: (  # type: ignore[method-assign]
        root_document,
        {
            LevelDirection.OUTGOING: [outgoing_document],
            LevelDirection.INCOMING: [incoming_document_with_mixed_levels],
        },
    )

    def _fake_generate(**kwargs: object) -> Path:
        output_file = kwargs["output_file"]
        assert isinstance(output_file, Path)
        return output_file.with_suffix(".svg")

    graph._generate_graphviz_graph_internal_ext = _fake_generate  # type: ignore[method-assign]

    results = graph.generate_graphviz_level_graphs_ext(table_name="users", output_dir=tmp_path, format="svg")

    assert results["outgoing"][0]["depth"] == 1
    assert str(results["outgoing"][0]["path"]).endswith("graphviz_ext_users_outgoing_level1.svg")
    assert results["incoming"][0]["depth"] == 2
    assert str(results["incoming"][0]["path"]).endswith("graphviz_ext_users_incoming_level2.svg")
    assert results["incoming"][0]["title"] == "Nivel 2"
