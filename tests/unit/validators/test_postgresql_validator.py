"""
Tests for PostgreSQL Query Validator
"""

from util_bbdd.models import QueryDefinition
from util_bbdd.validators.postgresql_validator import PostgreSQLValidator


class TestPostgreSQLValidatorBasics:
    """Pruebas básicas del validador PostgreSQL"""

    def test_validator_init(self):
        """PostgreSQLValidator se inicia correctamente"""
        validator = PostgreSQLValidator()
        assert validator is not None
        assert validator.db_type == "postgresql"


class TestPostgreSQLValidatorDatabaseParam:
    """Pruebas de validación de parámetro database"""

    def test_valid_database(self):
        """Acepta nombre de BD válido"""
        validator = PostgreSQLValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="postgresql",
            sql_template="SELECT * FROM users",
            required_params=["database"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"database": "my_database"})
        assert is_valid is True

    def test_missing_database(self):
        """Falla si falta database"""
        validator = PostgreSQLValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="postgresql",
            sql_template="SELECT * FROM users",
            required_params=["database"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {})
        assert is_valid is False

    def test_empty_database(self):
        """Falla si database está vacío"""
        validator = PostgreSQLValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="postgresql",
            sql_template="SELECT * FROM users",
            required_params=["database"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"database": ""})
        assert is_valid is False

    def test_none_database(self):
        """Falla si database es None"""
        validator = PostgreSQLValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="postgresql",
            sql_template="SELECT * FROM users",
            required_params=["database"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"database": None})
        assert is_valid is False


class TestPostgreSQLValidatorSchemaParam:
    """Pruebas de validación de parámetro schema"""

    def test_valid_schema(self):
        """Acepta schema válido"""
        validator = PostgreSQLValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="postgresql",
            sql_template="SELECT * FROM users",
            required_params=["schema"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"schema": "public"})
        assert is_valid is True

    def test_empty_schema(self):
        """Falla si schema está vacío"""
        validator = PostgreSQLValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="postgresql",
            sql_template="SELECT * FROM users",
            required_params=["schema"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"schema": ""})
        assert is_valid is False


class TestPostgreSQLValidatorBothParams:
    """Pruebas con database y schema"""

    def test_both_database_and_schema(self):
        """Acepta database AND schema juntos"""
        validator = PostgreSQLValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="postgresql",
            sql_template="SELECT * FROM users",
            required_params=["database", "schema"],
        )

        params = {"database": "my_db", "schema": "public"}
        is_valid, _ = validator.validate_parameters(query_def, params)
        assert is_valid is True

    def test_database_missing_schema_valid(self):
        """Falla si database falta aunque schema sea válido"""
        validator = PostgreSQLValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="postgresql",
            sql_template="SELECT * FROM users",
            required_params=["database"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"schema": "public"})
        assert is_valid is False


class TestPostgreSQLValidatorNoRequiredParams:
    """Pruebas sin parámetros requeridos"""

    def test_no_required_params(self):
        """Pasa sin parámetros requeridos"""
        validator = PostgreSQLValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="postgresql",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        is_valid, _ = validator.validate_parameters(query_def, {})
        assert is_valid is True
