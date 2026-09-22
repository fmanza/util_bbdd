"""Tests de regresión para DriverValidator [FND-02].

Verifica que `check_driver_availability` lanza `InvalidDatabaseType` (no
`ValueError`/`DriverError` genérico) para un `db_type` desconocido, unificando
el criterio con `DatabaseTypeValidator.validate_db_type`.
"""

import pytest

from util_bbdd._core.exceptions import InvalidDatabaseType
from util_bbdd._drivers.driver_validator import DriverValidator


def test_check_driver_availability_unknown_db_type_raises_invalid_database_type() -> None:
    with pytest.raises(InvalidDatabaseType) as exc_info:
        DriverValidator.check_driver_availability("db_inexistente", {})

    assert exc_info.value.db_type == "db_inexistente"


def test_check_driver_availability_unknown_db_type_message_contains_db_type() -> None:
    with pytest.raises(InvalidDatabaseType, match="db_inexistente"):
        DriverValidator.check_driver_availability("db_inexistente", {})
