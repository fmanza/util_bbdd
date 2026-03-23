"""Tests para normalización de configuración de impresión."""

from __future__ import annotations

from pathlib import Path

from util_bbdd.doc.print_config_manager import PrintConfigManager


def test_normalize_accepts_documented_nested_imprimir_block() -> None:
    config = {
        "imprimir": {
            "table_style": "Grid Table 4 Accent 4",
            "tablas_por_documento": 25,
            "rutinas": {
                "imprimir_procedures": True,
                "imprimir_function": True,
            },
            "tablas": {
                "imprimir_tablas": True,
            },
        }
    }

    normalized = PrintConfigManager.normalize(config)
    resolved = PrintConfigManager.resolve_for_word(normalized)

    assert normalized["table_style"] == "Grid Table 4 Accent 4"
    assert normalized["tablas_por_documento"] == 25
    assert normalized["rutinas"]["imprimir_procedures"] is True
    assert normalized["rutinas"]["imprimir_function"] is True
    assert resolved["include_procedures"] is True
    assert resolved["include_functions"] is True
    assert resolved["include_tables"] is True


def test_resolve_for_word_applies_safe_graph_defaults() -> None:
    normalized = PrintConfigManager.normalize(
        {
            "grafo": {
                "enabled": True,
            }
        }
    )

    resolved = PrintConfigManager.resolve_for_word(normalized)

    assert resolved["include_diagrams"] is True
    assert resolved["graph_options"]["format"] == "png"
    assert resolved["graph_options"]["max_depth"] == 1
    assert resolved["graph_options"]["direction"] == "both"
    assert resolved["graph_options"]["images_paginated"] is True
    assert resolved["graph_options"]["max_subnodes"] == 5
    assert resolved["graph_options"]["dpi"] == 150
    assert resolved["graph_options"]["columns"]["mode"] == "relations"
    assert resolved["graph_options"]["columns"]["max_items"] == 8
    assert resolved["graph_options"]["columns"]["show_data_types"] is False


def test_normalize_graph_contract_accepts_legacy_format_alias() -> None:
    normalized = PrintConfigManager.normalize(
        {
            "grafo": {
                "enabled": True,
                "format": "png",
            }
        }
    )

    assert normalized["grafo"]["render_format"] == "png"


def test_resolve_for_html_uses_canonical_render_format() -> None:
    normalized = PrintConfigManager.normalize(
        {
            "grafo": {
                "enabled": True,
                "render_format": "png",
            }
        }
    )

    resolved = PrintConfigManager.resolve_for_html(
        config=normalized,
        output_dir=Path("docs_out"),
        default_template_file=Path("detail.html.j2"),
    )

    assert resolved["include_diagrams"] is True
    assert resolved["diagram_options"]["format"] == "png"


def test_resolve_for_word_coerces_svg_to_png() -> None:
    normalized = PrintConfigManager.normalize(
        {
            "grafo": {
                "enabled": True,
                "render_format": "svg",
            }
        }
    )

    resolved = PrintConfigManager.resolve_for_word(normalized)

    assert resolved["graph_options"]["format"] == "png"


def test_normalize_graph_contract_uses_nested_column_configuration() -> None:
    normalized = PrintConfigManager.normalize(
        {
            "grafo": {
                "enabled": True,
                "direction": "outgoing",
                "max_depth": 3,
                "columns": {
                    "mode": "compact",
                    "max_items": 4,
                    "show_data_types": True,
                },
                "cardinality": {
                    "style": "end_markers",
                    "show_constraint_name": True,
                },
            }
        }
    )

    assert normalized["grafo"]["direction"] == "outgoing"
    assert normalized["grafo"]["max_depth"] == 3
    assert normalized["grafo"]["columns"]["mode"] == "compact"
    assert normalized["grafo"]["columns"]["max_items"] == 4
    assert normalized["grafo"]["columns"]["show_data_types"] is True
    assert normalized["grafo"]["cardinality"]["show_constraint_name"] is True
