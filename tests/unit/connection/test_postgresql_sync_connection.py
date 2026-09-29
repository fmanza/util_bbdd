"""Conexión sync directa de PostgreSQL (psycopg3): kwargs válidos para libpq (H2)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from util_bbdd.connection.postgresql.connection_postgresql import PostgreSQLConnection

psycopg = pytest.importorskip("psycopg")

BASE: dict[str, Any] = {"host": "db", "user": "app", "password": "pw", "database": "ventas"}


def _connect_validating_conninfo(**kwargs: Any) -> dict[str, Any]:
    """Sustituto de psycopg.connect que valida los kwargs como libpq (sin red) y los devuelve."""
    psycopg.conninfo.make_conninfo(**kwargs)
    return kwargs


def test_database_is_passed_as_dbname() -> None:
    """``database`` no es una opción de libpq: psycopg.connect la rechazaba en toda conexión directa."""
    with patch("psycopg.connect", side_effect=_connect_validating_conninfo):
        kwargs = PostgreSQLConnection.connect(dict(BASE))
    assert kwargs["dbname"] == "ventas"
    assert "database" not in kwargs


def test_explicit_dbname_wins_over_database() -> None:
    with patch("psycopg.connect", side_effect=_connect_validating_conninfo):
        kwargs = PostgreSQLConnection.connect({**BASE, "dbname": "otra"})
    assert kwargs["dbname"] == "otra"
    assert "database" not in kwargs


def test_schema_still_goes_to_options() -> None:
    with patch("psycopg.connect", side_effect=_connect_validating_conninfo):
        kwargs = PostgreSQLConnection.connect({**BASE, "schema": "ventas_s"})
    assert kwargs["options"] == "-c search_path=ventas_s"


@pytest.mark.parametrize(("keepalives", "expected"), [(True, 1), (False, 0)])
def test_boolean_options_are_sent_as_integers(keepalives: bool, expected: int) -> None:
    """libpq rechaza ``keepalives="True"`` en el servidor ("invalid integer value"); make_conninfo no lo detecta."""
    with patch("psycopg.connect", side_effect=_connect_validating_conninfo):
        kwargs = PostgreSQLConnection.connect({**BASE, "keepalives": keepalives})
    assert kwargs["keepalives"] == expected
    assert type(kwargs["keepalives"]) is int


def test_tcp_keepalives_are_sent_with_libpq_names() -> None:
    """``tcp_keepalives_*`` es el nombre del parámetro del servidor; libpq usa ``keepalives_*`` (H6)."""
    with patch("psycopg.connect", side_effect=_connect_validating_conninfo):
        kwargs = PostgreSQLConnection.connect(
            {**BASE, "tcp_keepalives_idle": 30, "tcp_keepalives_interval": 5, "tcp_keepalives_count": 3}
        )
    assert (kwargs["keepalives_idle"], kwargs["keepalives_interval"], kwargs["keepalives_count"]) == (30, 5, 3)
    assert not any(key.startswith("tcp_") for key in kwargs)
