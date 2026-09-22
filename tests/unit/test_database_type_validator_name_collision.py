"""Tests de regresión para la colisión de nombre DatabaseTypeValidator [SVC-05].

Antes de este fix existían dos clases distintas llamadas DatabaseTypeValidator:
`_drivers.validator.DatabaseTypeValidator` (valida si un db_type está soportado,
lee database_types.json) y `validators.base_validator.DatabaseTypeValidator`
(ABC para validadores de parámetros de query por motor) — superficie de import
confusa. La segunda se renombró a QueryParameterValidator.
"""

from __future__ import annotations

from util_bbdd._drivers.validator import DatabaseTypeValidator as DriverDatabaseTypeValidator
from util_bbdd.validators import QueryParameterValidator
from util_bbdd.validators.base_validator import QueryParameterValidator as BaseQueryParameterValidator


def test_driver_database_type_validator_and_query_parameter_validator_are_unrelated() -> None:
    assert DriverDatabaseTypeValidator is not QueryParameterValidator
    assert not issubclass(DriverDatabaseTypeValidator, QueryParameterValidator)
    assert not issubclass(QueryParameterValidator, DriverDatabaseTypeValidator)


def test_query_parameter_validator_exported_consistently() -> None:
    assert QueryParameterValidator is BaseQueryParameterValidator


def test_validators_package_no_longer_exports_database_type_validator_name() -> None:
    import util_bbdd.validators as validators_pkg

    assert "DatabaseTypeValidator" not in validators_pkg.__all__
    assert "QueryParameterValidator" in validators_pkg.__all__


def test_engine_validators_still_subclass_query_parameter_validator() -> None:
    from util_bbdd.validators import (
        HSQLDBValidator,
        MariaDBValidator,
        OracleValidator,
        PostgreSQLValidator,
        SQLiteValidator,
        SQLServerValidator,
    )

    for cls in (
        MariaDBValidator,
        OracleValidator,
        PostgreSQLValidator,
        HSQLDBValidator,
        SQLServerValidator,
        SQLiteValidator,
    ):
        assert issubclass(cls, QueryParameterValidator)
