"""
Tests for SQL Server Query Validator
"""

from util_bbdd.models import QueryDefinition
from util_bbdd.validators.sqlserver_validator import SQLServerValidator


class TestSQLServerValidatorBasics:
    """Pruebas básicas del validador SQL Server"""

    def test_validator_init(self):
        """SQLServerValidator se inicia correctamente"""
        validator = SQLServerValidator()
        assert validator is not None
        assert validator.db_type == "sqlserver"


class TestSQLServerValidatorSchema:
    """Pruebas de validación de schema"""

    def test_valid_schema(self):
        """Acepta schema válido"""
        validator = SQLServerValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlserver",
            sql_template="SELECT * FROM users",
            required_params=["esquema"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"esquema": "dbo"})
        assert is_valid is True

    def test_empty_schema(self):
        """Falla con schema vacío"""
        validator = SQLServerValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlserver",
            sql_template="SELECT * FROM users",
            required_params=["esquema"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"esquema": ""})
        assert is_valid is False

    def test_none_schema(self):
        """Falla con schema None"""
        validator = SQLServerValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlserver",
            sql_template="SELECT * FROM users",
            required_params=["esquema"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"esquema": None})
        assert is_valid is False

    def test_custom_schema(self):
        """Acepta schema personalizado"""
        validator = SQLServerValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlserver",
            sql_template="SELECT * FROM users",
            required_params=["esquema"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"esquema": "custom_schema"})
        assert is_valid is True


class TestSQLServerValidatorNoSchema:
    """Pruebas sin parámetro schema"""

    def test_no_schema_required(self):
        """Pasa sin schema cuando no es requerido"""
        validator = SQLServerValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlserver",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {})
        assert is_valid is True

    def test_multiple_params(self):
        """Acepta múltiples parámetros"""
        validator = SQLServerValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlserver",
            sql_template="SELECT * FROM users",
            required_params=["esquema", "database"],
        )

        params = {"esquema": "dbo", "database": "mydb"}
        is_valid, warnings = validator.validate_parameters(query_def, params)
        assert is_valid is True
