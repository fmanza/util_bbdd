"""P1 de drivers-connections-audit (FASE 1, 2026-10-08): driver de PostgreSQL declarado frente al usado.

La librería conecta con psycopg 3 (+ psycopg_pool) en sync y asyncpg en async, pero ``database_types.json`` declaraba
``psycopg2`` / ``psycopg2-binary`` y ``pyproject.toml`` no tenía extra para PostgreSQL: instalar lo declarado dejaba
``DriverError: psycopg no disponible``.
"""

from __future__ import annotations

import tomllib

from pathlib import Path

from util_bbdd._drivers import get_database_validator

ROOT = Path(__file__).resolve().parents[2]


def test_database_types_declares_the_drivers_actually_used() -> None:
    info = get_database_validator().get_db_type_info("postgresql")

    assert info["drivers"] == ["psycopg", "asyncpg"]
    assert info["driver_info"]["import_name"] == "psycopg"
    assert "psycopg2" not in info["driver_info"]["install_command"]


def test_pyproject_has_postgresql_extra_with_sync_pool_and_async_drivers() -> None:
    extras = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["optional-dependencies"]
    names = {requirement.split(">")[0].split("[")[0].strip().lower() for requirement in extras["postgresql"]}

    assert {"psycopg", "psycopg-pool", "asyncpg"} <= names
