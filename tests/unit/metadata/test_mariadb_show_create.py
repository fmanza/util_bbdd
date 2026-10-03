"""``SHOW CREATE TABLE`` reconstruido desde ``information_schema`` (H-29): reglas de formato de MySQL y MariaDB.

La paridad con la reflexión tabla a tabla se verifica contra los servidores en
``tests/integration/test_comparar_prefetch_engines.py``; aquí, el texto y su lectura con el parser de SQLAlchemy.
"""

from __future__ import annotations

from typing import Any

import pytest

from sqlalchemy.dialects.mysql import base as mysql_base

from util_bbdd.metadata.mariadb._show_create import SchemaRows, build_show_create, statistics_sql

QUOTE = mysql_base.MySQLDialect().identifier_preparer.quote_identifier


def _column(name: str, column_type: str, *, nullable: str = "YES", default: Any = None, extra: str = "",
            comment: str = "", charset: Any = None, collation: Any = None, generated: Any = None) -> tuple[Any, ...]:  # fmt: skip
    return ("t", name, column_type, nullable, default, extra, comment, charset, collation, generated)


def _rows(*columns: tuple[Any, ...], indexes: tuple[Any, ...] = (), fks: tuple[Any, ...] = (),
          rules: tuple[Any, ...] = ()) -> SchemaRows:  # fmt: skip
    return SchemaRows.from_results([("t", "InnoDB", "utf8mb4_0900_ai_ci", "tabla 't'")], columns, indexes, fks, rules)


def _lines(server: str, rows: SchemaRows) -> list[str]:
    return build_show_create(server, "db", "t", rows, QUOTE).split("\n")


@pytest.mark.parametrize(
    ("server", "default", "extra", "column_type", "expected"),
    [
        ("mysql", "0", "", "int", "  `c` int DEFAULT '0'"),
        ("mysql", "it's", "", "varchar(5)", "  `c` varchar(5) DEFAULT 'it''s'"),
        ("mysql", "a\\b", "", "varchar(5)", "  `c` varchar(5) DEFAULT 'a\\\\b'"),
        ("mysql", "b'101'", "", "bit(3)", "  `c` bit(3) DEFAULT b'101'"),
        (
            "mysql",
            "CURRENT_TIMESTAMP(3)",
            "DEFAULT_GENERATED",
            "datetime(3)",
            "  `c` datetime(3) DEFAULT CURRENT_TIMESTAMP(3)",
        ),
        ("mysql", "uuid()", "DEFAULT_GENERATED", "char(36)", "  `c` char(36) DEFAULT (uuid())"),
        (
            "mysql",
            "CURRENT_TIMESTAMP",
            "DEFAULT_GENERATED on update CURRENT_TIMESTAMP",
            "timestamp",
            "  `c` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        ),
        ("mariadb", "0", "", "int(11)", "  `c` int(11) DEFAULT 0"),
        ("mariadb", "'x'", "", "varchar(5)", "  `c` varchar(5) DEFAULT 'x'"),
        ("mariadb", "NULL", "", "int(11)", "  `c` int(11) DEFAULT NULL"),
        ("mariadb", "uuid()", "", "char(36)", "  `c` char(36) DEFAULT uuid()"),
    ],
)
def test_default_rendering(server: str, default: str, extra: str, column_type: str, expected: str) -> None:
    assert _lines(server, _rows(_column("c", column_type, default=default, extra=extra)))[1] == expected


def test_collation_generated_auto_increment_and_comment() -> None:
    lines = _lines(
        "mysql",
        _rows(
            _column("id", "bigint unsigned", nullable="NO", extra="auto_increment"),
            _column("v", "varchar(9)", charset="latin1", collation="latin1_bin"),
            _column("w", "varchar(9)", charset="utf8mb4", collation="utf8mb4_0900_ai_ci"),
            _column("g", "int", nullable="NO", extra="STORED GENERATED", generated="(`i` + 1)"),
            _column("c", "varchar(5)", comment="com'ent \\ x"),
        ),
    )
    assert [line.rstrip(",") for line in lines[1:6]] == [
        "  `id` bigint unsigned NOT NULL AUTO_INCREMENT",
        "  `v` varchar(9) CHARACTER SET latin1 COLLATE latin1_bin",
        "  `w` varchar(9)",  # la collation de la tabla no se escribe
        "  `g` int GENERATED ALWAYS AS ((`i` + 1)) STORED NOT NULL",
        "  `c` varchar(5) COMMENT 'com''ent \\\\ x'",
    ]
    assert lines[-1] == ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='tabla ''t'''"


def test_keys_in_show_create_order_with_prefix_desc_and_expression() -> None:
    indexes = (
        ("t", "ft", 1, "tx", None, None, "FULLTEXT", None),
        ("t", "ix", 1, "i", None, "D", "BTREE", None),
        ("t", "ix", 1, "v", 10, "A", "BTREE", None),
        ("t", "fx", 1, None, None, "A", "BTREE", "lower(`v`)"),
        ("t", "PRIMARY", 0, "id", None, "A", "BTREE", None),
        ("t", "uk", 0, "v", None, "A", "BTREE", None),
    )
    lines = _lines("mysql", _rows(_column("id", "int"), indexes=indexes))
    assert (
        lines[2:-1]
        == [
            "  PRIMARY KEY (`id`),",
            "  UNIQUE KEY `uk` (`v`),",
            "  KEY `fx` ((lower(`v`))),",
            "  KEY `ix` (`i` DESC,`v`(10)),",
            "  FULLTEXT KEY `ft` (`tx`)",
        ]
        or lines
    )


@pytest.mark.parametrize(
    ("server", "rules", "suffix"),
    [
        ("mysql", ("NO ACTION", "NO ACTION"), ""),
        ("mysql", ("RESTRICT", "NO ACTION"), " ON DELETE RESTRICT"),
        ("mariadb", ("RESTRICT", "RESTRICT"), ""),
        ("mariadb", ("NO ACTION", "RESTRICT"), " ON DELETE NO ACTION"),
        ("mysql", ("SET NULL", "CASCADE"), " ON DELETE SET NULL ON UPDATE CASCADE"),
    ],
)
def test_foreign_keys_omit_the_implicit_rule_of_each_server(server: str, rules: tuple[str, str], suffix: str) -> None:
    fks = (("t", "fk", "a", "db", "p", "x"), ("t", "fk", "b", "db", "p", "y"))
    rows = _rows(_column("a", "int"), fks=fks, rules=(("t", "fk", *rules),))
    line = _lines(server, rows)[2]
    assert line == f"  CONSTRAINT `fk` FOREIGN KEY (`a`, `b`) REFERENCES `p` (`x`, `y`){suffix}"


def test_reference_to_other_schema_is_qualified_and_parsed() -> None:
    rows = _rows(
        _column("a", "int"), fks=(("t", "fk", "a", "otra", "p", "x"),), rules=(("t", "fk", "CASCADE", "NO ACTION"),)
    )
    sql = build_show_create("mysql", "db", "t", rows, QUOTE)
    assert "REFERENCES `otra`.`p` (`x`) ON DELETE CASCADE" in sql
    state = mysql_base.MySQLDialect()._tabledef_parser.parse(sql, "utf8mb4")
    assert state.fk_constraints[0]["table"] == ["otra", "p"]
    assert state.table_options["mysql_comment"] == "tabla 't'"


def test_statistics_expression_only_in_mysql() -> None:
    assert "EXPRESSION" in statistics_sql("mysql")
    assert "EXPRESSION" not in statistics_sql("mariadb")
