"""
Simplified tests for QueryResolver - Query resolution and validation
Focus on core functionality without complex mocking
"""

from unittest.mock import MagicMock

import pytest

from util_bbdd import QueryParameterError, QueryValidationError
from util_bbdd.models import QueryDefinition, ResolvedQuery
from util_bbdd.query import QueryResolver


@pytest.fixture
def mock_registry():
    """Fixture providing a mock QueryRegistry"""
    m = MagicMock()
    return m


@pytest.fixture
def resolver(mock_registry):
    """Fixture providing a QueryResolver with mocked registry"""
    return QueryResolver(registry=mock_registry, db_type="mariadb")


class TestQueryResolverBasics:
    """Pruebas básicas del QueryResolver"""

    def test_resolver_init(self):
        """QueryResolver se inicia correctamente"""
        resolver = QueryResolver()
        assert resolver is not None

    def test_resolver_with_mock_registry(self, resolver):
        """QueryResolver se inicia con registry mock"""
        assert resolver is not None

    def test_resolve_returns_resolved_query(self, resolver, mock_registry):
        """Resolve retorna ResolvedQuery"""
        query_def = QueryDefinition(
            name="test",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=[],
        )
        mock_registry.get_query_definition.return_value = query_def

        result = resolver.resolve("test", {})
        assert isinstance(result, ResolvedQuery)

    def test_resolve_with_parameters(self, resolver, mock_registry):
        """Resolve interpola parámetros"""
        query_def = QueryDefinition(
            name="select_id",
            db_type="mariadb",
            sql_template="SELECT * FROM users WHERE id = {id}",
            required_params=["id"],
        )
        mock_registry.get_query_definition.return_value = query_def

        result = resolver.resolve("select_id", {"id": 123})
        assert result.query_definition.name == "select_id"
        assert result.query_definition.db_type == "mariadb"

    def test_resolve_fails_validation_missing_param(self, resolver, mock_registry):
        """Resolve falla si falta parámetro requerido"""
        query_def = QueryDefinition(
            name="select_id",
            db_type="mariadb",
            sql_template="SELECT * FROM users WHERE id = {id}",
            required_params=["id"],
        )
        mock_registry.get_query_definition.return_value = query_def

        with pytest.raises((QueryParameterError, QueryValidationError)):
            resolver.resolve("select_id", {})

    def test_resolve_uses_bound_db_type_when_not_provided(self, mock_registry):
        """Permite resolver sin db_type explícito cuando está ligado."""
        query_def = QueryDefinition(
            name="test",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=[],
        )
        mock_registry.get_query_definition.return_value = query_def
        resolver = QueryResolver(registry=mock_registry, db_type="mariadb")

        result = resolver.resolve("test", params={})

        assert isinstance(result, ResolvedQuery)
        mock_registry.get_query_definition.assert_called_once_with("mariadb", "test")

    def test_resolve_without_db_type_and_without_binding_raises(self, mock_registry):
        """Falla con QueryParameterError si no hay db_type ni binding."""
        with pytest.raises(QueryParameterError):
            QueryResolver(registry=mock_registry).resolve("test", params={})


class TestQueryResolverInterpolation:
    """Pruebas de interpolación de SQL"""

    def test_interpolate_no_params(self, resolver):
        """Interpola SQL sin parámetros"""
        template = "SELECT * FROM users"
        result = resolver._interpolate_sql(template, {})
        assert result == "SELECT * FROM users"

    def test_interpolate_single_param(self, resolver):
        """Interpola SQL con un parámetro"""
        template = "SELECT * FROM users WHERE id = {id}"
        result = resolver._interpolate_sql(template, {"id": "123"})
        assert "123" in result
        assert "{id}" not in result

    def test_interpolate_multiple_params(self, resolver):
        """Interpola SQL con múltiples parámetros"""
        template = "SELECT * FROM {table} WHERE id > {min} AND id < {max}"
        result = resolver._interpolate_sql(template, {"table": "users", "min": 10, "max": 20})
        assert "users" in result
        assert "10" in result
        assert "20" in result
        assert "{" not in result


class TestQueryResolverMetadata:
    """Pruebas de metadatos"""

    def test_resolved_query_has_fields(self, resolver, mock_registry):
        """ResolvedQuery tiene todos los campos requeridos"""
        query_def = QueryDefinition(
            name="test",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=[],
        )
        mock_registry.get_query_definition.return_value = query_def

        result = resolver.resolve("test", {})

        assert hasattr(result, "query_definition")
        assert hasattr(result, "final_sql")
        assert hasattr(result, "validated")
        assert hasattr(result, "warnings")
        assert hasattr(result, "metadata")

    def test_resolved_query_has_elapsed_time(self, resolver, mock_registry):
        """ResolvedQuery metadata contiene elapsed_ms"""
        query_def = QueryDefinition(
            name="test",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=[],
        )
        mock_registry.get_query_definition.return_value = query_def

        result = resolver.resolve("test", {})

        assert "elapsed_ms" in result.metadata
        assert result.metadata["elapsed_ms"] >= 0


class TestQueryResolverByDatabase:
    """Pruebas por tipo de BD"""

    @pytest.mark.parametrize(
        "db_type",
        ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"],
    )
    def test_resolve_each_database_type(self, db_type):
        """Resuelve queries para cada tipo de BD"""
        query_def = QueryDefinition(
            name=f"query_{db_type}",
            db_type=db_type,
            sql_template="SELECT * FROM data",
            required_params=[],
        )

        mock_registry = MagicMock()
        mock_registry.get_query_definition.return_value = query_def
        resolver = QueryResolver(registry=mock_registry, db_type=db_type)

        result = resolver.resolve(f"query_{db_type}", {})
        assert result.query_definition.db_type == db_type


class TestQueryResolverErrors:
    """Pruebas de manejo de errores"""

    def test_unsupported_db_type_raises_error(self, resolver, mock_registry):
        """Falla con tipo de BD no soportado"""
        query_def = QueryDefinition(
            name="test",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=[],
        )
        mock_registry.get_query_definition.return_value = query_def

        resolver_unsupported = QueryResolver(registry=mock_registry, db_type="unsupported_db_type")

        # QueryResolver wraps unexpected exceptions in QueryParameterError
        with pytest.raises(QueryParameterError):
            resolver_unsupported.resolve("test", {})

    def test_query_not_found_raises_error(self, resolver, mock_registry):
        """Falla si query no existe"""
        from util_bbdd import QueryNotFoundError

        mock_registry.get_query_definition.side_effect = QueryNotFoundError("test_query")

        # QueryResolver re-raises QueryNotFoundError without wrapping
        with pytest.raises(QueryNotFoundError):
            resolver.resolve("test_query", {})
