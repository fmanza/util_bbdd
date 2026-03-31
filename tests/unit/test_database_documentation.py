"""Tests del flujo multi-formato de DatabaseDocumentation."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any, cast

import util_bbdd.doc.database_documentation as database_documentation_module

from util_bbdd.database_exceptions import QueryNotFoundError
from util_bbdd.doc._storage_inventory_runtime import StorageInventoryRuntime
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


def test_database_documentation_normalizes_output_formats_without_duplicates(tmp_path: Path) -> None:
    doc = _build_documentation_stub(
        formatos=["word"],
        normalized_config=PrintConfigManager.normalize({}),
        output_dir=tmp_path,
    )

    assert doc._normalize_output_formats([" WORD ", "html", "word", "", "HTML"]) == ["word", "html"]


def test_database_documentation_resolves_output_dirs_under_execution_root(tmp_path: Path) -> None:
    doc = _build_documentation_stub(
        formatos=["word"],
        normalized_config=PrintConfigManager.normalize({}),
        output_dir=tmp_path,
    )
    doc.fichero_salida = Path("nested/report.docx")

    word_dir = doc._get_format_output_dir("word")
    html_dir = doc._get_format_output_dir("html")

    assert word_dir == tmp_path / "report" / "WORD"
    assert html_dir == tmp_path / "report" / "HTML"
    assert word_dir.is_dir()
    assert html_dir.is_dir()


def test_database_documentation_falls_back_to_schema_context_when_query_context_is_empty(tmp_path: Path) -> None:
    class _SchemaDbManager:
        db_type = "postgresql"
        database = "demo"
        conn_params = {"schema": "analytics"}

        def get_query_context_database(self) -> str:
            return ""

    doc = _build_documentation_stub(
        formatos=["word"],
        normalized_config=PrintConfigManager.normalize({}),
        output_dir=tmp_path,
    )
    doc.db_manager = cast(Any, _SchemaDbManager())

    assert doc._get_generator_database_context() == "analytics"


def test_database_documentation_delegates_storage_inventory_report(tmp_path: Path, monkeypatch: Any) -> None:
    doc = _build_documentation_stub(
        formatos=["word"],
        normalized_config=PrintConfigManager.normalize({"storage": {"tablespace": "ts_demo"}}),
        output_dir=tmp_path,
    )
    captured: dict[str, Any] = {}

    class _FakeStorageInventoryRuntime:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def get_storage_inventory_report(self) -> dict[str, Any]:
            return {"sections": [{"title": "demo", "rows": []}], "total_rows": 0}

    monkeypatch.setattr(database_documentation_module, "StorageInventoryRuntime", _FakeStorageInventoryRuntime)

    report = doc.get_storage_inventory_report()

    assert report == {"sections": [{"title": "demo", "rows": []}], "total_rows": 0}
    assert captured["db_manager"] is doc.db_manager
    assert captured["logger"] is doc.logger
    assert captured["db_type"] == "postgresql"
    assert captured["database"] == "demo"
    assert captured["print_config"] == doc.imprimir_config


def test_storage_inventory_runtime_parses_mariadb_temp_storage_variables() -> None:
    class _ResolvedQuery:
        def __init__(self, final_sql: str) -> None:
            self.final_sql = final_sql

    class _MariadbStorageManager:
        db_type = "mariadb"
        conn_params: dict[str, Any] = {}

        def resolve_query(self, query_name: str, **kwargs: Any) -> _ResolvedQuery:
            if query_name == "temp_storage_variables":
                assert kwargs["database"] == "demo"
                return _ResolvedQuery("SHOW VARIABLES LIKE 'innodb_temp_data_file_path'")
            raise QueryNotFoundError(query_name)

        def execute_query_many(self, query_name: str, **kwargs: Any) -> list[tuple[str, str]]:
            assert query_name == "temp_storage_variables"
            assert kwargs["database"] == "demo"
            return [("innodb_temp_data_file_path", "ibtmp1:12M:autoextend:max:5G")]

        def execute_custom_one(self, _query: str) -> None:
            return None

    runtime = StorageInventoryRuntime(
        db_manager=cast(Any, _MariadbStorageManager()),
        logger=logging.getLogger(__name__),
        db_type="mariadb",
        database="demo",
        print_config={},
    )

    report = runtime.get_storage_inventory_report()

    assert report["db_type"] == "mariadb"
    assert report["database"] == "demo"
    assert report["total_rows"] == 1
    assert report["tablespace"] == ""
    assert [section["status"] for section in report["sections"]] == ["not_supported", "not_supported", "ok"]
    temp_section = report["sections"][-1]
    assert temp_section["headers"] == [
        "Variable",
        "Archivo",
        "Inicial (MB)",
        "Autoextend",
        "Maximo (MB)",
        "Valor bruto",
    ]
    assert temp_section["rows"] == [
        [
            "innodb_temp_data_file_path",
            "ibtmp1",
            "12,00",
            "Si",
            "5120,00",
            "ibtmp1:12M:autoextend:max:5G",
        ]
    ]
    assert temp_section["numeric_columns"] == [2, 4]
