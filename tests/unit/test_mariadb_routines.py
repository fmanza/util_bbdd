"""Tests focalizados para helpers publicos de rutinas MariaDB."""

from __future__ import annotations

from util_bbdd.metadata.mariadb.routines import (
    build_mariadb_routine_ddl,
    build_public_mariadb_routine_parameter_rows,
    decode_mariadb_routine_detail_rows,
    decode_mariadb_routine_parameter_detail_rows,
    filter_mariadb_routine_parameter_rows,
    format_mariadb_definer,
)


def _hex_text(text: str) -> str:
    return text.encode("utf-8").hex()


def test_decode_mariadb_routine_detail_rows_decodes_hex_fields() -> None:
    rows = [
        (
            _hex_text("calcular_total"),
            "function",
            _hex_text("comentario"),
            _hex_text("app@localhost"),
            _hex_text("invoker"),
            _hex_text("reads sql data"),
            "yes",
            _hex_text("DECIMAL(10,2)"),
            _hex_text("STRICT_ALL_TABLES"),
            _hex_text("RETURN subtotal * 1.21"),
        )
    ]

    decoded = decode_mariadb_routine_detail_rows(rows)

    assert decoded == [
        {
            "routine_name": "calcular_total",
            "routine_type": "FUNCTION",
            "routine_comment": "comentario",
            "definer": "app@localhost",
            "security_type": "INVOKER",
            "sql_data_access": "READS SQL DATA",
            "is_deterministic": "YES",
            "return_type": "DECIMAL(10,2)",
            "sql_mode": "STRICT_ALL_TABLES",
            "routine_definition": "RETURN subtotal * 1.21",
        }
    ]


def test_decode_mariadb_routine_parameter_rows_and_public_contract() -> None:
    rows = [
        (
            _hex_text("in"),
            _hex_text("p_id"),
            "procedure",
            _hex_text("sync_users"),
            _hex_text("INT"),
            _hex_text(""),
            _hex_text(""),
            1,
        ),
        (
            "RETURN",
            "RETURN_VALUE",
            "function",
            _hex_text("build_label"),
            _hex_text("VARCHAR(50)"),
            _hex_text("utf8mb4"),
            _hex_text("utf8mb4_general_ci"),
            0,
        ),
    ]

    decoded = decode_mariadb_routine_parameter_detail_rows(rows)
    filtered = filter_mariadb_routine_parameter_rows(
        decoded,
        routine_name="sync_users",
        routine_type="procedure",
    )

    assert filtered == [decoded[0]]
    assert build_public_mariadb_routine_parameter_rows(filtered) == [("IN", "p_id", "INT", "", 1)]
    assert decoded[1]["mode"] == "RETURN"
    assert decoded[1]["name"] == "RETURN_VALUE"


def test_format_mariadb_definer_quotes_user_and_host() -> None:
    assert format_mariadb_definer("app@localhost") == "`app`@`localhost`"
    assert format_mariadb_definer("`svc`@`%`") == "`svc`@`%`"


def test_build_mariadb_routine_ddl_uses_format_and_ddl_helpers() -> None:
    ddl = build_mariadb_routine_ddl(
        database="demo",
        routine_name="build_label",
        routine_type="FUNCTION",
        routine_definition="RETURN CONCAT('ID-', p_id)",
        definer="app@localhost",
        security_type="INVOKER",
        sql_data_access="READS SQL DATA",
        is_deterministic="YES",
        return_type="VARCHAR(20)",
        routine_comment="doc's routine",
        parameters=[
            {
                "mode": "IN",
                "name": "p_id",
                "data_type": "INT",
                "default_value": "",
                "charset": "",
                "collation": "",
            },
            {
                "mode": "RETURN",
                "name": "RETURN_VALUE",
                "data_type": "VARCHAR(20)",
                "default_value": "",
                "charset": "utf8mb4",
                "collation": "utf8mb4_general_ci",
            },
        ],
    )

    assert "CREATE DEFINER=`app`@`localhost` FUNCTION `demo`.`build_label`(p_id INT)" in ddl
    assert "RETURNS VARCHAR(20) CHARSET utf8mb4 COLLATE utf8mb4_general_ci" in ddl
    assert "DETERMINISTIC" in ddl
    assert "SQL SECURITY INVOKER" in ddl
    assert "COMMENT 'doc''s routine'" in ddl
    assert ddl.endswith("RETURN CONCAT('ID-', p_id)")
