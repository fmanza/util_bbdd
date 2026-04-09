"""Tests del payload HTML de diagramas por pestañas."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from util_bbdd.doc.infrastructure.renderers.html_generator import HtmlGenerator


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
    assert tabs[0]["visible_levels"] == 1
    assert tabs[0]["direction_help"] == "Relaciones de salida hacia tablas hijas o dependientes de la tabla actual."
    assert tabs[0]["items"][0]["depth"] == 1
    assert tabs[0]["items"][0]["short_title"] == "Nivel 1"
    assert tabs[1]["direction"] == "incoming"
    assert tabs[1]["hidden_levels"] == 1
    assert tabs[1]["has_hidden_levels"] is True
    assert tabs[1]["items"][0]["aria_label"] == "Entrada Nivel 2 de users"
    assert flat_paths == ["graphs/users_outgoing_level1.svg", "graphs/users_incoming_level2.svg"]
    assert summary["max_depth"] == 3
    assert summary["visible_outgoing_levels"] == 1
    assert summary["visible_incoming_levels"] == 1
    assert summary["has_hidden_incoming_levels"] is True
    assert summary["has_any_hidden_levels"] is True


def test_build_diagram_tab_payload_normalizes_incoming_order_and_labels(tmp_path: Path) -> None:
    generator = HtmlGenerator(database="demo", headers={})
    output_dir = tmp_path / "site"
    graph_dir = output_dir / "graphs"
    graph_dir.mkdir(parents=True)

    incoming_level_1 = graph_dir / "users_incoming_level1.svg"
    incoming_level_2 = graph_dir / "users_incoming_level2.svg"
    svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><g class="node"><title>users</title></g></svg>'
    incoming_level_1.write_text(svg_content, encoding="utf-8")
    incoming_level_2.write_text(svg_content, encoding="utf-8")

    tabs, flat_paths, _ = generator._build_diagram_tab_payload(
        table_name="users",
        generated_groups={
            "summary": {
                "max_depth": 5,
                "total_outgoing_levels": 0,
                "total_incoming_levels": 2,
                "hidden_outgoing_levels": 0,
                "hidden_incoming_levels": 0,
            },
            "outgoing": [],
            "incoming": [
                {"depth": 2, "path": incoming_level_2, "title": "Nivel 1"},
                {"depth": 1, "path": incoming_level_1, "title": "Nivel 1"},
            ],
        },
        output_dir=output_dir,
        navigation_links={"users": "../tables/users.html"},
    )

    assert len(tabs) == 1
    assert tabs[0]["direction"] == "incoming"
    assert [item["depth"] for item in tabs[0]["items"]] == [1, 2]
    assert [item["title"] for item in tabs[0]["items"]] == ["Nivel 1", "Nivel 2"]
    assert [item["short_title"] for item in tabs[0]["items"]] == ["Nivel 1", "Nivel 2"]
    assert [item["aria_label"] for item in tabs[0]["items"]] == [
        "Entrada Nivel 1 de users",
        "Entrada Nivel 2 de users",
    ]
    assert flat_paths == ["graphs/users_incoming_level1.svg", "graphs/users_incoming_level2.svg"]


def test_build_diagram_legend_payload_matches_current_contract() -> None:
    generator = HtmlGenerator(database="demo", headers={})

    legend = generator._build_diagram_legend_payload()

    assert legend["title"] == "Leyenda visual"
    assert legend["direction_items"][0]["label"] == "Salida"
    assert legend["direction_items"][0]["swatch"] == "#1D70B8"
    assert legend["direction_items"][1]["label"] == "Entrada"
    assert legend["table_type_items"][0]["label"] == "Entidad"
    assert legend["table_type_items"][0]["swatch"] == "#CFE8FF"
    assert legend["table_type_items"][1]["label"] == "Asociación"
    assert legend["table_type_items"][2]["label"] == "Jerarquía"
    assert legend["cardinality_items"][0]["marker"] == "1"
    assert legend["cardinality_items"][1]["marker"] == "N"
    assert legend["cardinality_items"][2]["marker"] == "M"
    assert legend["relation_type_items"][0]["label"] == "FK"
    assert "clave foránea" in legend["relation_type_items"][0]["description"]
    assert "tipología visual heurística" in legend["notes"][1].lower()
    assert "cardinalidad" in legend["notes"][0].lower()


def test_build_view_payload_exposes_excluded_diagram_policy_when_diagrams_are_enabled() -> None:
    generator = HtmlGenerator(database="demo", headers={"COLUMNAS": []})

    class _Provider:
        db_type = "postgresql"

        def get_columns(self, table_name: str) -> list[tuple[Any, ...]]:
            return []

    payload = generator._build_view_payload(
        view_name="v_users",
        comentario="Vista usuarios",
        data_provider=_Provider(),
        section_flags=[False, False],
        include_diagrams=True,
        diagram_options={"view_policy": "exclude"},
    )

    assert payload["diagram_policy"]["state"] == "exclude"
    assert payload["diagram_policy"]["title"] == "Política de diagramado de vistas"
    assert "no se incluyen" in payload["diagram_policy"]["label"].lower()
    assert "v_users" in payload["diagram_policy"]["description"]


def test_render_detail_page_writes_view_diagram_policy_notice(tmp_path: Path) -> None:
    generator = HtmlGenerator(database="demo", headers={})
    detail_template, _, _ = generator._setup_templates(generator.default_template_file)
    output_file = tmp_path / "v_users.html"

    generator._render_detail_page(
        template=detail_template,
        output_file=output_file,
        entity_kind="vista",
        entity={
            "name": "v_users",
            "comment": "Vista usuarios",
            "ddl": None,
            "show_columnas": False,
            "columnas": {"headers": [], "rows": []},
            "show_columns_charset": False,
            "columns_charset": {"headers": [], "rows": []},
            "diagram_policy": {
                "state": "exclude",
                "title": "Política de diagramado de vistas",
                "label": "Las vistas no se incluyen en el diagrama relacional enriquecido.",
                "description": "La vista v_users se documenta con su DDL y columnas, pero no participa en el grafo de relaciones generado para tablas.",
                "reasons": [
                    "El renderer actual de relaciones trabaja sobre claves foráneas entre tablas y no modela vistas como nodos del grafo.",
                ],
                "notes": [
                    "Si en una versión futura analysis incorpora soporte real para vistas, esta política podrá ampliarse.",
                ],
            },
        },
        generated_at="2026-03-24 10:00:00",
        storage_report=None,
    )

    rendered = output_file.read_text(encoding="utf-8")
    assert "Política de diagramado de vistas" in rendered
    assert "Las vistas no se incluyen en el diagrama relacional enriquecido." in rendered
    assert "La vista v_users se documenta con su DDL y columnas" in rendered
    assert "no modela vistas como nodos del grafo" in rendered


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
    assert payload["diagram_summary"]["visible_outgoing_levels"] == 1
    assert payload["diagram_summary"]["has_any_hidden_levels"] is False
    assert len(payload["diagram_tabs"]) == 1
    assert payload["diagram_tabs"][0]["direction"] == "outgoing"
    assert (
        payload["diagram_tabs"][0]["direction_help"]
        == "Relaciones de salida hacia tablas hijas o dependientes de la tabla actual."
    )
    assert payload["diagram_legend"]["table_type_items"][1]["label"] == "Asociación"
    assert payload["diagram_legend"]["relation_type_items"][0]["label"] == "FK"
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
            "diagram_summary": {
                "max_depth": 2,
                "total_outgoing_levels": 1,
                "total_incoming_levels": 1,
                "visible_outgoing_levels": 1,
                "visible_incoming_levels": 0,
                "has_hidden_outgoing_levels": True,
                "has_hidden_incoming_levels": False,
                "has_any_hidden_levels": True,
                "outgoing_hidden_help": "Salida oculta: niveles de tablas hijas o dependientes que existen en el grafo, pero no se muestran por el límite de profundidad visible.",
                "incoming_hidden_help": "Entrada oculta: niveles de tablas padre o referenciadoras que existen en el grafo, pero no se muestran por el límite de profundidad visible.",
            },
            "diagram_legend": {
                "title": "Leyenda visual",
                "direction_items": [
                    {
                        "label": "Salida",
                        "swatch": "#1D70B8",
                        "description": "Aristas salientes hacia tablas hijas o dependientes visibles en el diagrama.",
                    },
                    {
                        "label": "Entrada",
                        "swatch": "#A61C00",
                        "description": "Aristas entrantes desde tablas padre o referenciadoras visibles en el diagrama.",
                    },
                ],
                "table_type_items": [
                    {
                        "label": "Entidad",
                        "swatch": "#CFE8FF",
                        "description": "Tabla de negocio general que no encaja en las heurísticas de asociación o jerarquía.",
                    },
                    {
                        "label": "Asociación",
                        "swatch": "#D8F3DC",
                        "description": "Tabla puente detectada por varias FKs y, cuando aplica, PK compuesta basada en columnas relacionales.",
                    },
                    {
                        "label": "Jerarquía",
                        "swatch": "#FFE5C2",
                        "description": "Tabla con autorreferencia que representa relaciones padre-hijo dentro de la misma entidad.",
                    },
                ],
                "cardinality_items": [
                    {"marker": "1", "description": "Un registro relacionado."},
                    {"marker": "N", "description": "Muchos registros relacionados."},
                    {"marker": "M", "description": "Muchos registros en relaciones de tabla intermedia."},
                ],
                "relation_type_items": [
                    {
                        "label": "FK",
                        "description": "Tipo de relación soportado hoy por el renderer de diagramas: clave foránea.",
                    }
                ],
                "notes": [
                    "Los marcadores de cardinalidad se muestran separados de la arista para mejorar la legibilidad.",
                    "Los colores de tabla representan una tipología visual heurística del nodo, no una taxonomía absoluta del modelo de datos.",
                    "La leyenda de tipos de relación podrá ampliarse cuando analysis exponga más tipos reales además de FK.",
                ],
            },
            "diagram_viewer": {
                "title": "Controles del visor",
                "help": "Ctrl + rueda para zoom",
                "tips": [
                    "Usa las pestañas por nivel para aislar relaciones.",
                ],
                "status_ready": "Listo para navegar",
                "status_dragging": "Moviendo diagrama",
                "status_zoom_prefix": "Zoom",
                "min_zoom": 0.5,
                "max_zoom": 3.0,
                "zoom_step": 0.25,
                "pan_step": 140,
                "initial_zoom": 1.0,
                "wheel_zoom_requires_ctrl": True,
                "drag_pan_enabled": True,
            },
            "diagram_tabs": [
                {
                    "group_id": "users-outgoing",
                    "direction": "outgoing",
                    "direction_label": "Salida",
                    "direction_help": "Relaciones de salida hacia tablas hijas o dependientes de la tabla actual.",
                    "items": [
                        {
                            "tab_id": "users-outgoing-level-1",
                            "title": "Nivel 1",
                            "short_title": "Nivel 1",
                            "depth": 1,
                            "path": "graphs/users_outgoing_level1.svg",
                            "direction": "outgoing",
                            "aria_label": "Salida Nivel 1 de users",
                        }
                    ],
                    "total_levels": 1,
                    "visible_levels": 1,
                    "hidden_levels": 0,
                    "has_hidden_levels": False,
                }
            ],
        },
        generated_at="2026-03-22 10:00:00",
        storage_report=None,
    )

    rendered = output_file.read_text(encoding="utf-8")
    assert 'data-diagram-group="users-outgoing"' in rendered
    assert 'data-tab-target="users-outgoing-level-1"' in rendered
    assert "Salida visible: 1 de 1" in rendered
    assert "Leyenda visual" in rendered
    assert "Tipo de tabla" in rendered
    assert "Tabla puente detectada por varias FKs" in rendered
    assert "Tipo de relación" in rendered
    assert "clave foránea" in rendered
    assert "Salida oculta: niveles de tablas hijas o dependientes" in rendered
    assert 'data-diagram-action="zoom-in"' in rendered
    assert 'data-diagram-action="pan-right"' in rendered
    assert 'data-diagram-action="copy-png"' in rendered
    assert 'data-diagram-action="copy-svg"' in rendered
    assert 'data-diagram-action="download-svg"' in rendered
    assert 'data-diagram-action="download-png"' in rendered
    assert 'data-tooltip="Alejar"' in rendered
    assert 'data-tooltip="Acercar"' in rendered
    assert 'data-tooltip="Ajustar al área visible"' in rendered
    assert 'data-tooltip="Desplazar a la derecha"' in rendered
    assert 'data-tooltip="Copiar PNG"' in rendered
    assert 'data-tooltip="Copiar SVG"' in rendered
    assert 'data-tooltip="Descargar SVG"' in rendered
    assert 'data-tooltip="Descargar PNG"' in rendered
    assert "../assets/icons/icon-png-copy.svg" in rendered
    assert "../assets/icons/icon-svg-copy.svg" in rendered
    assert "../assets/icons/icon-svg-download.svg" in rendered
    assert "../assets/icons/icon-png-download.svg" in rendered
