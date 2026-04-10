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


class TestDatabaseQueriesBackwardCompat:
    """Tests ensuring backward compatibility for all public methods"""

    def test_database_queries_init_without_queries_file(self):
        """DatabaseQueries can be initialized with just db_type"""
        dq = DatabaseQueries(db_type="mariadb")
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
        dq = DatabaseQueries(db_type="mariadb")
        assert hasattr(dq, "get_query")
        assert callable(dq.get_query)

    def test_get_tables_query_method_exists(self):
        """get_tables_query() convenience method exists"""
        dq = DatabaseQueries(db_type="mariadb")
        assert hasattr(dq, "get_tables_query")
        assert callable(dq.get_tables_query)

    def test_get_columns_query_method_exists(self):
        """get_columns_query() convenience method exists"""
        dq = DatabaseQueries(db_type="mariadb")
        assert hasattr(dq, "get_columns_query")
        assert callable(dq.get_columns_query)

    def test_get_views_query_method_exists(self):
        """get_views_query() convenience method exists"""
        dq = DatabaseQueries(db_type="mariadb")
        assert hasattr(dq, "get_views_query")
        assert callable(dq.get_views_query)

    def test_get_routines_query_method_exists(self):
        """get_routines_query() convenience method exists"""
        dq = DatabaseQueries(db_type="mariadb")
        assert hasattr(dq, "get_routines_query")
        assert callable(dq.get_routines_query)

    def test_get_available_query_names_method_exists(self):
        """get_available_query_names() information method exists"""
        dq = DatabaseQueries(db_type="mariadb")
        assert hasattr(dq, "get_available_query_names")
        assert callable(dq.get_available_query_names)

    def test_get_all_queries_method_exists(self):
        """get_all_queries() information method exists"""
        dq = DatabaseQueries(db_type="mariadb")
        assert hasattr(dq, "get_all_queries")
        assert callable(dq.get_all_queries)


class TestDatabaseQueriesConvenienceMethods:
    """Tests for convenience methods that should delegate to registry/resolver"""

    def test_get_tables_query_for_mariadb(self):
        """get_tables_query returns SQL template for MariaDB"""
        dq = DatabaseQueries(db_type="mariadb")
        query = dq.get_tables_query(database="test_db")
        # Should return non-empty SQL template
        assert isinstance(query, str)
        assert len(query) > 0
        # Should contain references to database
        assert "test_db" in query or "database" in query.lower()

    def test_get_columns_query_for_mariadb(self):
        """get_columns_query returns SQL template for MariaDB"""
        dq = DatabaseQueries(db_type="mariadb")
        query = dq.get_columns_query(database="test_db", table="test_table")
        assert isinstance(query, str)
        assert len(query) > 0

    def test_get_views_query_for_mariadb(self):
        """get_views_query returns SQL template for MariaDB"""
        dq = DatabaseQueries(db_type="mariadb")
        query = dq.get_views_query(database="test_db")
        assert isinstance(query, str)
        assert len(query) > 0

    def test_get_routines_query_for_mariadb(self):
        """get_routines_query returns SQL template for MariaDB"""
        dq = DatabaseQueries(db_type="mariadb")
        query = dq.get_routines_query(database="test_db")
        assert isinstance(query, str)
        assert len(query) > 0


class TestDatabaseQueriesInformationMethods:
    """Tests for information/metadata methods"""

    def test_get_available_query_names_returns_list(self):
        """get_available_query_names returns list of strings"""
        dq = DatabaseQueries(db_type="mariadb")
        names = dq.get_available_query_names()
        assert isinstance(names, list)
        assert len(names) > 0
        assert all(isinstance(name, str) for name in names)

    def test_get_available_query_names_includes_common_queries(self):
        """get_available_query_names includes standard queries"""
        dq = DatabaseQueries(db_type="mariadb")
        names = dq.get_available_query_names()
        # Should include at least basic queries
        common_queries = ["obtener_tablas", "obtener_columnas"]
        found_queries = [q for q in common_queries if q in names]
        assert len(found_queries) > 0

    def test_get_all_queries_returns_dict(self):
        """get_all_queries returns dictionary"""
        dq = DatabaseQueries(db_type="mariadb")
        all_queries = dq.get_all_queries()
        assert isinstance(all_queries, dict)
        assert len(all_queries) > 0

    def test_get_all_queries_dict_has_query_names_as_keys(self):
        """get_all_queries dict has query names as keys"""
        dq = DatabaseQueries(db_type="mariadb")
        all_queries = dq.get_all_queries()
        names = dq.get_available_query_names()
        # All available names should be in get_all_queries
        for name in names:
            assert name in all_queries


class TestDatabaseQueriesDelegation:
    """Tests verifying internal delegation to Registry/Resolver"""

    def test_database_queries_queries_property_delegates_to_registry(self):
        """queries expone el storage del registry en lugar de cache duplicada."""
        dq = DatabaseQueries(db_type="mariadb")

        assert dq.queries is dq.registry.queries

    def test_database_queries_get_query_works_with_kwargs(self):
        """get_query should accept and handle arbitrary kwargs for templating"""
        dq = DatabaseQueries(db_type="mariadb")
        # get_query should accept kwargs for template variable substitution
        query = dq.get_query("obtener_tablas", database="test_db")
        assert isinstance(query, str)
        assert len(query) > 0

    def test_database_queries_multiple_databases_work(self):
        """DatabaseQueries should work for all supported database types"""
        db_types = ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"]
        for db_type in db_types:
            dq = DatabaseQueries(db_type=db_type)
            names = dq.get_available_query_names()
            assert isinstance(names, list)
            assert len(names) > 0

    def test_database_queries_available_names_match_registry(self):
        """La API legacy de nombres usa el camino canónico del registry."""
        dq = DatabaseQueries(db_type="postgresql")

        assert dq.get_available_query_names() == dq.registry.get_available_queries("postgresql")


class TestDatabaseQueriesMultipleMotors:
    """Test that refactored DatabaseQueries works for all motors"""

    @pytest.mark.parametrize("db_type", ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"])
    def test_database_queries_works_for_all_motors(self, db_type):
        """DatabaseQueries can be instantiated for all supported motors"""
        dq = DatabaseQueries(db_type=db_type)
        assert dq.db_type == db_type
        # Should have public methods available
        assert hasattr(dq, "get_query")
        assert hasattr(dq, "get_available_query_names")

    @pytest.mark.parametrize("db_type", ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"])
    def test_database_queries_get_available_queries_for_all_motors(self, db_type):
        """Each motor has available queries"""
        dq = DatabaseQueries(db_type=db_type)
        names = dq.get_available_query_names()
        assert isinstance(names, list)
        assert len(names) > 0


class TestDatabaseQueriesConsistency:
    """Tests for consistency between old and new implementations"""

    def test_get_query_returns_string(self):
        """get_query returns string (SQL template)"""
        dq = DatabaseQueries(db_type="mariadb")
        query = dq.get_query("obtener_tablas")
        assert isinstance(query, str)
        assert len(query) > 0

    def test_get_query_raises_for_nonexistent_query(self):
        """get_query raises appropriate exception for nonexistent query"""
        dq = DatabaseQueries(db_type="mariadb")
        with pytest.raises(QueryNotFoundError):
            dq.get_query("nonexistent_query_name_xyz")

    def test_get_query_includes_placeholders(self):
        """get_query results include placeholders like {database}"""
        dq = DatabaseQueries(db_type="mariadb")
        query = dq.get_query("obtener_tablas")
        # Oracle queries should have {schema} or {db_context}
        # MariaDB queries should have {database}
        # At minimum, should contain placeholder syntax
        assert "{" in query and "}" in query

    def test_postgresql_storage_query_includes_filesystem_fallback_for_builtin_tablespaces(self):
        """PostgreSQL storage query should resolve path for pg_default/pg_global too."""
        dq = DatabaseQueries(db_type="postgresql")
        query = dq.get_query("ficheros_fisicos", tablespace="pg_default")

        assert "current_setting('data_directory')" in query
        assert "pg_tablespace_location" in query
        assert "pg_tablespace_size" in query

    def test_mariadb_storage_queries_include_temp_tablespaces_and_temp_variables(self):
        """MariaDB expone inventario temporal y variable InnoDB para documentacion."""
        dq = DatabaseQueries(db_type="mariadb")

        storage_queries = dq.get_storage_inventory_queries(database="test_db")
        temp_tablespaces_sql = dq.get_query("temp_tablespaces")
        temp_variables_sql = dq.get_query("temp_storage_variables")

        assert "temp_tablespaces" in storage_queries
        assert "temp_storage_variables" in storage_queries
        assert "information_schema.FILES" in storage_queries["temp_tablespaces"]
        assert "FILE_TYPE = 'TEMPORARY'" in temp_tablespaces_sql
        assert "innodb_temp_data_file_path" in temp_variables_sql

    def test_sqlite_storage_queries_use_explicit_summary_key(self):
        """SQLite expone resumen del fichero principal como capacidad propia."""
        dq = DatabaseQueries(db_type="sqlite")

        storage_queries = dq.get_storage_inventory_queries()

        assert "primary" in storage_queries
        assert "sqlite_file_summary" in storage_queries
        assert "ficheros_fisicos_adicional" not in storage_queries
        assert "pragma_page_count" in storage_queries["sqlite_file_summary"].lower()

    def test_get_query_documentation_exposes_description_dependencies_and_examples(self):
        """La documentación pública se mantiene estable tras extraer helpers internos."""
        dq = DatabaseQueries(db_type="mariadb")

        documentation = dq.get_query_documentation("temp_storage_variables")

        assert documentation["query_name"] == "temp_storage_variables"
        assert documentation["db_type"] == "mariadb"
        assert documentation["description"] == "Obtiene variables de configuración del almacenamiento temporal"
        assert isinstance(documentation["dependencies"], dict)
        assert isinstance(documentation["examples"], list)
        assert documentation["examples"][0]["description"].startswith("Leer innodb_temp_data_file_path")

    def test_export_documentation_writes_full_catalog_json(self, tmp_path: Path):
        """export_documentation serializa el catálogo completo en JSON."""
        dq = DatabaseQueries(db_type="sqlite")
        output_file = tmp_path / "queries.json"

        dq.export_documentation(output_file)

        exported = json.loads(output_file.read_text(encoding="utf-8"))
        assert exported["db_type"] == "sqlite"
        assert "queries" in exported
        assert "sqlite_file_summary" in exported["queries"]
