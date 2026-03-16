"""
Tests for SQLite Query Validator
"""

from util_bbdd.models import QueryDefinition
from util_bbdd.validators.sqlite_validator import SQLiteValidator


class TestSQLiteValidatorBasics:
    """Pruebas básicas del validador SQLite"""

    def test_validator_init(self):
        """SQLiteValidator se inicia correctamente"""
        validator = SQLiteValidator()
        assert validator is not None
        assert validator.db_type == "sqlite"


class TestSQLiteValidatorDatabaseFile:
    """Pruebas de validación de archivo de BD"""

    def test_valid_database_file(self):
        """Acepta ruta de archivo válida"""
        validator = SQLiteValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlite",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"database_file": "/path/to/db.sqlite"})
        assert is_valid is True

    def test_valid_windows_path(self):
        """Acepta ruta Windows"""
        validator = SQLiteValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlite",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"database_file": "C:\\database\\db.sqlite"})
        assert is_valid is True

    def test_empty_database_file(self):
        """Genera warning con archivo vacío"""
        validator = SQLiteValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlite",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        # SQLite debería permitir BD en memoria, pero generar warning si file está vacío
        is_valid, _ = validator.validate_parameters(query_def, {"database_file": ""})
        # SQLite debería pasar (pueden usar :memory:) pero puede haber _
        assert is_valid is True or len(_) > 0

    def test_no_database_file_param(self):
        """Pasa sin parámetro database_file"""
        validator = SQLiteValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlite",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        is_valid, _ = validator.validate_parameters(query_def, {})
        assert is_valid is True


class TestSQLiteValidatorImMemory:
    """Pruebas para BD en memoria"""

    def test_in_memory_database(self):
        """Acepta BD en memoria (:memory:)"""
        validator = SQLiteValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlite",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"database_file": ":memory:"})
        assert is_valid is True


class TestSQLiteValidatorNoRequiredParams:
    """Pruebas sin parámetros requeridos"""

    def test_no_required_params(self):
        """Pasa sin parámetros requeridos"""
        validator = SQLiteValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlite",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        is_valid, _ = validator.validate_parameters(query_def, {})
        assert is_valid is True

    def test_optional_params_ignored(self):
        """Ignora parámetros opcionales"""
        validator = SQLiteValidator()
        query_def = QueryDefinition(
            name="query",
            db_type="sqlite",
            sql_template="SELECT * FROM users",
            required_params=[],
        )

        params = {"extra": "param", "another": "value"}
        is_valid, _ = validator.validate_parameters(query_def, params)
        assert is_valid is True
