"""
Tests for Validators Factory - get_type_validator()
"""

import pytest

from util_bbdd.validators import (
    DatabaseTypeValidator,
    HSQLDBValidator,
    MariaDBValidator,
    OracleValidator,
    PostgreSQLValidator,
    SQLiteValidator,
    SQLServerValidator,
    get_type_validator,
)


class TestGetTypeValidatorFactory:
    """Pruebas para factory get_type_validator()"""

    def test_mariadb_validator(self):
        """Factory retorna MariaDBValidator para 'mariadb'"""
        validator = get_type_validator("mariadb")
        assert isinstance(validator, MariaDBValidator)
        assert validator.db_type == "mariadb"

    def test_oracle_validator(self):
        """Factory retorna OracleValidator para 'oracle'"""
        validator = get_type_validator("oracle")
        assert isinstance(validator, OracleValidator)
        assert validator.db_type == "oracle"

    def test_postgresql_validator(self):
        """Factory retorna PostgreSQLValidator para 'postgresql'"""
        validator = get_type_validator("postgresql")
        assert isinstance(validator, PostgreSQLValidator)
        assert validator.db_type == "postgresql"

    def test_hsqldb_validator(self):
        """Factory retorna HSQLDBValidator para 'hsqldb'"""
        validator = get_type_validator("hsqldb")
        assert isinstance(validator, HSQLDBValidator)
        assert validator.db_type == "hsqldb"

    def test_sqlserver_validator(self):
        """Factory retorna SQLServerValidator para 'sqlserver'"""
        validator = get_type_validator("sqlserver")
        assert isinstance(validator, SQLServerValidator)
        assert validator.db_type == "sqlserver"

    def test_sqlite_validator(self):
        """Factory retorna SQLiteValidator para 'sqlite'"""
        validator = get_type_validator("sqlite")
        assert isinstance(validator, SQLiteValidator)
        assert validator.db_type == "sqlite"

    def test_all_validators_inherit_from_base(self):
        """Todos los validadores heredan de DatabaseTypeValidator"""
        db_types = ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"]
        for db_type in db_types:
            validator = get_type_validator(db_type)
            assert isinstance(validator, DatabaseTypeValidator)

    def test_case_insensitive_mariadb(self):
        """Factory es case-insensitive para 'MARIADB'"""
        validator1 = get_type_validator("mariadb")
        validator2 = get_type_validator("MARIADB")
        assert validator1.__class__ is validator2.__class__
        assert validator1.db_type == validator2.db_type

    def test_case_insensitive_oracle(self):
        """Factory es case-insensitive para diferentes variaciones"""
        validators = [
            get_type_validator("Oracle"),
            get_type_validator("ORACLE"),
            get_type_validator("oracle"),
        ]
        for v in validators:
            assert isinstance(v, OracleValidator)

    def test_unsupported_database_type(self):
        """Falla con tipo de BD no soportado"""
        with pytest.raises(ValueError):
            get_type_validator("unsupported_db")

    def test_unsupported_empty_string(self):
        """Falla con string vacío"""
        with pytest.raises(ValueError):
            get_type_validator("")

    def test_error_message_lists_supported(self):
        """Mensaje de error lista tipos soportados"""
        with pytest.raises(ValueError) as exc_info:
            get_type_validator("unknown")
        error_msg = str(exc_info.value)
        # Should mention some supported types
        assert "mariadb" in error_msg.lower() or "Supported types" in error_msg

    def test_each_call_returns_new_instance(self):
        """Cada llamada retorna una nueva instancia"""
        validator1 = get_type_validator("mariadb")
        validator2 = get_type_validator("mariadb")
        assert validator1 is not validator2
        assert validator1.__class__ is validator2.__class__

    def test_validator_has_validate_parameters_method(self):
        """Cada validador tiene el método validate_parameters"""
        db_types = ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"]
        for db_type in db_types:
            validator = get_type_validator(db_type)
            assert hasattr(validator, "validate_parameters")
            assert callable(validator.validate_parameters)

    def test_all_types_documented_in_docstring(self):
        """Tipos soportados están documentados en docstring"""
        docstring = get_type_validator.__doc__
        assert docstring is not None
        assert "mariadb" in docstring.lower()
