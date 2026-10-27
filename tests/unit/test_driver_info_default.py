"""U-T2 (G8 y G14 de util_bbdd_web): sin ``cx_Oracle`` y ``default_driver`` homogéneo, sin romper ``driver_info``."""

from __future__ import annotations

import json

from pathlib import Path

import pytest

from util_bbdd import SyncDatabaseManager
from util_bbdd._drivers._config_loader import default_driver
from util_bbdd._drivers.validator import get_database_validator

pytestmark = pytest.mark.unit

ENGINES = SyncDatabaseManager.get_supported_db_types()
RAW = json.loads((Path(__file__).parents[2] / "src/util_bbdd/data/database_types.json").read_text(encoding="utf-8"))
DRIVER_KEYS = {"name", "pip_package", "import_name", "install_command", "system_requirements"}


@pytest.mark.parametrize("db_type", ENGINES)
def test_every_engine_has_a_default_driver_with_the_same_shape(db_type: str) -> None:
    info = SyncDatabaseManager.get_db_type_info_static(db_type)
    driver = info["default_driver"]

    assert DRIVER_KEYS <= set(driver)
    assert "default" not in driver
    assert driver["import_name"] in info["drivers"]
    assert get_database_validator().get_db_type_driver_info(db_type)["import_name"] == driver["import_name"]


def test_driver_info_keeps_its_shape() -> None:
    sqlserver = SyncDatabaseManager.get_db_type_info_static("sqlserver")
    assert [option["name"] for option in sqlserver["driver_info"]] == ["pymssql", "pyodbc"]  # lista conservada
    assert sqlserver["default_driver"]["name"] == "pymssql"
    for db_type in ENGINES:
        assert type(SyncDatabaseManager.get_db_type_info_static(db_type)["driver_info"]) is type(
            RAW["database_types"][db_type]["driver_info"]
        )


def test_sqlserver_driver_info_is_no_longer_empty() -> None:
    """Hasta v4.5.x, ``get_db_type_driver_info("sqlserver")`` coercía la lista a ``{}``."""
    assert get_database_validator().get_db_type_driver_info("sqlserver")["pip_package"] == "pymssql"


def test_obsolete_cx_oracle_is_gone() -> None:
    assert SyncDatabaseManager.get_db_type_info_static("oracle")["drivers"] == ["oracledb"]
    assert "cx_Oracle" not in json.dumps(RAW["database_types"])


def test_default_driver_rules() -> None:
    options = [{"name": "a", "import_name": "a"}, {"name": "b", "import_name": "b", "default": True}]
    assert default_driver(options) == {"name": "b", "import_name": "b"}
    assert default_driver(options[:1]) == {"name": "a", "import_name": "a"}  # sin marca: la primera
    assert default_driver({"import_name": "x", "pip_package": "x"}) == {
        "import_name": "x",
        "pip_package": "x",
        "name": "x",
    }
    assert default_driver([]) == {} and default_driver(None) == {}
