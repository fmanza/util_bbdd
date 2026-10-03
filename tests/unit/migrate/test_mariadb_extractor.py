"""Extractores MariaDB/MySQL: columnas del snapshot con las convenciones de ``INFORMATION_SCHEMA`` (C3)."""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd.migrate.extractors import MariaDBSchemaExtractor
from util_bbdd.migrate.extractors.mysql import MariaDBFullTypeSchemaExtractor, MySQLSchemaExtractor
from util_bbdd.migrate.ir.models import CanonicalColumn

from ._snapshot_source import col, fake_manager, table


def _column(extractor: type, data_type: str, base_type: str, **kw: Any) -> CanonicalColumn:
    (t,) = extractor(fake_manager("mariadb", table("t"), col("t", "c", 1, data_type, base_type, **kw))).extract("db")
    return t.columns[0]


@pytest.mark.parametrize(
    ("data_type", "base_type", "kw", "expected"),
    [
        ("int(11)", "int", {}, ("INT", None, 10, 0)),
        ("bigint(20) unsigned", "bigint", {}, ("BIGINT", None, 20, 0)),
        ("tinyint(1)", "tinyint", {}, ("TINYINT", None, 3, 0)),
        ("mediumint", "mediumint", {}, ("MEDIUMINT", None, 7, 0)),
        ("float", "float", {}, ("FLOAT", None, 12, None)),
        ("double(10,4)", "double", {}, ("DOUBLE", None, 10, 4)),
        ("decimal(12,2)", "decimal", {"precision": 12, "scale": 2}, ("DECIMAL", None, 12, 2)),
        ("bit(3)", "bit", {}, ("BIT", None, 3, None)),
        ("varchar(30)", "varchar", {"length": 30}, ("VARCHAR", 30, None, None)),
        ("text", "text", {"length": 65535}, ("TEXT", 65535, None, None)),
        ("longblob", "longblob", {}, ("LONGBLOB", 4294967295, None, None)),
        ("blob", "blob", {}, ("BLOB", 65535, None, None)),
        ("enum('a','bcd','it''s')", "enum", {}, ("ENUM", 4, None, None)),
        ("set('x','y')", "set", {}, ("SET", 3, None, None)),
        ("json", "json", {}, ("JSON", None, None, None)),
        ("datetime(3)", "datetime", {}, ("DATETIME", None, None, None)),
    ],
)
def test_types_follow_information_schema(
    data_type: str, base_type: str, kw: dict[str, Any], expected: tuple[Any, ...]
) -> None:
    c = _column(MariaDBSchemaExtractor, data_type, base_type, **kw)
    assert (c.source_type, c.char_length, c.precision, c.scale) == expected


def test_full_column_types_keep_column_type() -> None:
    assert _column(MariaDBFullTypeSchemaExtractor, "int(10) unsigned", "int").source_type == "int(10) unsigned"
    assert _column(MySQLSchemaExtractor, "enum('a')", "enum").source_type == "ENUM"
    mysql_full = MySQLSchemaExtractor(
        fake_manager("mysql", table("t"), col("t", "c", 1, "enum('a')", "enum")), full_column_types=True
    )
    assert mysql_full.extract("db")[0].columns[0].source_type == "enum('a')"


@pytest.mark.parametrize(
    ("extractor", "kw", "default"),
    [
        (MariaDBSchemaExtractor, {}, "NULL"),  # MariaDB escribe 'NULL' en las nulables sin default
        (MariaDBSchemaExtractor, {"nullable": False}, None),
        (MariaDBSchemaExtractor, {"default": "'x'"}, "'x'"),
        (MySQLSchemaExtractor, {}, None),
        (MySQLSchemaExtractor, {"default": "'x'"}, "'x'"),  # MySQLCatalog ya la entrecomilla
        (MariaDBFullTypeSchemaExtractor, {}, "NULL"),
    ],
)
def test_defaults(extractor: type, kw: dict[str, Any], default: str | None) -> None:
    assert _column(extractor, "varchar(10)", "varchar", length=10, **kw).default == default


def test_auto_increment_from_identity() -> None:
    assert _column(MariaDBSchemaExtractor, "int", "int", identity="by default", nullable=False).auto_increment is True
    assert _column(MariaDBSchemaExtractor, "int", "int").auto_increment is False
