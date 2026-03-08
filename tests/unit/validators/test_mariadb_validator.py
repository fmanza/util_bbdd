"""
Tests for MariaDB Query Validator
"""

from util_bbdd.models import QueryDefinition
from util_bbdd.validators.mariadb_validator import MariaDBValidator


class TestMariaDBValidatorBasics:
    """Pruebas básicas del validador MariaDB"""

    def test_validator_init(self):
        """MariaDBValidator se inicia correctamente"""
        validator = MariaDBValidator()
        assert validator is not None
        assert validator.db_type == "mariadb"

    def test_validator_class_name(self):
        """MariaDBValidator tiene el nombre correcto"""
        validator = MariaDBValidator()
        assert validator.__class__.__name__ == "MariaDBValidator"


class TestMariaDBValidatorRequiredParams:
    """Pruebas de parámetros requeridos"""

    def test_missing_required_param(self):
        """Falla si falta parámetro requerido"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="insert_user",
            db_type="mariadb",
            sql_template="INSERT INTO users (name) VALUES ({name})",
            required_params=["name"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {})
        assert is_valid is False
        assert len(warnings) > 0

    def test_none_required_param(self):
        """Falla si parámetro requerido es None"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="insert_user",
            db_type="mariadb",
            sql_template="INSERT INTO users (name) VALUES ({name})",
            required_params=["name"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"name": None})
        assert is_valid is False

    def test_empty_string_required_param(self):
        """Falla si parámetro requerido es vacío"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="insert_user",
            db_type="mariadb",
            sql_template="INSERT INTO users (name) VALUES ({name})",
            required_params=["name"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"name": ""})
        assert is_valid is False

    def test_valid_required_param(self):
        """Pasa con parámetro requerido válido"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="insert_user",
            db_type="mariadb",
            sql_template="INSERT INTO users (name) VALUES ({name})",
            required_params=["name"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"name": "John"})
        assert is_valid is True


class TestMariaDBValidatorCharset:
    """Pruebas de validación de charset"""

    def test_valid_charset(self):
        """Acepta charset válido"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=["charset"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"charset": "utf8mb4"})
        assert is_valid is True

    def test_valid_charsets_variations(self):
        """Acepta diferentes charsets válidos"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=["charset"],
        )

        valid_charsets = ["utf8", "utf8mb4", "latin1", "ascii", "binary"]
        for charset in valid_charsets:
            is_valid, warnings = validator.validate_parameters(query_def, {"charset": charset})
            assert is_valid is True, f"Failed for charset: {charset}"


class TestMariaDBValidatorDatabaseName:
    """Pruebas de validación de nombre de BD"""

    def test_valid_database_name(self):
        """Acepta nombre de BD válido"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=["database"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"database": "my_database"})
        assert is_valid is True

    def test_empty_database_name(self):
        """Falla con nombre de BD vacío"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=["database"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"database": ""})
        assert is_valid is False


class TestMariaDBValidatorMultipleParams:
    """Pruebas con múltiples parámetros"""

    def test_multiple_required_params_all_valid(self):
        """Pasa con múltiples parámetros válidos"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="insert_user",
            db_type="mariadb",
            sql_template="INSERT INTO users (name, email) VALUES ({name}, {email})",
            required_params=["name", "database"],
        )

        params = {"name": "John", "database": "my_db"}
        is_valid, warnings = validator.validate_parameters(query_def, params)
        assert is_valid is True

    def test_multiple_required_params_one_missing(self):
        """Falla si falta uno de múltiples parámetros"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="insert_user",
            db_type="mariadb",
            sql_template="INSERT INTO users (name, email) VALUES ({name}, {email})",
            required_params=["name", "charset"],
        )

        params = {"name": "John"}
        is_valid, warnings = validator.validate_parameters(query_def, params)
        assert is_valid is False


class TestMariaDBValidatorNoRequiredParams:
    """Pruebas sin parámetros requeridos"""

    def test_query_no_required_params(self):
        """Pasa query sin parámetros requeridos"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="select_all",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {})
        assert is_valid is True

    def test_query_no_required_params_extra_params(self):
        """Acepta parámetros extra incluso si no son requeridos"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="select_all",
            db_type="mariadb",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        params = {"extra": "param", "another": "value"}
        is_valid, warnings = validator.validate_parameters(query_def, params)
        assert is_valid is True
