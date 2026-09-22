"""Tests de regresión: el bootstrap de adapters no enmascara errores reales [MDC-04].

Antes de este fix, `_register_*_adapters()` en mariadb/postgresql/oracle capturaba
`Exception` (no solo `ImportError`) al registrar en el AdapterRegistry global,
enmascarando cualquier error real de bootstrap -- incluido el `ValueError` que el
registry lanza a propósito ante un doble registro. Solo mysql/sqlite/sqlserver ya
capturaban `ImportError` específicamente.

Cada módulo ya ejecutó su `_register_*_adapters()` una vez al importarse (al
cargar la suite de tests); llamarla de nuevo aquí fuerza el camino de "ya
registrado" contra el registry global real, sin necesidad de mockear nada.
"""

from __future__ import annotations

import pytest


def test_mariadb_double_registration_raises_value_error() -> None:
    from util_bbdd.metadata.mariadb import _register_mariadb_adapters

    with pytest.raises(ValueError, match="ya registrado"):
        _register_mariadb_adapters()


def test_postgresql_double_registration_raises_value_error() -> None:
    from util_bbdd.metadata.postgresql import _register_postgresql_adapters

    with pytest.raises(ValueError, match="ya registrado"):
        _register_postgresql_adapters()


def test_oracle_double_registration_raises_value_error() -> None:
    from util_bbdd.metadata.oracle import _register_oracle_adapters

    with pytest.raises(ValueError, match="ya registrado"):
        _register_oracle_adapters()
