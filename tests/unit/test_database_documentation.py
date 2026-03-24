"""Tests del flujo multi-formato de DatabaseDocumentation."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any, cast

import util_bbdd.doc.database_documentation as database_documentation_module

from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.doc.print_config_manager import PrintConfigManager


class _FakeDbManager:
    db_type = "postgresql"
    database = "demo"
    conn_params: dict[str, Any] = {}

    def get_query_context_database(self) -> str:
        return "demo"


def _build_documentation_stub(
    *,
    formatos: list[str],
    normalized_config: dict[str, Any],
    output_dir: Path,
) -> DatabaseDocumentation:
    doc: DatabaseDocumentation = DatabaseDocumentation.__new__(DatabaseDocumentation)
    doc.logger = logging.getLogger(__name__)
    doc.db_manager = cast(Any, _FakeDbManager())
    doc.imprimir_config = normalized_config
    doc.formatos = formatos
    doc.directorio_salida = output_dir
    doc.fichero_salida = Path("report")
    doc.headers = {}
    doc.table_style = "Table Grid"
    doc.tablas = []
    doc.vistas = []
    doc.rutinas = []
    return doc


def test_database_documentation_shares_graph_generator_between_word_and_html(monkeypatch: Any, tmp_path: Path) -> None:
    normalized = PrintConfigManager.normalize(
        {
            "grafo": {
                "enabled": True,
                "max_depth": 2,
                "direction": "incoming",
                "dpi": 180,
                "columns": {
                    "mode": "compact",
                    "max_items": 4,
                    "show_data_types": True,
                },
                "cardinality": {
                    "show_constraint_name": True,
                },
            }
        }
    )
    doc = _build_documentation_stub(formatos=["word", "html"], normalized_config=normalized, output_dir=tmp_path)

    init_calls: list[dict[str, Any]] = []
    captured: dict[str, Any] = {}

    class _FakeGraphGenerator:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            init_calls.append(kwargs)

    def _fake_word_generate_document(
        self: Any,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        data_provider: Any,
        output_file: Path,
        print_config: dict[str, Any] | None = None,
        graph_generator: Any = None,
    ) -> None:
        captured["word"] = graph_generator

    def _fake_html_generate_document(
        self: Any,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        data_provider: Any,
        output_dir: Path,
        print_config: dict[str, Any] | None = None,
        graph_generator: Any = None,
    ) -> None:
        captured["html"] = graph_generator

    monkeypatch.setattr(database_documentation_module, "GraphvizRelationshipGraphExt", _FakeGraphGenerator)
    monkeypatch.setattr(
        database_documentation_module.WordGenerator,
        "generate_document",
        _fake_word_generate_document,
    )
    monkeypatch.setattr(
        database_documentation_module.HtmlGenerator,
        "generate_document",
        _fake_html_generate_document,
    )

    doc._create_documents()

    assert len(init_calls) == 1
    assert captured["word"] is captured["html"]
    assert init_calls[0]["db_manager"] is doc.db_manager
    assert init_calls[0]["column_mode"] == "compact"
    assert init_calls[0]["max_columns"] == 4
    assert init_calls[0]["show_data_types"] is True
    assert init_calls[0]["max_depth"] == 2
    assert init_calls[0]["direction"] == "incoming"
    assert init_calls[0]["show_constraint_name"] is True
    assert init_calls[0]["render_dpi"] == 180


def test_database_documentation_does_not_prebuild_shared_graph_generator_for_single_format(
    monkeypatch: Any, tmp_path: Path
) -> None:
    normalized = PrintConfigManager.normalize({"grafo": {"enabled": True}})
    doc = _build_documentation_stub(formatos=["word"], normalized_config=normalized, output_dir=tmp_path)
    captured: dict[str, Any] = {}

    class _ForbiddenGraphGenerator:
        def __init__(self, **kwargs: Any) -> None:
            raise AssertionError("No debe construir un generador compartido para un único formato")

    def _fake_word_generate_document(
        self: Any,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        data_provider: Any,
        output_file: Path,
        print_config: dict[str, Any] | None = None,
        graph_generator: Any = None,
    ) -> None:
        captured["word"] = graph_generator

    monkeypatch.setattr(database_documentation_module, "GraphvizRelationshipGraphExt", _ForbiddenGraphGenerator)
    monkeypatch.setattr(
        database_documentation_module.WordGenerator,
        "generate_document",
        _fake_word_generate_document,
    )

    doc._create_documents()

    assert captured["word"] is None
