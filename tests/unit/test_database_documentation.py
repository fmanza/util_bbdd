"""Tests de la fachada pública DatabaseDocumentation (configuración, flujo multi-formato, errores; WP5)."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any

import pytest

import util_bbdd.doc as doc_package
import util_bbdd.doc.database_documentation as database_documentation_module

from util_bbdd._core.exceptions import (
    DatabaseOperationError,
    DocumentationConfigError,
    DocumentationError,
    DocumentationRenderError,
)
from util_bbdd.doc import DatabaseDocumentation, DocumentationResult
from util_bbdd.doc.application.use_cases.documentation_orchestrator import DocumentationSession
from util_bbdd.metadata.model import ALL_KINDS, Kind, RoutineMeta, SchemaSnapshot, TableMeta, ViewMeta


class _FakeDbManager:
    """``DocumentationSourcePort`` mínimo: cuenta las lecturas para comprobar cuándo se consulta la BD."""

    db_type = "postgresql"
    database = "demo"
    conn_params: dict[str, Any] = {}

    def __init__(self, *, fail: bool = False) -> None:
        self.reads: list[str] = []
        self._fail = fail

    def get_query_context_database(self) -> str:
        self.reads.append("context")
        return "demo"

    def get_schema_metadata(self, schema: str | None = None, *, kinds: Collection[Kind] = ALL_KINDS) -> SchemaSnapshot:
        self.reads.append("snapshot")
        if self._fail:
            raise DatabaseOperationError("sin conexión")
        data: dict[Kind, tuple[Any, ...]] = {
            Kind.TABLES: (TableMeta("users"), TableMeta("orders")),
            Kind.VIEWS: (ViewMeta("v_users", "SELECT 1"),),
            Kind.ROUTINES: (RoutineMeta("refresh", "PROCEDURE"),),
        }
        return SchemaSnapshot("postgresql", "demo", {kind: data.get(kind, ()) for kind in kinds})


def _documentation(tmp_path: Path, formatos: list[str], imprimir: dict[str, Any] | None = None) -> Any:
    manager = _FakeDbManager()
    return manager, DatabaseDocumentation(
        manager, directorio_salida=tmp_path, fichero_salida=Path("report"), imprimir=imprimir, formatos=formatos
    )


def _capture_renderers(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Path, Any, Any]]:
    calls: list[tuple[str, Path, Any, Any]] = []

    def _fake(name: str) -> Any:
        def generate_document(self: Any, tables: list[Any], views: list[Any], routines: list[Any], data_provider: Any,
                              output_target: Path, print_config: Any = None, graph_generator: Any = None) -> None:  # fmt: skip
            assert isinstance(data_provider, DocumentationSession)
            calls.append((name, output_target, graph_generator, data_provider))

        return generate_document

    for name, cls in (
        ("word", database_documentation_module.WordGenerator),
        ("excel", database_documentation_module.ExcelGenerator),
        ("html", database_documentation_module.HtmlGenerator),
    ):
        monkeypatch.setattr(cls, "generate_document", _fake(name))
    return calls


# ── API pública ──────────────────────────────────────────────────────────────


def test_public_api_is_the_facade_and_its_result() -> None:
    assert doc_package.__all__ == ["DatabaseDocumentation", "DocumentationResult"]
    assert not hasattr(doc_package, "WordGenerator")


def test_constructor_validates_without_reading_the_database(tmp_path: Path) -> None:
    manager, documentation = _documentation(tmp_path, ["word", "excel"])

    assert manager.reads == []
    for member in ("tablas", "vistas", "rutinas", "catalog", "headers", "imprimir_config", "db_manager", "get_ddl"):
        assert not hasattr(documentation, member)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"formatos": ["pdf"]},
        {"formatos": "word"},
        {"imprimir": "todo"},
        {"headers_file": Path("no_existe.json")},
        {"imprimir": {"plantilla_word": "no_existe.docx"}},
        {"batch_window_seconds": -1},
        {"batch_window_seconds": "90"},
        {"batch_window_seconds": True},
        {"batch_window_seconds": 1.5},
    ],
)
def test_invalid_configuration_raises_documentation_config_error(tmp_path: Path, kwargs: dict[str, Any]) -> None:
    with pytest.raises(DocumentationConfigError) as raised:
        DatabaseDocumentation(_FakeDbManager(), directorio_salida=tmp_path, **kwargs)

    assert isinstance(raised.value, ValueError)  # compatibilidad con quien capturaba ValueError
    assert isinstance(raised.value, DocumentationError)


@pytest.mark.parametrize(("value", "expected"), [(None, 0), (0, 0), (90, 90)])
def test_batch_window_seconds_accepts_none_and_non_negative_ints(value: int | None, expected: int) -> None:
    assert DatabaseDocumentation._batch_window(value) == expected


def test_missing_word_template_is_ignored_when_word_is_not_requested(tmp_path: Path) -> None:
    DatabaseDocumentation(
        _FakeDbManager(), directorio_salida=tmp_path, imprimir={"plantilla_word": "no_existe.docx"}, formatos=["html"]
    )


def test_malformed_headers_file_raises_config_error(tmp_path: Path) -> None:
    headers_file = tmp_path / "headers.json"
    headers_file.write_text('{"headers": {"COLUMNAS": {"sin_base": []}}}', encoding="utf-8")

    with pytest.raises(DocumentationConfigError):
        DatabaseDocumentation(_FakeDbManager(), directorio_salida=tmp_path, headers_file=headers_file)


# ── Generación ───────────────────────────────────────────────────────────────


def test_generate_reads_the_catalog_and_returns_outputs_and_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _capture_renderers(monkeypatch)
    manager, documentation = _documentation(tmp_path, ["word", "excel", "html"])

    result = documentation.generate()

    assert isinstance(result, DocumentationResult)
    assert [call[0] for call in calls] == ["word", "excel", "html"]
    assert result.outputs == {
        "word": tmp_path / "report" / "WORD" / "report.docx",
        "excel": tmp_path / "report" / "EXCEL" / "report.xlsx",
        "html": tmp_path / "report" / "HTML",
    }
    assert (result.tables, result.views, result.routines) == (2, 1, 1)
    assert calls[0][3] is calls[1][3] is calls[2][3]  # una sesión para todos los formatos
    assert "snapshot" in manager.reads


def test_one_graph_generator_is_shared_by_word_and_html(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _capture_renderers(monkeypatch)
    factory_calls: list[tuple[Any, dict[str, Any]]] = []

    def _fake_factory(source: Any, options: dict[str, Any]) -> object:
        factory_calls.append((source, options))
        return object()

    monkeypatch.setattr(database_documentation_module, "build_graph_generator_from_options", _fake_factory)
    imprimir = {
        "grafo": {
            "enabled": True,
            "max_depth": 2,
            "direction": "incoming",
            "dpi": 180,
            "workers": 3,
            "columns": {"mode": "compact", "max_items": 4, "show_data_types": True},
            "cardinality": {"show_constraint_name": True},
        }
    }
    _, documentation = _documentation(tmp_path, ["word", "excel", "html"], imprimir)

    documentation.generate()

    assert len(factory_calls) == 1
    by_format = {call[0]: call[2] for call in calls}
    assert by_format["word"] is by_format["html"] is not None
    assert by_format["excel"] is None
    source, options = factory_calls[0]
    assert source is calls[0][3].db_manager
    assert options["columns"] == {"mode": "compact", "max_items": 4, "show_data_types": True}
    assert (options["max_depth"], options["direction"], options["dpi"], options["workers"]) == (2, "incoming", 180, 3)
    assert options["cardinality"]["show_constraint_name"] is True


def test_graph_generator_for_a_single_format_and_none_when_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _capture_renderers(monkeypatch)
    generator = object()
    monkeypatch.setattr(database_documentation_module, "build_graph_generator_from_options", lambda *_: generator)

    _documentation(tmp_path, ["word"], {"grafo": {"enabled": True}})[1].generate()
    _documentation(tmp_path, ["word", "html"], {})[1].generate()

    assert [call[2] for call in calls] == [generator, None, None]


def test_renderer_failure_is_wrapped_in_documentation_render_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _broken(self: Any, *args: Any, **kwargs: Any) -> None:
        raise OSError("disco lleno")

    monkeypatch.setattr(database_documentation_module.ExcelGenerator, "generate_document", _broken)
    _, documentation = _documentation(tmp_path, ["excel"])

    with pytest.raises(DocumentationRenderError, match="excel") as raised:
        documentation.generate()

    assert isinstance(raised.value.__cause__, OSError)


def test_database_errors_are_not_wrapped(tmp_path: Path) -> None:
    documentation = DatabaseDocumentation(_FakeDbManager(fail=True), directorio_salida=tmp_path, formatos=["excel"])

    with pytest.raises(DatabaseOperationError):
        documentation.generate()
