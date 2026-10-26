"""Extras de drivers sin instalación propia hasta 4.0.x: SQL Server, HSQLDB y SQLite async (util_bbdd_web G3, 4.1.0).

Cada motor se instala con un extra (``pip install "util_bbdd[sqlserver]"``) y el ``install_command`` del catálogo lo
dice, igual que ``postgresql`` (``test_postgresql_driver_declaration.py``).
"""

from __future__ import annotations

import tomllib

from pathlib import Path
from typing import Any

import pytest

from util_bbdd._drivers import get_database_validator

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]

EXPECTED: dict[str, set[str]] = {
    "sqlserver": {"pymssql"},
    "sqlserver-odbc": {"pyodbc", "aioodbc"},
    "hsqldb": {"jaydebeapi"},
    "sqlite-async": {"aiosqlite"},
}


def _extras() -> dict[str, list[str]]:
    data: dict[str, Any] = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras: dict[str, list[str]] = data["project"]["optional-dependencies"]
    return extras


@pytest.mark.parametrize(("extra", "packages"), sorted(EXPECTED.items()))
def test_extra_declares_the_engine_drivers(extra: str, packages: set[str]) -> None:
    names = {requirement.split(">")[0].split("[")[0].strip().lower() for requirement in _extras()[extra]}
    assert names == packages


@pytest.mark.parametrize(
    ("db_type", "driver", "extra"),
    [("sqlserver", "pymssql", "sqlserver"), ("sqlserver", "pyodbc", "sqlserver-odbc"), ("hsqldb", None, "hsqldb")],
)
def test_install_command_names_the_extra(db_type: str, driver: str | None, extra: str) -> None:
    driver_info = get_database_validator().get_db_type_info(db_type)["driver_info"]
    options = driver_info if isinstance(driver_info, list) else [driver_info]
    info = next(option for option in options if driver is None or option["name"] == driver)
    assert f"util_bbdd[{extra}]" in info["install_command"]
