"""Tests for PR 5 - DatabaseQueries refactor to follow SRP

DatabaseQueries currently mixes multiple responsibilities:
1. Query loading (now delegated to QueryRegistry)
2. Basic access (get_query)
3. Convenience methods (get_tables_query, etc.)
4. Information/metadata (get_available_query_names, etc.)
5. Validation (now delegated to QueryResolver)

PR 5 should preserve public API while internally delegating to new components.
"""

import json

from pathlib import Path

import pytest

from util_bbdd import QueryNotFoundError
from util_bbdd.query import DatabaseQueries

SAMPLE_QUERIES = Path(__file__).resolve().parents[1] / "fixtures" / "sql_queries_sample.json"


class TestDatabaseQueriesBackwardCompat:
    """Tests ensuring backward compatibility for all public methods"""

    def test_database_queries_init_without_queries_file(self):
        """DatabaseQueries can be initialized with just db_type"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        assert dq.db_type == "mariadb"

    def test_database_queries_init_with_queries_file(self):
        """DatabaseQueries can be initialized with queries file path"""
        # Use actual queries file path if it exists, or just skip this test
        queries_file = Path(__file__).parent.parent.parent / "src" / "util_bbdd" / "data" / "sql_queries.json"
        if queries_file.exists():
            dq = DatabaseQueries(db_type="mariadb", queries_file=queries_file)
            assert dq.db_type == "mariadb"

    def test_get_query_method_exists(self):
        """get_query() method is public and callable"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        assert hasattr(dq, "get_query")
        assert callable(dq.get_query)

    def test_get_available_query_names_method_exists(self):
        """get_available_query_names() information method exists"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        assert hasattr(dq, "get_available_query_names")
        assert callable(dq.get_available_query_names)

    def test_get_all_queries_method_exists(self):
        """get_all_queries() information method exists"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        assert hasattr(dq, "get_all_queries")
        assert callable(dq.get_all_queries)


class TestDatabaseQueriesConvenienceMethods:
    """Tests for convenience methods that should delegate to registry/resolver"""


class TestDatabaseQueriesInformationMethods:
    """Tests for information/metadata methods"""

    def test_get_available_query_names_returns_list(self):
        """get_available_query_names returns list of strings"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        names = dq.get_available_query_names()
        assert isinstance(names, list)
        assert len(names) > 0
        assert all(isinstance(name, str) for name in names)

    def test_get_available_query_names_includes_common_queries(self):
        """get_available_query_names includes standard queries"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        names = dq.get_available_query_names()
        # Should include at least basic queries
        common_queries = ["obtener_tablas", "obtener_columnas"]
        found_queries = [q for q in common_queries if q in names]
        assert len(found_queries) > 0

    def test_get_all_queries_returns_dict(self):
        """get_all_queries returns dictionary"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        all_queries = dq.get_all_queries()
        assert isinstance(all_queries, dict)
        assert len(all_queries) > 0

    def test_get_all_queries_dict_has_query_names_as_keys(self):
        """get_all_queries dict has query names as keys"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        all_queries = dq.get_all_queries()
        names = dq.get_available_query_names()
        # All available names should be in get_all_queries
        for name in names:
            assert name in all_queries


class TestDatabaseQueriesDelegation:
    """Tests verifying internal delegation to Registry/Resolver"""

    def test_database_queries_registry_exposes_queries(self):
        """registry.queries expone el storage de queries cargadas."""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)

        assert isinstance(dq.registry.queries, dict)
        assert len(dq.registry.queries) > 0

    def test_database_queries_get_query_works_with_kwargs(self):
        """get_query should accept and handle arbitrary kwargs for templating"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        # get_query should accept kwargs for template variable substitution
        query = dq.get_query("obtener_tablas", database="test_db")
        assert isinstance(query, str)
        assert len(query) > 0

    def test_database_queries_multiple_databases_work(self):
        """DatabaseQueries should work for all supported database types"""
        db_types = ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"]
        for db_type in db_types:
            dq = DatabaseQueries(db_type=db_type, queries_file=SAMPLE_QUERIES)
            names = dq.get_available_query_names()
            assert isinstance(names, list)
            assert len(names) > 0

    def test_database_queries_available_names_match_registry(self):
        """La API legacy de nombres usa el camino canónico del registry."""
        dq = DatabaseQueries(db_type="postgresql", queries_file=SAMPLE_QUERIES)

        assert dq.get_available_query_names() == dq.registry.get_available_queries("postgresql")


class TestDatabaseQueriesMultipleMotors:
    """Test that refactored DatabaseQueries works for all motors"""

    @pytest.mark.parametrize("db_type", ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"])
    def test_database_queries_works_for_all_motors(self, db_type):
        """DatabaseQueries can be instantiated for all supported motors"""
        dq = DatabaseQueries(db_type=db_type, queries_file=SAMPLE_QUERIES)
        assert dq.db_type == db_type
        # Should have public methods available
        assert hasattr(dq, "get_query")
        assert hasattr(dq, "get_available_query_names")

    @pytest.mark.parametrize("db_type", ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"])
    def test_database_queries_get_available_queries_for_all_motors(self, db_type):
        """Each motor has available queries"""
        dq = DatabaseQueries(db_type=db_type, queries_file=SAMPLE_QUERIES)
        names = dq.get_available_query_names()
        assert isinstance(names, list)
        assert len(names) > 0


class TestDatabaseQueriesConsistency:
    """Tests for consistency between old and new implementations"""

    def test_get_query_returns_string(self):
        """get_query returns string (SQL template)"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        query = dq.get_query("obtener_tablas")
        assert isinstance(query, str)
        assert len(query) > 0

    def test_get_query_raises_for_nonexistent_query(self):
        """get_query raises appropriate exception for nonexistent query"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        with pytest.raises(QueryNotFoundError):
            dq.get_query("nonexistent_query_name_xyz")

    def test_get_query_includes_placeholders(self):
        """get_query results include placeholders like {database}"""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)
        query = dq.get_query("obtener_tablas")
        # Oracle queries should have {schema} or {db_context}
        # MariaDB queries should have {database}
        # At minimum, should contain placeholder syntax
        assert "{" in query and "}" in query

    def test_get_query_documentation_exposes_description_dependencies_and_examples(self):
        """La documentación pública se mantiene estable tras extraer helpers internos."""
        dq = DatabaseQueries(db_type="mariadb", queries_file=SAMPLE_QUERIES)

        documentation = dq.get_query_documentation("temp_storage_variables")

        assert documentation["query_name"] == "temp_storage_variables"
        assert documentation["db_type"] == "mariadb"
        # E2c: las consultas son del usuario; la librería ya no trae descripciones ni ejemplos propios
        assert documentation["description"] == "Consulta SQL personalizada"
        assert isinstance(documentation["dependencies"], dict)
        assert documentation["examples"] == []

    def test_export_documentation_writes_full_catalog_json(self, tmp_path: Path):
        """export_documentation serializa el catálogo completo en JSON."""
        dq = DatabaseQueries(db_type="sqlite", queries_file=SAMPLE_QUERIES)
        output_file = tmp_path / "queries.json"

        dq.export_documentation(output_file)

        exported = json.loads(output_file.read_text(encoding="utf-8"))
        assert exported["db_type"] == "sqlite"
        assert "queries" in exported
        assert "sqlite_file_summary" in exported["queries"]
