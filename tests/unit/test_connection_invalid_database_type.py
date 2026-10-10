"""Tests de regresión para el tipo de excepción en db_type no soportado [CNX-03].

Antes de este fix, `connection/factory.py` y `connection/params.py` lanzaban
`ConnectionError`/`ValueError` genéricos para un db_type no soportado, en vez de
`InvalidDatabaseType` — incumpliendo la regla de `.github/SHARED_INSTRUCTIONS.md`
("Valida db_type al inicio; lanza InvalidDatabaseType antes de intentar conexión").
"""

from __future__ import annotations

import pytest

from util_bbdd.connection.factory import ConnectionFactory
from util_bbdd.connection.params import ConnectionParamsManager
from util_bbdd.exceptions import InvalidDatabaseType


def test_connection_factory_unsupported_db_type_raises_invalid_database_type() -> None:
    with pytest.raises(InvalidDatabaseType, match="no_existe"):
        ConnectionFactory.create_connection("no_existe", {})


def test_get_connection_config_unsupported_db_type_raises_invalid_database_type() -> None:
    with pytest.raises(InvalidDatabaseType, match="no_existe"):
        ConnectionParamsManager.get_connection_config("no_existe", {})


def test_get_pool_config_unsupported_db_type_raises_invalid_database_type() -> None:
    with pytest.raises(InvalidDatabaseType, match="no_existe"):
        ConnectionParamsManager.get_pool_config("no_existe", {})


def test_sanitize_for_connection_unsupported_db_type_raises_invalid_database_type() -> None:
    with pytest.raises(InvalidDatabaseType):
        ConnectionParamsManager.sanitize_for_connection("no_existe", {})


def test_sanitize_for_pool_unsupported_db_type_raises_invalid_database_type() -> None:
    with pytest.raises(InvalidDatabaseType):
        ConnectionParamsManager.sanitize_for_pool("no_existe", {})
