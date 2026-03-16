"""Tests for advanced database-specific validators (PR 4)

Advanced validation rules for each database motor, including:
- Schema/database context handling per motor
- Table name validation (especially HSQLDB)
- Parameter mapping and normalization
"""

import pytest

from util_bbdd.models import QueryDefinition
from util_bbdd.validators import (
    HSQLDBValidator,
    MariaDBValidator,
    OracleValidator,
    PostgreSQLValidator,
    SQLiteValidator,
    SQLServerValidator,
    get_type_validator,
)


class TestMariaDBAdvancedValidator:
    """Advanced validation rules for MariaDB"""

    def test_mariadb_requires_database_for_introspection(self):
        """MariaDB introspection queries require 'database' parameter"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="obtener_tablas",
            db_type="mariadb",
            sql_template="SELECT * FROM information_schema.tables WHERE table_schema = '{database}'",
            required_params=["database"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {"database": "my_db"})
        assert is_valid is True
        assert len(warnings) == 0

    def test_mariadb_fails_without_database_param(self):
        """MariaDB fails validation when 'database' param is missing"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="obtener_tablas",
            db_type="mariadb",
            sql_template="SELECT * FROM information_schema.tables WHERE table_schema = '{database}'",
            required_params=["database"],
        )

        is_valid, warnings = validator.validate_parameters(query_def, {})
        assert is_valid is False
        assert any("database" in w.lower() for w in warnings)

    def test_mariadb_allows_charset_param(self):
        """MariaDB allows optional 'charset' parameter"""
        validator = MariaDBValidator()
        query_def = QueryDefinition(
            name="custom_query",
            db_type="mariadb",
            sql_template="SELECT * FROM {table}",
            required_params=["table"],
            optional_params=["charset"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"table": "users", "charset": "utf8mb4"})
        assert is_valid is True


class TestOracleAdvancedValidator:
    """Advanced validation rules for Oracle - distinct schema vs database"""

    def test_oracle_requires_schema_param(self):
        """Oracle uses 'schema' parameter (not 'database')"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="obtener_tablas",
            db_type="oracle",
            sql_template="SELECT * FROM all_tables WHERE owner = '{schema}'",
            required_params=["schema"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"schema": "HR"})
        assert is_valid is True

    def test_oracle_fails_without_schema_param(self):
        """Oracle fails if required 'schema' parameter is missing"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="obtener_tablas",
            db_type="oracle",
            sql_template="SELECT * FROM all_tables WHERE owner = '{schema}'",
            required_params=["schema"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {})
        assert is_valid is False

    def test_oracle_schema_name_max_length(self):
        """Oracle schema names cannot exceed 30 characters"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="test",
            db_type="oracle",
            sql_template="SELECT * FROM all_tables WHERE owner = '{schema}'",
            required_params=["schema"],
        )

        # Valid: exactly 30 chars
        is_valid, _ = validator.validate_parameters(query_def, {"schema": "A" * 30})
        assert is_valid is True

        # Invalid: 31 chars
        is_valid, _ = validator.validate_parameters(query_def, {"schema": "A" * 31})
        assert is_valid is False
        assert any("30" in w for w in _)

    def test_oracle_schema_name_allowed_characters(self):
        """Oracle schema names allow alphanumeric, underscore, $, #"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="test",
            db_type="oracle",
            sql_template="SELECT * FROM all_tables",
            required_params=["schema"],
        )

        valid_schemas = ["HR", "USER_123", "USER$NAME", "USER#NAME", "HR_2024"]
        for schema in valid_schemas:
            is_valid, _ = validator.validate_parameters(query_def, {"schema": schema})
            assert is_valid is True, f"Schema '{schema}' should be valid"

    def test_oracle_schema_name_rejects_invalid_chars(self):
        """Oracle schema names reject invalid characters"""
        validator = OracleValidator()
        query_def = QueryDefinition(
            name="test",
            db_type="oracle",
            sql_template="SELECT * FROM all_tables",
            required_params=["schema"],
        )

        invalid_schemas = ["USER-NAME", "USER.NAME", "USER NAME", "USER@NAME"]
        for schema in invalid_schemas:
            is_valid, _ = validator.validate_parameters(query_def, {"schema": schema})
            assert is_valid is False, f"Schema '{schema}' should be invalid"


class TestPostgreSQLAdvancedValidator:
    """Advanced validation rules for PostgreSQL"""

    def test_postgresql_requires_database_param(self):
        """PostgreSQL uses 'database' in terminology"""
        validator = PostgreSQLValidator()
        query_def = QueryDefinition(
            name="obtener_tablas",
            db_type="postgresql",
            sql_template="SELECT * FROM information_schema.tables WHERE table_schema = '{database}'",
            required_params=["database"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"database": "public"})
        assert is_valid is True


class TestHSQLDBAdvancedValidator:
    """Advanced validation rules for HSQLDB - strict table naming"""

    def test_hsqldb_table_name_validation_alphanum_underscore_hyphen(self):
        """HSQLDB accepts alphanumeric + hyphen + underscore in table names"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="obtener_tablas",
            db_type="hsqldb",
            sql_template="SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '{table}'",
            required_params=["table"],
        )

        valid_names = ["users", "user_profiles", "user-profiles", "USER_123", "table1"]
        for name in valid_names:
            is_valid, _ = validator.validate_parameters(query_def, {"table": name})
            assert is_valid is True, f"Table name '{name}' should be valid for HSQLDB"

    def test_hsqldb_table_name_rejects_special_chars(self):
        """HSQLDB rejects table names with special characters"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="obtener_tablas",
            db_type="hsqldb",
            sql_template="SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '{table}'",
            required_params=["table"],
        )

        invalid_names = ["user@profile", "user.table", "user profile", "user;drop", "user$profile"]
        for name in invalid_names:
            is_valid, _ = validator.validate_parameters(query_def, {"table": name})
            assert is_valid is False, f"Table name '{name}' should be invalid for HSQLDB"
            assert any("table" in w.lower() for w in _)

    def test_hsqldb_works_without_table_param(self):
        """HSQLDB can handle queries without table parameter"""
        validator = HSQLDBValidator()
        query_def = QueryDefinition(
            name="obtener_tablas",
            db_type="hsqldb",
            sql_template="SELECT * FROM INFORMATION_SCHEMA.TABLES",
            required_params=[],
        )

        is_valid, _ = validator.validate_parameters(query_def, {})
        assert is_valid is True


class TestSQLServerAdvancedValidator:
    """Advanced validation rules for SQL Server"""

    def test_sqlserver_supports_schema_context(self):
        """SQL Server supports schema parameter"""
        validator = SQLServerValidator()
        query_def = QueryDefinition(
            name="obtener_tablas",
            db_type="sqlserver",
            sql_template="SELECT * FROM INFORMATION_SCHEMA.TABLES",
            required_params=[],
        )

        is_valid, _ = validator.validate_parameters(query_def, {})
        assert is_valid is True

    def test_sqlserver_validates_schema_if_provided(self):
        """SQL Server validates schema if provided"""
        validator = SQLServerValidator()
        query_def = QueryDefinition(
            name="custom_query",
            db_type="sqlserver",
            sql_template="SELECT * FROM {schema}.{table}",
            required_params=["schema", "table"],
        )

        is_valid, _ = validator.validate_parameters(query_def, {"schema": "dbo", "table": "users"})
        assert is_valid is True


class TestSQLiteAdvancedValidator:
    """Advanced validation rules for SQLite - file-based database"""

    def test_sqlite_requires_minimal_params(self):
        """SQLite requires minimal parameters (no schema/database)"""
        validator = SQLiteValidator()
        query_def = QueryDefinition(
            name="obtener_tablas",
            db_type="sqlite",
            sql_template="SELECT name FROM sqlite_master WHERE type='table'",
            required_params=[],
        )

        is_valid, _ = validator.validate_parameters(query_def, {})
        assert is_valid is True


class TestValidatorFactoryPattern:
    """Test the validator factory pattern"""

    def test_get_type_validator_returns_correct_validator(self):
        """get_type_validator returns correct validator for each db_type"""
        validators = {
            "mariadb": MariaDBValidator,
            "oracle": OracleValidator,
            "postgresql": PostgreSQLValidator,
            "hsqldb": HSQLDBValidator,
            "sqlserver": SQLServerValidator,
            "sqlite": SQLiteValidator,
        }

        for db_type, expected_class in validators.items():
            validator = get_type_validator(db_type)
            assert isinstance(validator, expected_class)

    def test_get_type_validator_raises_for_unknown_db_type(self):
        """get_type_validator raises ValueError for unsupported db_type"""
        with pytest.raises(ValueError):
            get_type_validator("unsupported_db")


class TestValidatorConsistency:
    """Tests for consistency across all validators"""

    def test_validate_parameters_returns_tuple(self):
        """All validators return (bool, list) from validate_parameters"""
        validators = [
            MariaDBValidator(),
            OracleValidator(),
            PostgreSQLValidator(),
            HSQLDBValidator(),
            SQLServerValidator(),
            SQLiteValidator(),
        ]

        query_def = QueryDefinition(
            name="test",
            db_type="mariadb",
            sql_template="SELECT 1",
            required_params=[],
        )

        for validator in validators:
            result = validator.validate_parameters(query_def, {})
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], bool)
            assert isinstance(result[1], list)

    def test_missing_required_param_detected_by_all_validators(self):
        """All validators detect missing required parameters"""
        validators_and_types = [
            ("mariadb", MariaDBValidator()),
            ("oracle", OracleValidator()),
            ("postgresql", PostgreSQLValidator()),
            ("hsqldb", HSQLDBValidator()),
            ("sqlserver", SQLServerValidator()),
            ("sqlite", SQLiteValidator()),
        ]

        for db_type, validator in validators_and_types:
            query_def = QueryDefinition(
                name="test_query",
                db_type=db_type,
                sql_template="SELECT * FROM {required_param}",
                required_params=["required_param"],
            )

            is_valid, _ = validator.validate_parameters(query_def, {})
            assert is_valid is False, f"{db_type} should detect missing required param"


class TestValidatorConsumesDatabaseTypes:
    """Tests that validators can consult database_types.json for rules"""

    def test_all_validators_have_db_type_attribute(self):
        """Each validator has db_type class attribute"""
        validators = [
            (MariaDBValidator(), "mariadb"),
            (OracleValidator(), "oracle"),
            (PostgreSQLValidator(), "postgresql"),
            (HSQLDBValidator(), "hsqldb"),
            (SQLServerValidator(), "sqlserver"),
            (SQLiteValidator(), "sqlite"),
        ]

        for validator, expected_db_type in validators:
            assert hasattr(validator, "db_type")
            assert validator.db_type == expected_db_type
