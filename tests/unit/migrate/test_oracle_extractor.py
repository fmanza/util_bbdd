"""``OracleSchemaExtractor``: columnas, índices y packages desde el snapshot con las convenciones de ``ALL_TAB_COLS`` (C3)."""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd.migrate.extractors import OracleSchemaExtractor
from util_bbdd.migrate.ir.models import CanonicalColumn

from ._snapshot_source import col, fake_manager, index, routine, table


def _column(data_type: str, base_type: str, **kw: Any) -> CanonicalColumn:
    (t,) = OracleSchemaExtractor(
        fake_manager("oracle", table("T"), col("T", "C", 1, data_type, base_type, **kw))
    ).extract("HR")
    return t.columns[0]


@pytest.mark.parametrize(
    ("data_type", "base_type", "kw", "expected"),
    [
        ("VARCHAR2(30 CHAR)", "VARCHAR2", {"length": 30}, ("VARCHAR2", 30, None, None)),
        ("NVARCHAR2(20)", "NVARCHAR2", {"length": 20}, ("NVARCHAR2", 20, None, None)),
        ("NUMBER(12,2)", "NUMBER", {"precision": 12, "scale": 2}, ("NUMBER", None, 12, 2)),
        ("NUMBER", "NUMBER", {}, ("NUMBER", None, None, None)),
        ("NUMBER(*,0)", "NUMBER", {"scale": 0}, ("NUMBER", None, None, 0)),
        ("FLOAT(126)", "FLOAT", {"precision": 126}, ("FLOAT", None, 126, None)),
        ("RAW(16)", "RAW", {}, ("RAW", 16, None, None)),
        ("DATE", "DATE", {}, ("DATE", None, None, None)),
        ("TIMESTAMP(3)", "TIMESTAMP", {}, ("TIMESTAMP(3)", None, None, 3)),
        ("TIMESTAMP(6) WITH TIME ZONE", "TIMESTAMP WITH TIME ZONE", {}, ("TIMESTAMP(6) WITH TIME ZONE", None, None, 6)),
        ("INTERVAL YEAR(2) TO MONTH", "INTERVAL YEAR TO MONTH", {}, ("INTERVAL YEAR(2) TO MONTH", None, 2, 0)),
        ("INTERVAL DAY(3) TO SECOND(6)", "INTERVAL DAY TO SECOND", {}, ("INTERVAL DAY(3) TO SECOND(6)", None, 3, 6)),
        ("CLOB", "CLOB", {}, ("CLOB", None, None, None)),
    ],
)
def test_types_follow_all_tab_cols(
    data_type: str, base_type: str, kw: dict[str, Any], expected: tuple[Any, ...]
) -> None:
    c = _column(data_type, base_type, **kw)
    assert (c.source_type, c.char_length, c.precision, c.scale) == expected


def test_identity_is_auto_increment_without_sequence_default() -> None:
    c = _column("NUMBER(10)", "NUMBER", precision=10, scale=0, identity="always", default='"HR"."ISEQ$$_1".nextval')
    assert (c.auto_increment, c.default) == (True, None)


def test_plain_default_is_kept_and_virtual_column_has_none() -> None:
    assert _column("DATE", "DATE", default="SYSDATE").default == "SYSDATE"
    assert _column("NUMBER", "NUMBER", generated='"A"*2').default is None


def test_indexes_include_primary_and_read_desc_columns_by_name() -> None:
    (t,) = OracleSchemaExtractor(
        fake_manager(
            "oracle",
            table("T"),
            col("T", "ID", 1, "NUMBER"),
            col("T", "TS", 2, "DATE"),
            index("T", "PK_T", "ID", unique=True, primary=True),
            index("T", "IX_DESC", "ID", '"TS"'),
            index("T", "IX_EXPR", 'UPPER("TS")'),
        )
    ).extract("HR")
    assert [(i.name, i.columns) for i in t.indexes] == [("PK_T", ["ID"]), ("IX_DESC", ["ID", "TS"])]
    assert [w.code for w in t.warnings] == ["INDEX_EXPRESSION_SKIPPED"]


def test_standalone_routines_packages_and_members() -> None:
    routines = OracleSchemaExtractor(
        fake_manager(
            "oracle",
            routine("F", "FUNCTION", "CREATE OR REPLACE FUNCTION F RETURN NUMBER IS ...", return_type="NUMBER"),
            routine("P", "PROCEDURE"),
            routine("PKG", "PACKAGE"),
            routine("PKG.F1", "FUNCTION", return_type="NUMBER"),
            routine("PKG.P1", "PROCEDURE"),
        )
    ).extract_routines("HR")
    f, p, pkg, f1, p1 = routines
    assert (f.body.startswith("CREATE OR REPLACE FUNCTION"), f.is_package_member, f.warnings) == (True, False, [])
    assert [w.code for w in p.warnings] == ["ROUTINE_NO_BODY"]
    assert "ALL_SOURCE" in p.warnings[0].message
    assert [(r.name, r.routine_type, r.package_name, r.is_package_member, r.body) for r in (pkg, f1, p1)] == [
        ("PKG", "PROCEDURE", "PKG", True, ""),
        ("F1", "FUNCTION", "PKG", True, ""),
        ("P1", "PROCEDURE", "PKG", True, ""),
    ]
    assert {w.code for r in (pkg, f1, p1) for w in r.warnings} == {"ROUTINE_PACKAGE_MEMBER"}
    assert f1.warnings[0].message.startswith("'F1' es un ORACLE PACKAGE")
