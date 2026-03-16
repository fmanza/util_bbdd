"""
Tests for HSQLDB Query Validator
"""

from util_bbdd.models import QueryDefinition
from util_bbdd.validators.hsqldb_validator import HSQLDBValidator


class TestHSQLDBValidatorBasics:
    """Pruebas básicas del validador HSQLDB"""

    def test_validator_init(self):
        """HSQLDBValidator se inicia correctamente"""
        validator = HSQLDBValidator()
        assert validator is not None
        assert validator.db_type == "hsqldb"


class TestHSQLDBValidatorTableName:
    """Pruebas de validación de nombre de tabla"""

    def test_valid_table_name_simple(self):
        """Acepta nombre de tabla simple"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="hsqldb",
            sql_template="SELECT * FROM data",
            required_params=["table"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"table": "users"})
        assert is_valid is True

    def test_valid_table_name_with_underscore(self):
        """Acepta nombre de tabla con underscore"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="hsqldb",
            sql_template="SELECT * FROM data",
            required_params=["table"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"table": "user_data"})
        assert is_valid is True

    def test_valid_table_name_with_numbers(self):
        """Acepta nombre de tabla con números"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="hsqldb",
            sql_template="SELECT * FROM data",
            required_params=["table"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"table": "table123"})
        assert is_valid is True

    def test_valid_table_name_with_dash(self):
        """Acepta nombre de tabla con guión"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="hsqldb",
            sql_template="SELECT * FROM data",
            required_params=["table"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"table": "user-data"})
        assert is_valid is True

    def test_valid_table_name_complex(self):
        """Acepta nombre de tabla complejo"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="hsqldb",
            sql_template="SELECT * FROM data",
            required_params=["table"],
        )

        valid_tables = ["user_data_2024", "users-log", "table_1_test", "T123"]
        for table in valid_tables:
            is_valid, _ = validator.validate_parameters(query_def, {"table": table})
            assert is_valid is True, f"Failed for table: {table}"

    def test_table_invalid_special_chars(self):
        """Falla con caracteres especiales inválidos"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="hsqldb",
            sql_template="SELECT * FROM data",
            required_params=["table"],
        )

        invalid_tables = [
            "user@table",
            "user#table",
            "user$table",
            "user.table",
            "user table",
        ]
        for table in invalid_tables:
            is_valid, _ = validator.validate_parameters(query_def, {"table": table})
            assert is_valid is False, f"Should fail for table: {table}"

    def test_empty_table_name(self):
        """Falla con nombre de tabla vacío"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="hsqldb",
            sql_template="SELECT * FROM data",
            required_params=["table"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"table": ""})
        assert is_valid is False

    def test_none_table_name(self):
        """Falla con nombre de tabla None"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="hsqldb",
            sql_template="SELECT * FROM data",
            required_params=["table"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"table": None})
        assert is_valid is False


class TestHSQLDBValidatorNoTable:
    """Pruebas sin parámetro table"""

    def test_no_table_required(self):
        """Pasa sin table cuando no es requerido"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="hsqldb",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        is_valid, _ = validator.validate_parameters(query_def, {})
        assert is_valid is True
