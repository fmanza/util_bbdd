"""``schema`` en Oracle: owner por defecto de los metadatos con la misma conexión (util_bbdd_web G21, 4.1.0).

Hasta 4.0, ``MetadataContextResolver`` usaba siempre el usuario de la conexión como owner y Oracle rechazaba
``schema`` en ``conn_params``: documentar o dibujar otro schema exigía otra conexión con ese usuario. El catálogo ya
leía ``ALL_*`` filtrando por ``OWNER``; faltaba poder elegirlo. No se envía al driver ni cambia ``CURRENT_SCHEMA``.
"""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd.connection.config import OracleConnectionConfig
from util_bbdd.connection.params import ConnectionParamsManager
from util_bbdd.managers._metadata_context import MetadataContextResolver

pytestmark = pytest.mark.unit

BASE: dict[str, Any] = {"user": "bench", "password": "p", "host": "h", "service_name": "FREEPDB1"}


def _context(params: dict[str, Any]) -> str:
    return MetadataContextResolver.get_context_database(db_type="oracle", database="", conn_params=params)


@pytest.mark.parametrize(
    ("schema", "owner"),
    [(None, "BENCH"), ("hr", "HR"), ("HR", "HR"), ('"MixedCase"', "MixedCase"), ("APP$DATA#1", "APP$DATA#1")],
)
def test_schema_selects_the_metadata_owner(schema: str | None, owner: str) -> None:
    params = ConnectionParamsManager.prepare_and_validate("oracle", {**BASE, **({"schema": schema} if schema else {})})

    assert _context(params) == owner


def test_schema_is_not_sent_to_the_driver() -> None:
    params = ConnectionParamsManager.prepare_and_validate("oracle", {**BASE, "schema": "hr"})

    assert "schema" not in ConnectionParamsManager.sanitize_for_connection("oracle", params)
    assert "schema" not in OracleConnectionConfig.from_params(params).to_driver_kwargs()


@pytest.mark.parametrize("schema", ["hr; drop table x", "1hr", "a b", '"a"b"', "x" * 129, '""'])
def test_schema_must_be_an_oracle_identifier(schema: str) -> None:
    with pytest.raises(ValueError, match="schema"):
        ConnectionParamsManager.prepare_and_validate("oracle", {**BASE, "schema": schema})


def test_schema_is_declared_in_the_engine_catalog() -> None:
    from util_bbdd._drivers import get_database_validator

    optional = get_database_validator().get_db_type_info("oracle")["connection_params"]["optional"]
    assert "schema" in {param["name"] for param in optional}
