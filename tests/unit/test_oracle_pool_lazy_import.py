"""Tests de regresión para el import lazy de oracledb en PoolConnection [CNX-05].

Antes de este fix, connection/oracle/pool_connection_oracle.py hacía
`import oracledb` a nivel de módulo (eager), rompiendo el patrón de import
opcional lazy que ya seguían mariadb/postgresql (y el resto de ficheros de
conexión Oracle: connection_oracle.py, async_connection_oracle.py,
async_pool_connection_oracle.py) — importar el paquete util_bbdd.connection.oracle
fallaba si oracledb no estaba instalado, incluso sin usar pooling.
"""

from __future__ import annotations

import importlib
import sys
import types

import pytest


def _reload_module_with_fake_oracledb(monkeypatch: pytest.MonkeyPatch, fake_oracledb: object) -> types.ModuleType:
    sys.modules.pop("util_bbdd.connection.oracle.pool_connection_oracle", None)
    if fake_oracledb is None:
        monkeypatch.setitem(sys.modules, "oracledb", None)
    else:
        monkeypatch.setitem(sys.modules, "oracledb", fake_oracledb)
    return importlib.import_module("util_bbdd.connection.oracle.pool_connection_oracle")


def test_module_import_succeeds_when_oracledb_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """El módulo se importa sin fallar aunque oracledb no esté instalado (lazy)."""
    module = _reload_module_with_fake_oracledb(monkeypatch, None)
    assert module.HAS_ORACLEDB is False


# Sin la salida temprana de __del__, el objeto a medio construir emitía PytestUnraisableExceptionWarning
# (AttributeError en el destructor): el aviso pasa a ser un fallo del test.
@pytest.mark.filterwarnings("error::pytest.PytestUnraisableExceptionWarning")
def test_pool_connection_raises_clear_import_error_when_oracledb_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _reload_module_with_fake_oracledb(monkeypatch, None)

    with pytest.raises(ImportError, match="oracledb"):
        module.PoolConnection({"user": "scott", "password": "tiger", "database": "orcl"})


def test_has_oracledb_true_when_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_oracledb = types.SimpleNamespace(ConnectionPool=object)
    module = _reload_module_with_fake_oracledb(monkeypatch, fake_oracledb)
    assert module.HAS_ORACLEDB is True
