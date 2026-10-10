"""Tests de helpers internos del runtime documental."""

from __future__ import annotations

import json
import logging

from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

from util_bbdd.doc.application.use_cases.documentation_orchestrator import (
    DocumentationBootstrap,
    DocumentationOutputPlanner,
    DocumentationSession,
)
from util_bbdd.doc.domain.models import DocumentationBootstrapState, DocumentationSettings
from util_bbdd.doc.infrastructure.renderers.registry import build_default_renderer_registry
from util_bbdd.doc.infrastructure.renderers.shared.print_config_manager import PrintConfigManager
from util_bbdd.doc.infrastructure.runtime.headers_runtime import DocumentationHeadersRuntime
from util_bbdd.doc.infrastructure.runtime.metadata_runtime import DocumentationMetadataRuntimeFactory
from util_bbdd.doc.infrastructure.runtime.output_runtime import DocumentationOutputRuntime
from util_bbdd.doc.infrastructure.storage.runtime import StorageInventoryReportService, StorageInventoryRuntime
from util_bbdd.exceptions import DatabaseOperationError, QueryNotFoundError
from util_bbdd.metadata.model import ColumnMeta, Kind, PrimaryKeyMeta, RoutineMeta, SchemaSnapshot, TableMeta, ViewMeta


def _session(manager: Any, tmp_path: Path, formatos: list[str] | None = None) -> DocumentationSession:
    """Sesión de una generación sobre ``manager`` (lo que hace ``DatabaseDocumentation.generate``)."""
    settings = DocumentationSettings(
        print_config=PrintConfigManager.normalize({}),
        formatos=formatos or ["word"],
        headers_config={"headers": {}},
        headers={},
        table_style="Table Grid",
    )
    state = DocumentationBootstrapState(
        settings=settings,
        directorio_salida=tmp_path,
        fichero_salida=Path("report"),
        tablas=[],
        vistas=[],
        rutinas=[],
        catalog=None,
    )
    return DocumentationSession.from_state(
        state,
        db_manager=cast(Any, manager),
        logger=logging.getLogger(__name__),
        output_policy=DocumentationOutputRuntime(),
        metadata_runtime_factory=DocumentationMetadataRuntimeFactory(),
        storage_report_service=StorageInventoryReportService(),
    )


def test_normalize_output_formats_without_duplicates() -> None:
    output_runtime = DocumentationOutputRuntime()
    assert output_runtime.normalize_output_formats([" WORD ", "html", "word", "", "HTML"]) == ["word", "html"]


def test_get_format_output_dir_creates_execution_root(tmp_path: Path) -> None:
    fichero_salida = Path("nested/report.docx")
    output_runtime = DocumentationOutputRuntime()

    word_dir = output_runtime.get_format_output_dir(tmp_path, fichero_salida, "word")
    html_dir = output_runtime.get_format_output_dir(tmp_path, fichero_salida, "html")

    assert word_dir == tmp_path / "report" / "WORD"
    assert html_dir == tmp_path / "report" / "HTML"
    assert word_dir.is_dir()
    assert html_dir.is_dir()


def test_generate_auto_output_filename_reuses_recent_name_within_batch_window(tmp_path: Path) -> None:
    cache: dict[tuple[str, str], tuple[float, str]] = {}
    output_runtime = DocumentationOutputRuntime()

    first = output_runtime.generate_auto_output_filename(
        db_type="postgresql",
        database="demo",
        conn_params={},
        output_dir=tmp_path,
        output_cache=cache,
        batch_window_seconds=90,
        current_time=100.0,
        current_datetime=datetime(2026, 4, 1, 10, 0, 0),
    )
    second = output_runtime.generate_auto_output_filename(
        db_type="postgresql",
        database="demo",
        conn_params={},
        output_dir=tmp_path,
        output_cache=cache,
        batch_window_seconds=90,
        current_time=130.0,
        current_datetime=datetime(2026, 4, 1, 10, 1, 0),
    )
    third = output_runtime.generate_auto_output_filename(
        db_type="postgresql",
        database="demo",
        conn_params={},
        output_dir=tmp_path,
        output_cache=cache,
        batch_window_seconds=90,
        current_time=191.0,
        current_datetime=datetime(2026, 4, 1, 10, 2, 0),
    )

    assert first == Path("demo-20260401_100000")
    assert second == first
    assert third == Path("demo-20260401_100200")


def test_resolve_document_output_filename_uses_manager_context_when_missing(tmp_path: Path) -> None:
    cache: dict[tuple[str, str], tuple[float, str]] = {}
    output_runtime = DocumentationOutputRuntime()

    class _DbManagerWithoutConnParams:
        db_type = "oracle"
        database = "xe"

    resolved = output_runtime.resolve_document_output_filename(
        fichero_salida=None,
        db_manager=cast(Any, _DbManagerWithoutConnParams()),
        output_dir=tmp_path,
        output_cache=cache,
        batch_window_seconds=90,
    )

    assert resolved.name.startswith("xe-")


def test_documentation_output_planner_builds_ordered_paths(tmp_path: Path) -> None:
    class _ManagerStub:
        db_type = "postgresql"
        database = "demo"
        conn_params: dict[str, Any] = {}

        def get_query_context_database(self) -> str:
            return "demo"

    session = _session(_ManagerStub(), tmp_path, formatos=["word", "excel", "html"])
    plans = DocumentationOutputPlanner(session, build_default_renderer_registry()).build_plans()

    assert [(plan.output_format, plan.output_path) for plan in plans] == [
        ("word", tmp_path / "report" / "WORD" / "report.docx"),
        ("excel", tmp_path / "report" / "EXCEL" / "report.xlsx"),
        ("html", tmp_path / "report" / "HTML"),
    ]
    assert [plan.include_graph_generator for plan in plans] == [True, False, True]


def test_documentation_bootstrap_builds_initial_state(tmp_path: Path) -> None:
    class _DbManager:
        db_type = "postgresql"
        database = "demo"
        conn_params: dict[str, Any] = {}

        def get_schema_metadata(self, schema: str | None = None, *, kinds: Any = ()) -> SchemaSnapshot:
            data = {
                Kind.TABLES: (TableMeta("users", "usuarios"),),
                Kind.VIEWS: (ViewMeta("active_users", "SELECT 1"),),
                Kind.ROUTINES: (RoutineMeta("refresh_users", "PROCEDURE"),),
            }
            return SchemaSnapshot("postgresql", "demo", {k: data.get(k, ()) for k in kinds})

    headers_file = tmp_path / "headers.json"
    headers_file.write_text(
        json.dumps({"headers": {"tables": {"base": ["Nombre", "Propietario"]}}}),
        encoding="utf-8",
    )

    bootstrap = DocumentationBootstrap(
        db_manager=cast(Any, _DbManager()),
        directorio_salida=tmp_path,
        fichero_salida=Path("report"),
        imprimir={"table_style": "Light Grid", "grafo": {"enabled": True}},
        formatos=[" WORD ", "html", "word"],
        headers_file=headers_file,
        output_cache={},
        batch_window_seconds=90,
        print_config_policy=PrintConfigManager(),
        headers_runtime=DocumentationHeadersRuntime(),
        output_policy=DocumentationOutputRuntime(),
    )
    settings = bootstrap.settings()
    state = bootstrap.build(settings)

    assert settings.print_config == PrintConfigManager.normalize(
        {"table_style": "Light Grid", "grafo": {"enabled": True}}
    )
    assert settings.formatos == ["word", "html"]
    assert settings.table_style == "Light Grid"
    assert settings.headers_config["headers"]["tables"]["base"] == ["Nombre", "Propietario"]
    assert settings.headers == {"tables": ["Nombre", "Propietario"]}
    assert state.settings is settings
    assert state.directorio_salida == tmp_path
    assert state.fichero_salida == Path("report")
    # D1: filas neutras desde el snapshot (nombre, comentario[, collation | tipo])
    assert state.tablas == [("users", "usuarios", "")]
    assert state.vistas == [("active_users", "")]
    assert state.rutinas == [("refresh_users", "PROCEDURE", "")]


def test_documentation_session_caches_manager_metadata_calls(tmp_path: Path) -> None:
    class _DbManager:
        db_type = "postgresql"
        database = "demo"
        conn_params: dict[str, Any] = {}

        def __init__(self) -> None:
            self.calls: dict[str, int] = {"get_query_context_database": 0, "get_ddl": 0}
            self.loaded: list[frozenset[Kind]] = []

        def get_query_context_database(self) -> str:
            self.calls["get_query_context_database"] += 1
            return "demo"

        def get_ddl(self, tabla: str) -> str:
            self.calls["get_ddl"] += 1
            return f"DDL {tabla}"

        def get_schema_metadata(self, schema: str | None = None, *, kinds: Any = ()) -> SchemaSnapshot:
            self.loaded.append(frozenset(kinds))
            data = {
                Kind.COLUMNS: (ColumnMeta("users", "users_id", 1, "integer", "integer", False, identity="always"),),
                Kind.PRIMARY_KEYS: (PrimaryKeyMeta("users", "pk_users", ("users_id",)),),
            }
            return SchemaSnapshot("postgresql", "demo", {k: data.get(k, ()) for k in kinds})

    manager = _DbManager()

    session = _session(manager, tmp_path)

    assert session.database == "demo"
    assert session.get_ddl("users") == "DDL users"
    assert session.get_ddl("users") == "DDL users"
    expected_column = ("users_id", "integer", "NO", "", "IDENTITY (ALWAYS)", "")
    assert session.get_columns("users") == [expected_column]
    assert session.get_columns("users") == [expected_column]
    assert session.get_primary_keys("users") == [("users_id",)]
    assert session.get_primary_keys("users") == [("users_id",)]
    assert manager.calls == {"get_query_context_database": 1, "get_ddl": 1}
    # D1: cada tipo de objeto se lee una vez para todo el schema, no por tabla
    assert manager.loaded == [frozenset({Kind.COLUMNS}), frozenset({Kind.PRIMARY_KEYS})]


def test_documentation_session_metadata_helpers_delegate_successfully(tmp_path: Path) -> None:
    class _MetadataDbManager:
        db_type = "postgresql"
        database = "demo"
        conn_params: dict[str, Any] = {}

        def get_query_context_database(self) -> str:
            return "demo"

        def get_database_version(self) -> str:
            return "15.2"

        def get_database_charset_collation(self) -> dict[str, str]:
            return {"charset": "UTF8", "collation": "en_US.UTF-8"}

        def get_columns_charset_collation(self, tabla: str) -> list[tuple[str, str | None, str | None]]:
            assert tabla == "users"
            return [("name", "UTF8", "en_US.UTF-8")]

    session = _session(_MetadataDbManager(), tmp_path)

    assert session.get_database_version() == "15.2"
    assert session.get_database_charset_collation() == {"charset": "UTF8", "collation": "en_US.UTF-8"}
    assert session.get_columns_charset_collation("users") == [("name", "UTF8", "en_US.UTF-8")]


def test_documentation_session_metadata_helpers_return_none_on_error(tmp_path: Path) -> None:
    class _BrokenMetadataDbManager:
        db_type = "postgresql"
        database = "demo"
        conn_params: dict[str, Any] = {}

        def get_query_context_database(self) -> str:
            return "demo"

        def get_database_version(self) -> str:
            raise DatabaseOperationError("version boom")

        def get_database_charset_collation(self) -> dict[str, str]:
            raise DatabaseOperationError("charset boom")

        def get_columns_charset_collation(self, _tabla: str) -> list[tuple[str, str | None, str | None]]:
            raise DatabaseOperationError("columns boom")

    session = _session(_BrokenMetadataDbManager(), tmp_path)

    assert session.get_database_version() is None
    assert session.get_database_charset_collation() is None
    assert session.get_columns_charset_collation("users") is None


def test_documentation_session_falls_back_to_schema_context_when_query_context_is_empty(tmp_path: Path) -> None:
    class _SchemaDbManager:
        db_type = "postgresql"
        database = "demo"
        conn_params = {"schema": "analytics"}

        def get_query_context_database(self) -> str:
            return ""

    session = _session(_SchemaDbManager(), tmp_path)

    assert session.database == "analytics"


def test_documentation_session_caches_database_version_calls(tmp_path: Path) -> None:
    class _VersionDbManager:
        db_type = "postgresql"
        database = "demo"
        conn_params: dict[str, Any] = {}

        def __init__(self) -> None:
            self.calls: dict[str, int] = {
                "get_query_context_database": 0,
                "get_database_version": 0,
            }

        def get_query_context_database(self) -> str:
            self.calls["get_query_context_database"] += 1
            return "demo"

        def get_database_version(self) -> str:
            self.calls["get_database_version"] += 1
            return "15.2"

    manager = _VersionDbManager()

    session = _session(manager, tmp_path)

    assert session.get_database_version() == "15.2"
    assert session.get_database_version() == "15.2"
    assert manager.calls == {
        "get_query_context_database": 1,
        "get_database_version": 1,
    }


def test_documentation_session_storage_inventory_report_returns_runtime_output(tmp_path: Path) -> None:
    class _MariadbStorageManager:
        db_type = "mariadb"
        database = "demo"
        conn_params: dict[str, Any] = {}

        def get_query_context_database(self) -> str:
            return "demo"

        def get_storage_rows(self, query_name: str, **kwargs: Any) -> list[tuple[str, str]]:
            if query_name != "temp_storage_variables":
                raise QueryNotFoundError(query_name)
            assert kwargs["schema"] == "demo"
            return [("innodb_temp_data_file_path", "ibtmp1:12M:autoextend:max:5G")]

    session = _session(_MariadbStorageManager(), tmp_path)
    report = session.get_storage_inventory_report()

    assert report["db_type"] == "mariadb"
    assert report["database"] == "demo"
    assert report["total_rows"] == 1
    assert [section["status"] for section in report["sections"]] == ["not_supported", "not_supported", "ok"]
    assert report["sections"][-1]["rows"] == [
        [
            "innodb_temp_data_file_path",
            "ibtmp1",
            "12,00",
            "Si",
            "5120,00",
            "ibtmp1:12M:autoextend:max:5G",
        ]
    ]


def test_storage_inventory_runtime_parses_mariadb_temp_storage_variables() -> None:
    class _MariadbStorageManager:
        db_type = "mariadb"
        conn_params: dict[str, Any] = {}

        def get_storage_rows(self, query_name: str, **kwargs: Any) -> list[tuple[str, str]]:
            if query_name != "temp_storage_variables":
                raise QueryNotFoundError(query_name)
            assert kwargs["schema"] == "demo"
            return [("innodb_temp_data_file_path", "ibtmp1:12M:autoextend:max:5G")]

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


def test_storage_inventory_runtime_unregistered_engine_adds_fallback_notice(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """DOC-03 (AUDIT_CODE 2026-09-22): un motor sin inventario propio (HSQLDB, sin consultas de almacenamiento)
    debe advertir explícitamente que usa el fallback genérico, no caer en silencio."""

    class _UnregisteredEngineManager:
        db_type = "hsqldb"
        conn_params: dict[str, Any] = {}

        def get_storage_rows(self, query_name: str, **kwargs: Any) -> list[tuple[str, str]]:
            raise QueryNotFoundError(query_name)

    runtime = StorageInventoryRuntime(
        db_manager=cast(Any, _UnregisteredEngineManager()),
        logger=logging.getLogger(__name__),
        db_type="hsqldb",
        database="demo",
        print_config={},
    )

    with caplog.at_level(logging.WARNING):
        report = runtime.get_storage_inventory_report()

    notice_sections = [s for s in report["sections"] if s["query"] == "generic_storage_fallback_notice"]
    assert len(notice_sections) == 1
    assert notice_sections[0]["status"] == "not_supported"
    assert "fallback genérico" in notice_sections[0]["message"]
    assert any("hsqldb" in message.lower() and "genérico" in message.lower() for message in caplog.messages)
    assert [s["status"] for s in report["sections"][1:]] == ["not_supported", "not_supported"]


def test_storage_inventory_runtime_registered_engine_has_no_fallback_notice() -> None:
    """DOC-03 (AUDIT_CODE 2026-09-22): un motor con estrategia dedicada (mariadb)
    no debe generar la sección de aviso de fallback genérico."""

    class _MariadbStorageManager:
        db_type = "mariadb"
        conn_params: dict[str, Any] = {}

        def get_storage_rows(self, query_name: str, **kwargs: Any) -> list[tuple[str, str]]:
            raise QueryNotFoundError(query_name)

    runtime = StorageInventoryRuntime(
        db_manager=cast(Any, _MariadbStorageManager()),
        logger=logging.getLogger(__name__),
        db_type="mariadb",
        database="demo",
        print_config={},
    )

    report = runtime.get_storage_inventory_report()

    assert not any(s["query"] == "generic_storage_fallback_notice" for s in report["sections"])


def test_normalize_output_formats_rejects_invalid_values() -> None:
    output_runtime = DocumentationOutputRuntime()
    with pytest.raises(ValueError, match="Formato no soportado"):
        output_runtime.normalize_output_formats(["pdf"])
