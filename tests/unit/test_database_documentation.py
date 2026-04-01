"""Tests del flujo multi-formato de DatabaseDocumentation."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any, cast

import util_bbdd.doc.database_documentation as database_documentation_module

from util_bbdd.doc._documentation_orchestrator import DocumentationSession
from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.doc.print_config_manager import PrintConfigManager


class _FakeDbManager:
    db_type = "postgresql"
    database = "demo"
    conn_params: dict[str, Any] = {}

    def get_query_context_database(self) -> str:
        return "demo"


def _refresh_documentation_session(doc: DatabaseDocumentation) -> None:
    doc._bind_documentation_session(DocumentationSession.from_documentation(doc))


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
    _refresh_documentation_session(doc)
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
    word_calls: list[Path] = []

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
        assert isinstance(data_provider, DocumentationSession)
        assert data_provider.data_provider is doc
        captured["word"] = graph_generator
        word_calls.append(output_file)

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
        assert isinstance(data_provider, DocumentationSession)
        assert data_provider.data_provider is doc
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
    assert len(word_calls) == 1
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
        assert isinstance(data_provider, DocumentationSession)
        assert data_provider.data_provider is doc
        captured["word"] = graph_generator

    monkeypatch.setattr(database_documentation_module, "GraphvizRelationshipGraphExt", _ForbiddenGraphGenerator)
    monkeypatch.setattr(
        database_documentation_module.WordGenerator,
        "generate_document",
        _fake_word_generate_document,
    )

    doc._create_documents()

    assert captured["word"] is None


def test_database_documentation_generates_excel_without_graph_generator_kwarg(monkeypatch: Any, tmp_path: Path) -> None:
    doc = _build_documentation_stub(
        formatos=["excel"],
        normalized_config=PrintConfigManager.normalize({}),
        output_dir=tmp_path,
    )
    captured: dict[str, Any] = {}

    def _fake_excel_generate_document(
        self: Any,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        data_provider: Any,
        output_file: Path,
        print_config: dict[str, Any] | None = None,
    ) -> None:
        assert isinstance(data_provider, DocumentationSession)
        assert data_provider.data_provider is doc
        captured["output_file"] = output_file
        captured["print_config"] = print_config

    monkeypatch.setattr(
        database_documentation_module.ExcelGenerator,
        "generate_document",
        _fake_excel_generate_document,
    )

    doc._create_documents()

    assert captured["output_file"] == tmp_path / "report" / "EXCEL" / "report.xlsx"
    assert captured["print_config"] == doc.imprimir_config


def test_database_documentation_creates_requested_formats_in_order(monkeypatch: Any, tmp_path: Path) -> None:
    normalized = PrintConfigManager.normalize({"grafo": {"enabled": True}})
    doc = _build_documentation_stub(
        formatos=["word", "excel", "html"], normalized_config=normalized, output_dir=tmp_path
    )
    generator_calls: list[tuple[str, Path, Any, DocumentationSession]] = []

    class _FakeGraphGenerator:
        def __init__(self, **_: Any) -> None:
            return None

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
        assert isinstance(data_provider, DocumentationSession)
        assert data_provider.data_provider is doc
        generator_calls.append(("word", output_file, graph_generator, data_provider))

    def _fake_excel_generate_document(
        self: Any,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        data_provider: Any,
        output_file: Path,
        print_config: dict[str, Any] | None = None,
    ) -> None:
        assert isinstance(data_provider, DocumentationSession)
        assert data_provider.data_provider is doc
        generator_calls.append(("excel", output_file, None, data_provider))

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
        assert isinstance(data_provider, DocumentationSession)
        assert data_provider.data_provider is doc
        generator_calls.append(("html", output_dir, graph_generator, data_provider))

    monkeypatch.setattr(database_documentation_module, "GraphvizRelationshipGraphExt", _FakeGraphGenerator)
    monkeypatch.setattr(database_documentation_module.WordGenerator, "generate_document", _fake_word_generate_document)
    monkeypatch.setattr(
        database_documentation_module.ExcelGenerator, "generate_document", _fake_excel_generate_document
    )
    monkeypatch.setattr(database_documentation_module.HtmlGenerator, "generate_document", _fake_html_generate_document)

    doc._create_documents()

    assert [call[0] for call in generator_calls] == ["word", "excel", "html"]
    assert generator_calls[0][1] == tmp_path / "report" / "WORD" / "report.docx"
    assert generator_calls[1][1] == tmp_path / "report" / "EXCEL" / "report.xlsx"
    assert generator_calls[2][1] == tmp_path / "report" / "HTML"
    assert generator_calls[0][2] is generator_calls[2][2]
    assert isinstance(generator_calls[0][2], _FakeGraphGenerator)
    assert generator_calls[1][2] is None
    assert generator_calls[0][3] is generator_calls[1][3] is generator_calls[2][3]


def test_database_documentation_no_longer_exposes_legacy_metadata_api(tmp_path: Path) -> None:
    doc = _build_documentation_stub(
        formatos=["word"],
        normalized_config=PrintConfigManager.normalize({}),
        output_dir=tmp_path,
    )

    for member_name in (
        "db_type",
        "database",
        "get_ddl",
        "get_view_ddl",
        "get_columns",
        "get_routine_ddl",
        "get_routine_parameters",
        "get_primary_keys",
        "get_foreign_keys",
        "get_unique_constraints",
        "get_indices",
        "get_database_version",
        "get_database_charset_collation",
        "get_columns_charset_collation",
        "get_storage_inventory_report",
    ):
        assert not hasattr(doc, member_name)
