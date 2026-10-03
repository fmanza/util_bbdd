"""``SQLServerSchemaExtractor``: columnas y vistas desde el snapshot con las convenciones de ``INFORMATION_SCHEMA`` (C3)."""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd.migrate.extractors import SQLServerSchemaExtractor
from util_bbdd.migrate.ir.models import CanonicalColumn

from ._snapshot_source import col, fake_manager, routine, table, view


def _column(data_type: str, base_type: str, **kw: Any) -> CanonicalColumn:
    (t,) = SQLServerSchemaExtractor(
        fake_manager("sqlserver", table("t"), col("t", "c", 1, data_type, base_type, **kw))
    ).extract("dbo")
    return t.columns[0]


@pytest.mark.parametrize(
    ("data_type", "base_type", "kw", "expected"),
    [
        ("int", "int", {}, ("INT", None, 10, 0)),
        ("bigint", "bigint", {}, ("BIGINT", None, 19, 0)),
        ("money", "money", {}, ("MONEY", None, 19, 4)),
        ("float", "float", {}, ("FLOAT", None, 53, None)),
        ("decimal(12,2)", "decimal", {"precision": 12, "scale": 2}, ("DECIMAL", None, 12, 2)),
        ("nvarchar(50)", "nvarchar", {"length": 50}, ("NVARCHAR", 50, None, None)),
        ("varchar(max)", "varchar", {}, ("VARCHAR", -1, None, None)),
        ("varbinary(max)", "varbinary", {}, ("VARBINARY", -1, None, None)),
        ("text", "text", {}, ("TEXT", 2147483647, None, None)),
        ("ntext", "ntext", {}, ("NTEXT", 1073741823, None, None)),
        ("xml", "xml", {}, ("XML", -1, None, None)),
        ("datetime2(3)", "datetime2", {}, ("DATETIME2", None, None, None)),
        ("bit", "bit", {}, ("BIT", None, None, None)),
        ("code_t", "varchar", {"length": 10}, ("VARCHAR", 10, None, None)),  # tipo alias → tipo de sistema
        ("timestamp", "timestamp", {}, ("TIMESTAMP", None, None, None)),  # rowversion
    ],
)
def test_types_follow_information_schema(
    data_type: str, base_type: str, kw: dict[str, Any], expected: tuple[Any, ...]
) -> None:
    c = _column(data_type, base_type, **kw)
    assert (c.source_type, c.char_length, c.precision, c.scale) == expected


def test_identity_and_default() -> None:
    assert _column("int", "int", identity="by default").auto_increment is True
    c = _column("int", "int", default="((0))")
    assert (c.default, c.auto_increment) == ("((0))", False)


def _views(*objects: object) -> list[Any]:
    return SQLServerSchemaExtractor(fake_manager("sqlserver", *objects)).extract_views("dbo")


def test_create_view_header_is_removed() -> None:
    (v,) = _views(view("v", "CREATE VIEW dbo.v AS\nSELECT 1 AS x", "vista"), col("v", "x", 1, "int"))
    assert (v.query, v.columns, v.comment, v.warnings) == ("SELECT 1 AS x", ["x"], "vista", [])


def test_long_definition_is_not_truncated() -> None:
    body = "SELECT " + ", ".join(f"{i} AS c{i}" for i in range(1500))
    (v,) = _views(view("v", f"CREATE VIEW v AS {body}"))
    assert v.query == body


def test_header_column_list_and_unavailable_definition_warn() -> None:
    header, hidden = _views(view("h", "CREATE VIEW h (a) AS SELECT 1"), view("x", None))
    assert [w.code for w in header.warnings] == ["VIEW_HEADER_COLUMNS"]
    assert (hidden.query, [w.code for w in hidden.warnings]) == ("", ["VIEW_DEFINITION_UNAVAILABLE"])


def test_clr_routines_are_not_migrated() -> None:
    routines = SQLServerSchemaExtractor(
        fake_manager(
            "sqlserver",
            routine("p", "PROCEDURE", "CREATE PROCEDURE p AS SELECT 1", language="TSQL"),
            routine("clr", "PROCEDURE", language="CLR"),
        )
    ).extract_routines("dbo")
    assert [r.name for r in routines] == ["p"]
