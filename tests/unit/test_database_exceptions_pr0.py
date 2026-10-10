"""
Tests para excepciones (PR 0)

Pruebas unitarias para la jerarquía de excepciones actualizada
en database_exceptions.py.
"""

from util_bbdd import DatabaseException
from util_bbdd.exceptions import (
    InvalidDatabaseType,
    QueryError,
    QueryNotFoundError,
    QueryParameterError,
    QueryTimeoutError,
    QueryValidationError,
)


class TestExceptionHierarchy:
    """Tests para la jerarquía de excepciones"""

    def test_query_error_inherits_from_database_error(self):
        """Test: QueryError hereda de DatabaseException"""
        assert issubclass(QueryError, DatabaseException)

    def test_query_not_found_error_hierarchy(self):
        """Test: QueryNotFoundError hereda de QueryError"""
        assert issubclass(QueryNotFoundError, QueryError)
        assert issubclass(QueryNotFoundError, DatabaseException)

    def test_query_validation_error_hierarchy(self):
        """Test: QueryValidationError hereda de QueryError"""
        assert issubclass(QueryValidationError, QueryError)
        assert issubclass(QueryValidationError, DatabaseException)

    def test_query_parameter_error_hierarchy(self):
        """Test: QueryParameterError hereda de QueryError"""
        assert issubclass(QueryParameterError, QueryError)
        assert issubclass(QueryParameterError, DatabaseException)

    def test_query_timeout_error_hierarchy(self):
        """Test: QueryTimeoutError hereda de QueryError"""
        assert issubclass(QueryTimeoutError, QueryError)
        assert issubclass(QueryTimeoutError, DatabaseException)

    def test_database_type_not_supported_error_hierarchy(self):
        """Test: InvalidDatabaseType hereda de DatabaseException"""
        assert issubclass(InvalidDatabaseType, DatabaseException)


class TestQueryNotFoundError:
    """Tests para QueryNotFoundError"""

    def test_query_not_found_error_instantiation(self):
        """Test: puede instanciarse"""
        exc = QueryNotFoundError("Query 'test' not found")
        assert str(exc)

    def test_query_not_found_error_message(self):
        """Test: captura mensaje de error"""
        msg = "Query 'test_query' not found for db_type 'mariadb'"
        exc = QueryNotFoundError(msg)
        assert msg in str(exc)

    def test_query_not_found_error_with_cause(self):
        """Test: puede tener causa (for raise ... from err)"""
        try:
            try:
                raise KeyError("not found")
            except KeyError as e:
                raise QueryNotFoundError("Query not found") from e
        except QueryNotFoundError as exc:
            assert exc.__cause__ is not None
            assert isinstance(exc.__cause__, KeyError)


class TestQueryValidationError:
    """Tests para QueryValidationError"""

    def test_query_validation_error_instantiation(self):
        """Test: puede instanciarse"""
        exc = QueryValidationError("Validation failed")
        assert str(exc)

    def test_query_validation_error_message(self):
        """Test: captura mensaje de error"""
        msg = "Missing required parameter: 'database'"
        exc = QueryValidationError(msg)
        assert msg in str(exc)

    def test_query_validation_error_with_cause(self):
        """Test: puede tener causa"""
        try:
            try:
                raise ValueError("Invalid parameter")
            except ValueError as e:
                raise QueryValidationError("Validation failed") from e
        except QueryValidationError as exc:
            assert exc.__cause__ is not None


class TestQueryParameterError:
    """Tests para QueryParameterError"""

    def test_query_parameter_error_instantiation(self):
        """Test: puede instanciarse"""
        exc = QueryParameterError("Invalid parameter")
        assert str(exc)

    def test_query_parameter_error_message(self):
        """Test: captura mensaje de error"""
        msg = "Parameter 'table_name' is invalid for HSQLDB"
        exc = QueryParameterError(msg)
        assert msg in str(exc)


class TestQueryTimeoutError:
    """Tests para QueryTimeoutError"""

    def test_query_timeout_error_instantiation(self):
        """Test: puede instanciarse"""
        exc = QueryTimeoutError("Query execution timed out")
        assert str(exc)

    def test_query_timeout_error_message(self):
        """Test: captura mensaje de error"""
        msg = "Query execution exceeded timeout of 5.0 seconds"
        exc = QueryTimeoutError(msg)
        assert msg in str(exc)

    def test_query_timeout_error_with_cause(self):
        """Test: puede tener causa de TimeoutError"""
        try:
            try:
                raise TimeoutError("Operation timed out")
            except TimeoutError as e:
                raise QueryTimeoutError("Query timed out") from e
        except QueryTimeoutError as exc:
            assert exc.__cause__ is not None


class TestInvalidDatabaseType:
    """Tests para InvalidDatabaseType"""

    def test_database_type_not_supported_error_instantiation(self):
        """Test: puede instanciarse"""
        exc = InvalidDatabaseType("db_type 'nosql' not supported")
        assert str(exc)

    def test_database_type_not_supported_error_message(self):
        """Test: captura mensaje de error"""
        msg = "Database type 'mongodb' is not supported"
        exc = InvalidDatabaseType(msg)
        assert msg in str(exc)


class TestLegacyAliasRemoval:
    """Tests para validar eliminación definitiva de aliases legacy."""

    def test_database_query_error_alias_removed(self):
        """DatabaseQueryError no debe existir en el paquete raíz."""
        import util_bbdd

        assert not hasattr(util_bbdd, "DatabaseQueryError")


class TestExceptionInstantiation:
    """Tests generales de instanciación"""

    def test_all_query_errors_can_be_instantiated(self):
        """Test: todas las excepciones de Query pueden instanciarse"""
        msg = "Test message"

        exc1 = QueryError(msg)
        exc2 = QueryNotFoundError(msg)
        exc3 = QueryValidationError(msg)
        exc4 = QueryParameterError(msg)
        exc5 = QueryTimeoutError(msg)

        assert all(isinstance(e, DatabaseException) for e in [exc1, exc2, exc3, exc4, exc5])

    def test_exception_message_in_string_representation(self):
        """Test: mensaje aparece en str(exception)"""
        msg = "Custom error message"
        exc = QueryNotFoundError(msg)

        assert msg in str(exc)
