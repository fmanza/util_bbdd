"""Tests de regresión SVC-02 (AUDIT_CODE 2026-09-22).

`QueryResolver._interpolate_sql()` interpola los parámetros directamente en el SQL final vía
`str.format()`, sin bind params. La única defensa es la validación por motor. Antes de este fix,
5 de los 6 validadores no aplicaban ninguna allowlist de caracteres a `tabla`/`rutina`/
`tipo_rutina`/`tablespace`, permitiendo payloads como `'; DROP TABLE x; --` o `' OR '1'='1`.
"""

from __future__ import annotations

import pytest

from util_bbdd.models import QueryDefinition
from util_bbdd.validators import get_type_validator

DB_TYPES = ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"]

INJECTION_PAYLOADS = [
    "'; DROP TABLE x; --",
    "' OR '1'='1",
    "x`; DROP TABLE y; --",
    "x\\'; DROP TABLE y; --",
    "x UNION SELECT password FROM users",
    "x/*comment*/y",
]


def _query_def(param_name: str) -> QueryDefinition:
    return QueryDefinition(
        name="test_query",
        db_type="generic",
        sql_template=f"SELECT * FROM {{{param_name}}}",
        required_params=[],
    )


@pytest.mark.parametrize("db_type", DB_TYPES)
@pytest.mark.parametrize("param_name", ["tabla", "table", "rutina", "tipo_rutina", "tablespace"])
@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_validators_reject_injection_payloads_in_identifier_params(db_type: str, param_name: str, payload: str) -> None:
    validator = get_type_validator(db_type)
    query_def = _query_def(param_name)

    is_valid, errors = validator.validate_parameters(query_def, {param_name: payload})

    assert is_valid is False, f"{db_type}.{param_name} aceptó el payload {payload!r} sin rechazarlo"
    assert errors


@pytest.mark.parametrize("db_type", ["mariadb", "postgresql"])
@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_mariadb_and_postgresql_reject_injection_payloads_in_database_param(db_type: str, payload: str) -> None:
    """mariadb y postgresql solo comprobaban que 'database' no estuviera vacío."""
    validator = get_type_validator(db_type)
    query_def = _query_def("database")

    is_valid, errors = validator.validate_parameters(query_def, {"database": payload})

    assert is_valid is False, f"{db_type}.database aceptó el payload {payload!r} sin rechazarlo"
    assert errors


@pytest.mark.parametrize("db_type", DB_TYPES)
@pytest.mark.parametrize("param_name", ["tabla", "rutina", "tipo_rutina", "tablespace"])
def test_validators_accept_legitimate_identifiers(db_type: str, param_name: str) -> None:
    """La allowlist no debe rechazar identificadores SQL normales."""
    validator = get_type_validator(db_type)
    query_def = _query_def(param_name)

    is_valid, _ = validator.validate_parameters(query_def, {param_name: "CORE_USUARIOS_2024"})

    assert is_valid is True
