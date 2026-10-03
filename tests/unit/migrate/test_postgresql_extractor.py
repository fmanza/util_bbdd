"""``PostgreSQLSchemaExtractor``: columnas del snapshot con las convenciones de ``information_schema`` (C3)."""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd.migrate.extractors import PostgreSQLSchemaExtractor
from util_bbdd.migrate.ir.models import CanonicalColumn

from ._snapshot_source import col, fake_manager, table


def _column(data_type: str, base_type: str, **kw: Any) -> CanonicalColumn:
    (t,) = PostgreSQLSchemaExtractor(
        fake_manager("postgresql", table("t"), col("t", "c", 1, data_type, base_type, **kw))
    ).extract("public")
    return t.columns[0]


@pytest.mark.parametrize(
    ("data_type", "base_type", "kw", "expected"),
    [
        ("integer", "integer", {}, ("INTEGER", None, 32, 0)),
        ("smallint", "smallint", {}, ("SMALLINT", None, 16, 0)),
        ("bigint", "bigint", {}, ("BIGINT", None, 64, 0)),
        ("real", "real", {}, ("REAL", None, 24, None)),
        ("double precision", "double precision", {}, ("DOUBLE PRECISION", None, 53, None)),
        ("numeric(12,2)", "numeric", {"precision": 12, "scale": 2}, ("NUMERIC", None, 12, 2)),
        ("numeric", "numeric", {}, ("NUMERIC", None, None, None)),
        ("character varying(30)", "character varying", {"length": 30}, ("CHARACTER VARYING", 30, None, None)),
        ("character varying", "character varying", {}, ("CHARACTER VARYING", None, None, None)),
        ("character(3)", "character", {"length": 3}, ("CHARACTER", 3, None, None)),
        ("bit(3)", "bit", {"length": 3}, ("BIT", 3, None, None)),
        (
            "timestamp(3) without time zone",
            "timestamp without time zone",
            {},
            ("TIMESTAMP WITHOUT TIME ZONE", None, None, None),
        ),
        ("integer[]", "ARRAY", {}, ("ARRAY", None, None, None)),
        ("mood", "USER-DEFINED", {}, ("USER-DEFINED", None, None, None)),
        ("jsonb", "jsonb", {}, ("JSONB", None, None, None)),
    ],
)
def test_types_follow_information_schema(
    data_type: str, base_type: str, kw: dict[str, Any], expected: tuple[Any, ...]
) -> None:
    c = _column(data_type, base_type, **kw)
    assert (c.source_type, c.char_length, c.precision, c.scale) == expected


@pytest.mark.parametrize(
    ("kw", "auto_increment"),
    [
        ({"default": "nextval('t_c_seq'::regclass)"}, True),
        ({"default": "NEXTVAL('t_c_seq'::regclass)"}, True),
        ({"identity": "always"}, True),
        ({"identity": "by default"}, True),
        ({"default": "42"}, False),
        ({}, False),
    ],
)
def test_serial_and_identity_are_auto_increment(kw: dict[str, Any], auto_increment: bool) -> None:
    c = _column("integer", "integer", **kw)
    assert c.auto_increment is auto_increment
    assert c.default == kw.get("default")


def test_generated_column_has_no_default() -> None:
    c = _column("integer", "integer", generated="(a * 2)")
    assert (c.default, c.auto_increment) == (None, False)
