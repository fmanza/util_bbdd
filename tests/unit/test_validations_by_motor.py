"""Validaciones por motor con placeholders reales (las consultas de catálogo que tenía sql_queries.json hasta E2c,
conservadas como fichero de consultas de usuario en ``tests/fixtures/sql_queries_sample.json``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from util_bbdd.models import QueryDefinition
from util_bbdd.query import QueryRegistry
from util_bbdd.validators import get_type_validator

SAMPLE_QUERIES = Path(__file__).resolve().parents[1] / "fixtures" / "sql_queries_sample.json"


@pytest.mark.parametrize(
    ("db_type", "query_name", "params"),
    [
        ("mariadb", "obtener_tablas", {"database": "mydb"}),
        ("oracle", "create_table", {"tabla": "USERS", "esquema": "HR"}),
        ("postgresql", "create_view", {"esquema": "public", "tabla": "vw_users"}),
        ("hsqldb", "columnas_tabla", {"database": "PUBLIC", "tabla": "USERS"}),
        ("sqlserver", "create_rutina", {"esquema": "dbo", "rutina": "sp_test"}),
        ("sqlite", "create_table", {"tabla": "users"}),
    ],
)
def test_validator_accepts_real_placeholder_params(db_type: str, query_name: str, params: dict[str, str]) -> None:
    registry = QueryRegistry(SAMPLE_QUERIES)
    query_def = registry.get_query_definition(db_type, query_name)
    validator = get_type_validator(db_type)

    is_valid, warnings = validator.validate_parameters(query_def, params)

    assert is_valid is True
    assert isinstance(warnings, list)


@pytest.mark.parametrize(
    ("db_type", "query_name", "valid_params"),
    [
        ("mariadb", "obtener_tablas", {"database": "mydb"}),
        ("oracle", "create_table", {"tabla": "USERS", "esquema": "HR"}),
        ("postgresql", "create_view", {"esquema": "public", "tabla": "vw_users"}),
        ("hsqldb", "columnas_tabla", {"database": "PUBLIC", "tabla": "USERS"}),
        ("sqlserver", "create_rutina", {"esquema": "dbo", "rutina": "sp_test"}),
        ("sqlite", "create_table", {"tabla": "users"}),
    ],
)
def test_validator_rejects_missing_required_params(db_type: str, query_name: str, valid_params: dict[str, str]) -> None:
    registry = QueryRegistry(SAMPLE_QUERIES)
    query_def = registry.get_query_definition(db_type, query_name)
    validator = get_type_validator(db_type)

    missing_param = query_def.required_params[0]
    params = dict(valid_params)
    params.pop(missing_param, None)

    is_valid, warnings = validator.validate_parameters(query_def, params)

    assert is_valid is False
    assert any("Missing required parameter" in warning for warning in warnings)


def test_oracle_validator_validates_esquema_format() -> None:
    validator = get_type_validator("oracle")
    query_def = QueryDefinition(
        name="oracle_q",
        db_type="oracle",
        sql_template="SELECT * FROM dual",
        required_params=["esquema"],
    )

    is_valid, warnings = validator.validate_parameters(query_def, {"esquema": "BAD-NAME"})

    assert is_valid is False
    assert any("invalid characters" in warning.lower() for warning in warnings)


def test_hsqldb_validator_validates_tabla_alias() -> None:
    validator = get_type_validator("hsqldb")
    query_def = QueryDefinition(
        name="hsqldb_q",
        db_type="hsqldb",
        sql_template="SELECT 1",
        required_params=["tabla"],
    )

    is_valid, warnings = validator.validate_parameters(query_def, {"tabla": "bad.name"})

    assert is_valid is False
    assert any("table name contains invalid characters" in warning.lower() for warning in warnings)


def test_sqlserver_validator_accepts_schema_alias() -> None:
    validator = get_type_validator("sqlserver")
    query_def = QueryDefinition(
        name="sqlserver_q",
        db_type="sqlserver",
        sql_template="SELECT 1",
        required_params=["schema"],
    )

    is_valid, warnings = validator.validate_parameters(query_def, {"schema": "dbo"})

    assert is_valid is True
    assert warnings == []


def test_postgresql_columns_charset_collation_requires_database_and_tabla() -> None:
    registry = QueryRegistry(SAMPLE_QUERIES)
    query_def = registry.get_query_definition("postgresql", "columns_charset_collation")

    assert {"database", "tabla"}.issubset(set(query_def.required_params))
