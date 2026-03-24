"""Tests unitarios de helpers del renderer Graphviz extendido."""

from __future__ import annotations

from util_bbdd.analysis.base import ColumnVisualizationMode, GraphNode, TableVisualType
from util_bbdd.analysis.graphviz_ext import GraphvizRelationshipGraphExt


def _build_graph_instance() -> GraphvizRelationshipGraphExt:
    graph = object.__new__(GraphvizRelationshipGraphExt)
    graph.include_columns = True
    graph.show_data_types = True
    graph.max_columns = 2
    return graph


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
