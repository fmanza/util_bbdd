"""U-T7 (G18 de util_bbdd_web): todo parámetro interpolado con ``{nombre}`` se valida, no solo tabla/schema."""

from __future__ import annotations

import json

from decimal import Decimal
from pathlib import Path

import pytest

from util_bbdd.exceptions import QueryValidationError
from util_bbdd.query import QueryRegistry, QueryResolver
from util_bbdd.validators.base_validator import check_interpolated_params

pytestmark = pytest.mark.unit

TEMPLATE = "SELECT * FROM {tabla} WHERE estado = {estado} AND creado > :desde LIMIT {limite}"


@pytest.fixture
def resolver(tmp_path: Path) -> QueryResolver:
    queries = {engine: {"filtrar": TEMPLATE} for engine in ("postgresql", "sqlserver", "oracle", "sqlite")}
    path = tmp_path / "queries.json"
    path.write_text(json.dumps(queries), encoding="utf-8")
    return QueryResolver(QueryRegistry(path), db_type="postgresql")


@pytest.mark.parametrize(
    "estado",
    ["1; DROP TABLE x", "'a' OR 1=1", "a b", "x--", "x/*", 'a"b', True, float("nan"), ["a"]],
)
def test_unsafe_interpolated_values_are_rejected(resolver: QueryResolver, estado: object) -> None:
    with pytest.raises(QueryValidationError, match="'estado' is interpolated"):
        resolver.resolve("filtrar", {"tabla": "pedidos", "estado": estado, "limite": 10, "desde": "2024-01-01"})


@pytest.mark.parametrize("estado", ["", None])
def test_empty_values_are_rejected_as_required(resolver: QueryResolver, estado: object) -> None:
    with pytest.raises(QueryValidationError):  # lo rechaza antes el validador del motor (parámetro requerido)
        resolver.resolve("filtrar", {"tabla": "pedidos", "estado": estado, "limite": 10, "desde": "2024-01-01"})


@pytest.mark.parametrize("estado", ["ACTIVO", "dbo@x", "a$b#c", 7, -3, 2.5, Decimal("10.5")])
def test_identifiers_and_numbers_are_interpolated(resolver: QueryResolver, estado: object) -> None:
    resolved = resolver.resolve("filtrar", {"tabla": "pedidos", "estado": estado, "limite": 10, "desde": "x y'z"})
    assert f"estado = {estado} AND" in resolved.final_sql
    assert ":desde" in resolved.final_sql  # el valor de texto va por bind, sin validar ni interpolar


def test_only_fields_of_the_template_are_checked() -> None:
    assert check_interpolated_params("SELECT {a} FROM t WHERE b = :b", {"a": "col", "b": "'; DROP", "c": "x y"}) == []
    assert check_interpolated_params("SELECT {obj.attr}, {arr[0]}", {"obj": "a b", "arr": "ok"})[0].startswith(
        "Parameter 'obj'"
    )


def test_missing_parameter_keeps_its_error(resolver: QueryResolver) -> None:
    from util_bbdd.exceptions import QueryParameterError

    with pytest.raises((QueryParameterError, QueryValidationError)):
        resolver.resolve("filtrar", {"tabla": "pedidos", "limite": 1})
