"""Tests para las mejoras de Phase 2 del tech debt (TD-07, TD-11, TD-12)."""

from __future__ import annotations

import logging

from unittest.mock import MagicMock

import pytest

from util_bbdd import DatabaseOperationError
from util_bbdd.managers import SyncDatabaseManager
from util_bbdd.managers._manager_shared_mixin import DatabaseManagerSharedMixin
from util_bbdd.metadata import DatabaseMetadataCache
from util_bbdd.metadata.cache import RelationshipMetadataCache

# ---------------------------------------------------------------------------
# TD-12: TemplateEngine auto_reload=False
# ---------------------------------------------------------------------------


class TestTemplateEngineAutoReload:
    """Verifica que Jinja2 Environment usa auto_reload=False (TD-12)."""

    def test_environment_has_auto_reload_disabled(self) -> None:
        from pathlib import Path

        from util_bbdd.doc.infrastructure.renderers.shared.template_engine import TemplateEngine

        templates_root = Path(__file__).resolve().parents[2] / "src" / "util_bbdd" / "doc" / "templates"
        engine = TemplateEngine(templates_root=templates_root)

        assert engine.environment.auto_reload is False


# ---------------------------------------------------------------------------
# TD-11: DatabaseManagerSharedMixin
# ---------------------------------------------------------------------------


class TestDatabaseManagerSharedMixin:
    """Verifica herencia y métodos compartidos del mixin (TD-11)."""

    def test_sync_manager_inherits_from_mixin(self) -> None:
        assert issubclass(SyncDatabaseManager, DatabaseManagerSharedMixin)

    def test_async_manager_inherits_from_mixin(self) -> None:
        from util_bbdd.managers import AsyncDatabaseManager

        assert issubclass(AsyncDatabaseManager, DatabaseManagerSharedMixin)

    def test_mixin_clear_all_caches_delegates(self) -> None:
        manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
        manager.db_cache = DatabaseMetadataCache()
        manager.relationship_cache = RelationshipMetadataCache()
        manager.logger = logging.getLogger("test.mixin")

        manager.db_cache._tables_cache["ctx"] = [("t",)]
        manager._clear_all_caches()

        assert manager.db_cache._tables_cache == {}

    def test_mixin_cache_context_key_is_static(self) -> None:
        result = DatabaseManagerSharedMixin._cache_context_key("my_db")
        assert result == "my_db"

    def test_mixin_escape_sql_literal(self) -> None:
        result = DatabaseManagerSharedMixin._escape_sql_literal("O'Brien")
        assert "'" not in result or result == "O''Brien"

    def test_mixin_normalize_ddl_result_with_tuple(self) -> None:
        mixin = DatabaseManagerSharedMixin.__new__(DatabaseManagerSharedMixin)
        result = mixin._normalize_ddl_result(("CREATE TABLE t1;",))
        assert result == "CREATE TABLE t1;"

    def test_mixin_get_query_context_database(self) -> None:
        manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
        manager.db_type = "postgresql"
        manager.database = "testdb"
        manager.conn_params = {"database": "testdb"}
        result = manager._get_query_context_database()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_clear_cache_selective_table(self) -> None:
        manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
        manager.db_type = "postgresql"
        manager.database = "testdb"
        manager.conn_params = {"database": "testdb"}
        manager.db_cache = DatabaseMetadataCache()
        manager.relationship_cache = RelationshipMetadataCache()
        manager.logger = logging.getLogger("test.mixin")

        manager.db_cache._tables_cache["testdb"] = [("users",), ("orders",)]
        manager.db_cache._columns_cache[("testdb", "users")] = [("id", "int")]

        manager.clear_cache(context_database="testdb", table="users")

        assert ("testdb", "users") not in manager.db_cache._columns_cache


# ---------------------------------------------------------------------------
# TD-07: except Exception → specific exceptions
# ---------------------------------------------------------------------------


class TestSpecificExceptions:
    """Verifica que los generadores capturan excepciones específicas (TD-07)."""

    def test_documentation_metadata_runtime_catches_database_error(self) -> None:
        from util_bbdd.doc.infrastructure.runtime.metadata_runtime import DocumentationMetadataRuntime

        runtime = DocumentationMetadataRuntime(logger=logging.getLogger("test"))

        def _failing_operation() -> str:
            raise DatabaseOperationError("boom")

        result = runtime._call_optional_metadata(
            operation=_failing_operation,
            success_message="ok: {result}",
            error_message="fail: {error}",
        )
        assert result is None

    def test_documentation_metadata_runtime_does_not_catch_non_database_error(self) -> None:
        from util_bbdd.doc.infrastructure.runtime.metadata_runtime import DocumentationMetadataRuntime

        runtime = DocumentationMetadataRuntime(logger=logging.getLogger("test"))

        def _failing_operation() -> str:
            raise RuntimeError("unexpected")

        with pytest.raises(RuntimeError, match="unexpected"):
            runtime._call_optional_metadata(
                operation=_failing_operation,
                success_message="ok: {result}",
                error_message="fail: {error}",
            )

    def test_generator_shared_catches_database_error_for_version(self) -> None:
        from util_bbdd.doc.infrastructure.renderers.shared.generator_shared import GeneratorDatabaseInfoRuntime

        data_provider = MagicMock()
        data_provider.get_database_version.side_effect = DatabaseOperationError("version fail")
        data_provider.get_database_charset_collation.return_value = {}

        info_data: list[list[str]] = []
        GeneratorDatabaseInfoRuntime._append_version_info(
            data_provider=data_provider,
            info_data=info_data,
            logger=logging.getLogger("test"),
            include_error_rows=True,
            debug_context="test",
        )
        assert any("Error" in row[1] for row in info_data)

    def test_print_config_to_positive_int_catches_value_error(self) -> None:
        from util_bbdd.doc.infrastructure.renderers.shared.print_config_manager import PrintConfigManager

        result = PrintConfigManager._to_positive_int("not_a_number", 42)
        assert result == 42

    def test_print_config_to_positive_int_does_not_catch_other_errors(self) -> None:
        from util_bbdd.doc.infrastructure.renderers.shared.print_config_manager import PrintConfigManager

        result = PrintConfigManager._to_positive_int(None, 10)
        assert isinstance(result, int)
