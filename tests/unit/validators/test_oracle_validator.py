"""
Tests for Oracle Query Validator
"""

from util_bbdd.models import QueryDefinition
from util_bbdd.validators.oracle_validator import OracleValidator


class TestOracleValidatorBasics:
    """Pruebas básicas del validador Oracle"""

    def test_validator_init(self):
        """OracleValidator se inicia correctamente"""
        validator = OracleValidator()
        assert validator is not None
        assert validator.db_type == "oracle"


class TestOracleValidatorSchemaFormat:
    """Pruebas de validación de formato de schema"""

    def test_valid_schema_simple(self):
        """Acepta schema simple"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="oracle",
            sql_template="SELECT * FROM users",
            required_params=["schema"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"schema": "MY_SCHEMA"})
        assert is_valid is True

    def test_valid_schema_with_special_chars(self):
        """Acepta schema con caracteres especiales válidos"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="oracle",
            sql_template="SELECT * FROM users",
            required_params=["schema"],
        )

        valid_schemas = ["SCHEMA_1", "MY$SCHEMA", "SCHEMA#1", "MY_S"]
        for schema in valid_schemas:
            is_valid, warnings = validator.validate_parameters(query_def, {"schema": schema})
            assert is_valid is True, f"Failed for schema: {schema}"

    def test_schema_too_long(self):
        """Falla si schema excede 30 caracteres"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="oracle",
            sql_template="SELECT * FROM users",
            required_params=["schema"],
        )

        long_schema = "A" * 31  # Mayor a 30 caracteres
        is_valid, warnings = validator.validate_parameters(query_def, {"schema": long_schema})
        assert is_valid is False

    def test_schema_30_chars_exactly(self):
        """Acepta schema de exactamente 30 caracteres"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="oracle",
            sql_template="SELECT * FROM users",
            required_params=["schema"],
        )

        schema_30 = "A" * 30
        is_valid, warnings = validator.validate_parameters(query_def, {"schema": schema_30})
        assert is_valid is True

    def test_schema_invalid_characters(self):
        """Falla con caracteres inválidos en schema"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="oracle",
            sql_template="SELECT * FROM users",
            required_params=["schema"],
        )

        invalid_schemas = ["SCHEMA-123", "MY.SCHEMA", "SCHEMA@1", "MY SCHEMA"]
        for schema in invalid_schemas:
            is_valid, warnings = validator.validate_parameters(query_def, {"schema": schema})
            assert is_valid is False, f"Should fail for schema: {schema}"

    def test_empty_schema(self):
        """Falla con schema vacío"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="oracle",
            sql_template="SELECT * FROM users",
            required_params=["schema"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"schema": ""})
        assert is_valid is False

    def test_none_schema(self):
        """Falla con schema None"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="oracle",
            sql_template="SELECT * FROM users",
            required_params=["schema"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"schema": None})
        assert is_valid is False


class TestOracleValidatorNoSchema:
    """Pruebas sin parámetro schema"""

    def test_no_schema_required(self):
        """Pasa sin schema cuando no es requerido"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="oracle",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {})
        assert is_valid is True
