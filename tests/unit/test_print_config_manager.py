"""Tests para normalización de configuración de impresión."""

from __future__ import annotations

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
    assert resolved["graph_options"]["show_columns"] is False
    assert resolved["graph_options"]["images_paginated"] is True
    assert resolved["graph_options"]["max_subnodes"] == 5
    assert resolved["graph_options"]["dpi"] == 150
