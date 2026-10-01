"""P-1 (sesión 2026-10-01l): filtro de OPENJSON por columna, equivalente exacto del filtro por valor del hotfix A1.

``_fits`` (por valor) decide si una clave cabe exactamente en el tipo de la PK; si no cabe, el DELETE de SQL Server va por
``IN``. Costaba 0,40 s/1M con PK entera y 2,06 s/1M con PK ``DECIMAL``. ``_column_fits`` decide lo mismo para una columna
entera con operaciones agregadas. Cualquier divergencia reabriría A1 (borrado de filas no pedidas), así que se compara con
``_fits`` en miles de listas aleatorias, con los bordes exactos de cada tipo.
"""

from __future__ import annotations

import decimal
import random
import uuid

from typing import Any

import pytest

from sqlalchemy import NCHAR, NVARCHAR, BigInteger, Float, Integer, Numeric, SmallInteger, String, Uuid
from sqlalchemy.dialects.mssql import TINYINT

from util_bbdd.bulk._execution.delete_strategies import _column_fits, _fits, _openjson_payload

pytestmark = pytest.mark.unit

D = decimal.Decimal

_TYPES: list[Any] = [
    TINYINT(),
    SmallInteger(),
    Integer(),
    BigInteger(),
    Numeric(8, 2),
    Numeric(4, 0),
    Numeric(38, 10),
    Float(),
    String(5),
    String(None),
    NVARCHAR(3),
    NCHAR(2),
    Uuid(),
]

_POOL: list[Any] = [
    None,
    0,
    1,
    -1,
    255,
    256,
    -(2**15),
    -(2**15) - 1,
    2**15 - 1,
    2**31 - 1,
    2**31,
    -(2**31),
    2**63 - 1,
    2**63,
    10**6 - 1,
    10**6,
    True,
    False,
    1.5,
    float("nan"),
    D("1.10"),
    D("1.100"),
    D("1.105"),
    D("123456.78"),
    D("999999.99"),
    D("1000000.00"),
    D("-999999.99"),
    D("0E-10"),
    D("1E+3"),
    D("9999"),
    D("NaN"),
    D("Infinity"),
    D("1" * 28 + ".1234567890"),
    D("1" * 29 + ".12345678901"),
    "",
    "a",
    "abcde",
    "abcdef",
    "α",
    "αβγ",
    "αβγδ",
    "😀",
    "😀a",
    "x" * 3,
    uuid.UUID(int=1),
    "12345678-1234-5678-1234-567812345678",
    b"x",
]


def _reference(values: list[Any], column_type: Any) -> bool:
    return all(_fits(v, column_type) for v in values if v is not None)


@pytest.mark.parametrize("column_type", _TYPES, ids=lambda t: repr(t))
def test_single_values_match_reference(column_type: Any) -> None:
    for value in _POOL:
        assert _column_fits([value], column_type) == _reference([value], column_type), value


@pytest.mark.parametrize("column_type", _TYPES, ids=lambda t: repr(t))
def test_random_lists_match_reference(column_type: Any) -> None:
    rng = random.Random(20261001)
    for _ in range(2000):
        values = [rng.choice(_POOL) for _ in range(rng.randint(0, 6))]
        assert _column_fits(values, column_type) == _reference(values, column_type), values


@pytest.mark.parametrize("column_type", [Integer(), Numeric(8, 2), String(5), NVARCHAR(3), TINYINT()], ids=repr)
def test_homogeneous_lists_match_reference(column_type: Any) -> None:
    """Listas de un solo tipo (el caso real de una columna de PK), donde actúan las vías rápidas."""
    rng = random.Random(7)
    by_kind: dict[type, list[Any]] = {}
    for value in _POOL:
        if value is not None:
            by_kind.setdefault(type(value), []).append(value)
    for values_of_kind in by_kind.values():
        for _ in range(300):
            values = [rng.choice(values_of_kind) for _ in range(rng.randint(1, 8))] + [None] * rng.randint(0, 2)
            assert _column_fits(values, column_type) == _reference(values, column_type), values


def test_payload_keeps_the_previous_json() -> None:
    assert _openjson_payload([[1, None, 3]], [Integer()]) == "[1, null, 3]"
    assert _openjson_payload([[D("1.10"), D("0E-10")]], [Numeric(8, 2)]) == '["1.10", "0.0000000000"]'
    assert _openjson_payload([[D("1.10")], ["a"]], [Numeric(8, 2), String(5)]) == '[["1.10", "a"]]'
    assert _openjson_payload([[uuid.UUID(int=1)]], [Uuid()]) == '["00000000-0000-0000-0000-000000000001"]'
    assert _openjson_payload([[1, 256]], [TINYINT()]) is None
