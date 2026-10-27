"""U-T1 (G5 y G10 de util_bbdd_web): ``get_engine_capabilities`` y ``get_driver_status``.

La matriz de ``core/capabilities.py`` es declarativa (``core`` no importa las operaciones): estos tests la contrastan
con la fuente de cada capacidad para que no se desfase.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from util_bbdd import SyncDatabaseManager
from util_bbdd.connection import (
    DriverStatus,
    EngineCapabilities,
    EngineReadinessAdvisor,
    get_driver_status,
    get_engine_capabilities,
)
from util_bbdd.core.capabilities import DB_ASYNC_CAPABILITIES, ENGINE_CAPABILITIES
from util_bbdd.dump import _constraints
from util_bbdd.exceptions import ConnectionError as UtilConnectionError, InvalidDatabaseType
from util_bbdd.factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory
from util_bbdd.metadata.catalog_registry import supported_catalog_engines
from util_bbdd.migrate import MigrationPlanner

pytestmark = pytest.mark.unit

ENGINES = SyncDatabaseManager.get_supported_db_types()
#: db_type de la librería → nombre de dialecto de SQLAlchemy.
DIALECT = {"sqlserver": "mssql"}


def _has_sqlalchemy_dialect(db_type: str) -> bool:
    try:
        SQLAlchemyEngineFactory._build_connection_string(db_type, {"database": "x"}, "x", "pymssql")  # noqa: SLF001
    except UtilConnectionError:
        return False
    except Exception:  # noqa: BLE001 - faltan parámetros, pero hay dialecto
        return True
    return True


def test_every_supported_engine_has_capabilities() -> None:
    assert list(ENGINE_CAPABILITIES) == ENGINES
    for db_type in ENGINES:
        caps = get_engine_capabilities(db_type)
        assert isinstance(caps, EngineCapabilities) and caps.db_type == db_type


def test_lookup_is_case_insensitive_and_unknown_is_none() -> None:
    assert get_engine_capabilities(" SQLServer ") is ENGINE_CAPABILITIES["sqlserver"]
    assert get_engine_capabilities("db2") is None


@pytest.mark.parametrize("db_type", ENGINES)
def test_matrix_matches_each_source(db_type: str) -> None:
    caps = ENGINE_CAPABILITIES[db_type]
    sqlalchemy = _has_sqlalchemy_dialect(db_type)

    assert caps.async_supported is DB_ASYNC_CAPABILITIES[db_type]
    assert caps.migrate_source is (db_type in MigrationPlanner.supported_sources())
    assert caps.migrate_target is (db_type in MigrationPlanner.supported_targets())
    assert caps.readiness is EngineReadinessAdvisor().assess(db_type, {}).supported
    assert caps.documentation is caps.graphs is (db_type in supported_catalog_engines())
    assert caps.compare is caps.dump is caps.bulk is sqlalchemy
    assert caps.dump_constraints is (DIALECT.get(db_type, db_type) in _constraints._SUPPORTED_DIALECTS)  # noqa: SLF001


class TestDriverStatus:
    @pytest.mark.parametrize("db_type", ENGINES)
    def test_one_status_per_declared_driver(self, db_type: str) -> None:
        declared = SyncDatabaseManager.get_db_type_info_static(db_type)["drivers"]
        statuses = get_driver_status(db_type)
        assert [s.name for s in statuses] == declared
        assert all(isinstance(s, DriverStatus) and isinstance(s.installed, bool) for s in statuses)

    def test_builtin_driver_is_installed(self) -> None:
        assert get_driver_status("sqlite") == (DriverStatus("sqlite3", True),)

    def test_missing_driver_is_reported_without_importing_it(self) -> None:
        with patch("util_bbdd._drivers.driver_status.importlib.util.find_spec", return_value=None) as find_spec:
            statuses = get_driver_status("postgresql")
        assert [s.installed for s in statuses] == [False, False]
        assert [c.args[0] for c in find_spec.call_args_list] == ["psycopg", "asyncpg"]

    def test_broken_spec_counts_as_missing(self) -> None:
        with patch("util_bbdd._drivers.driver_status.importlib.util.find_spec", side_effect=ValueError("roto")):
            assert {s.installed for s in get_driver_status("mysql")} == {False}

    def test_unknown_engine_raises(self) -> None:
        with pytest.raises(InvalidDatabaseType):
            get_driver_status("db2")
