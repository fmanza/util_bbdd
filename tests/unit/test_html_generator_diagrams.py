"""Tests del payload HTML de diagramas por pestañas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from util_bbdd.doc.html_generator import HtmlGenerator


def test_build_diagram_tab_payload_groups_tabs_by_direction_and_level(tmp_path: Path) -> None:
    generator = HtmlGenerator(database="demo", headers={})
    output_dir = tmp_path / "site"
    graph_dir = output_dir / "graphs"
    graph_dir.mkdir(parents=True)

    outgoing_svg = graph_dir / "users_outgoing_level1.svg"
    incoming_svg = graph_dir / "users_incoming_level2.svg"
    svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><g class="node"><title>users</title></g></svg>'
    outgoing_svg.write_text(svg_content, encoding="utf-8")
    incoming_svg.write_text(svg_content, encoding="utf-8")

    tabs, flat_paths, summary = generator._build_diagram_tab_payload(
        table_name="users",
        generated_groups={
            "summary": {
                "max_depth": 3,
                "total_outgoing_levels": 1,
                "total_incoming_levels": 2,
                "hidden_outgoing_levels": 0,
                "hidden_incoming_levels": 1,
            },
            "outgoing": [{"depth": 1, "path": outgoing_svg, "title": "Nivel 1"}],
            "incoming": [{"depth": 2, "path": incoming_svg, "title": "Nivel 2"}],
        },
        output_dir=output_dir,
        navigation_links={"users": "../tables/users.html"},
    )

    assert len(tabs) == 2
    assert tabs[0]["direction"] == "outgoing"
    assert tabs[0]["items"][0]["depth"] == 1
    assert tabs[1]["direction"] == "incoming"
    assert tabs[1]["hidden_levels"] == 1
    assert flat_paths == ["graphs/users_outgoing_level1.svg", "graphs/users_incoming_level2.svg"]
    assert summary["max_depth"] == 3


def test_build_table_payload_includes_tabbed_diagram_metadata(tmp_path: Path) -> None:
    generator = HtmlGenerator(database="demo", headers={"COLUMNAS": []})
    output_dir = tmp_path / "site"
    output_dir.mkdir(parents=True)

    class _Provider:
        db_type = "postgresql"

        def get_columns(self, table_name: str) -> list[tuple[Any, ...]]:
            return []

        def get_primary_keys(self, table_name: str) -> list[str]:
            return []

        def get_foreign_keys(self, table_name: str) -> list[tuple[Any, ...]]:
            return []

        def get_unique_constraints(self, table_name: str) -> list[str]:
            return []

        def get_indices(self, table_name: str) -> list[tuple[Any, ...]]:
            return []

    class _GraphGenerator:
        def generate_graphviz_level_graphs_ext(self, **kwargs: Any) -> dict[str, Any]:
            graph_dir = Path(kwargs["output_dir"])
            graph_dir.mkdir(parents=True, exist_ok=True)
            outgoing = graph_dir / "users_outgoing_level1.svg"
            outgoing.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><g class="node"><title>users</title></g></svg>',
                encoding="utf-8",
            )
            return {
                "summary": {
                    "max_depth": 2,
                    "total_outgoing_levels": 1,
                    "total_incoming_levels": 0,
                    "hidden_outgoing_levels": 0,
                    "hidden_incoming_levels": 0,
                },
                "outgoing": [{"depth": 1, "path": outgoing, "title": "Nivel 1"}],
                "incoming": [],
            }

    payload = generator._build_table_payload(
        table_name="users",
        comentario="Usuarios",
        data_provider=_Provider(),
        section_flags=[False, False, False, False, False, False],
        include_diagrams=True,
        graph_generator=_GraphGenerator(),
        diagram_options={"output_dir": output_dir / "graphs", "max_depth": 2, "direction": "both"},
        output_dir=output_dir,
        svg_navigation_links={"users": "../tables/users.html"},
    )

    assert payload["diagram_summary"]["max_depth"] == 2
    assert len(payload["diagram_tabs"]) == 1
    assert payload["diagram_tabs"][0]["direction"] == "outgoing"
    assert payload["diagram_tabs"][0]["items"][0]["path"] == "graphs/users_outgoing_level1.svg"


def test_render_detail_page_writes_tabbed_diagram_markup(tmp_path: Path) -> None:
    generator = HtmlGenerator(database="demo", headers={"FK": [], "UNIQUE": [], "INDICES": []})
    detail_template, _, _ = generator._setup_templates(generator.default_template_file)
    output_file = tmp_path / "users.html"

    generator._render_detail_page(
        template=detail_template,
        output_file=output_file,
        entity_kind="tabla",
        entity={
            "name": "users",
            "comment": "Usuarios",
            "charset_collation": "",
            "ddl": None,
            "show_columnas": False,
            "columnas": {"headers": [], "rows": []},
            "show_columns_charset": False,
            "columns_charset": {"headers": [], "rows": []},
            "show_pk": False,
            "pk": None,
            "show_fk": False,
            "fk": None,
            "show_unicas": False,
            "unicas": None,
            "show_indices": False,
            "indices": None,
            "diagram_paths": [],
            "diagram_summary": {"max_depth": 2, "total_outgoing_levels": 1, "total_incoming_levels": 1},
            "diagram_tabs": [
                {
                    "group_id": "users-outgoing",
                    "direction": "outgoing",
                    "direction_label": "Salida",
                    "items": [
                        {
                            "tab_id": "users-outgoing-level-1",
                            "title": "Nivel 1",
                            "depth": 1,
                            "path": "graphs/users_outgoing_level1.svg",
                            "direction": "outgoing",
                        }
                    ],
                    "total_levels": 1,
                    "hidden_levels": 0,
                }
            ],
        },
        generated_at="2026-03-22 10:00:00",
        storage_report=None,
    )

    rendered = output_file.read_text(encoding="utf-8")
    assert 'data-diagram-group="users-outgoing"' in rendered
    assert 'data-tab-target="users-outgoing-level-1"' in rendered
    assert "Niveles salida: 1" in rendered
