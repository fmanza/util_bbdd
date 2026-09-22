"""Tests focalizados para helpers publicos de rutinas MariaDB."""

from __future__ import annotations

from util_bbdd.metadata.mariadb._adapter_helpers import (
    build_columns_safe_sql,
    build_routine_ddl_from_detail,
    build_view_definition_sql,
    process_view_result,
    routine_entries_to_rows,
)
from util_bbdd.metadata.mariadb._routine_models import MariaDBRoutineDetail, MariaDBRoutineParameterDetail
from util_bbdd.metadata.mariadb.routines import (
    build_mariadb_routine_ddl,
    build_public_mariadb_routine_parameter_entry_rows,
    decode_mariadb_routine_detail_entries,
    decode_mariadb_routine_parameter_detail_entries,
    filter_mariadb_routine_parameter_entries,
    format_mariadb_definer,
)


def _hex_text(text: str) -> str:
    return text.encode("utf-8").hex()


def test_decode_mariadb_routine_detail_entries_decodes_hex_fields() -> None:
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

    decoded = decode_mariadb_routine_detail_entries(rows)

    assert len(decoded) == 1
    assert decoded[0].to_dict() == {
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


def test_decode_mariadb_routine_parameter_entries_and_public_contract() -> None:
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

    decoded = decode_mariadb_routine_parameter_detail_entries(rows)
    filtered = filter_mariadb_routine_parameter_entries(
        decoded,
        routine_name="sync_users",
        routine_type="procedure",
    )

    assert filtered == [decoded[0]]
    assert build_public_mariadb_routine_parameter_entry_rows(filtered) == [("IN", "p_id", "INT", "", 1)]
    assert decoded[1].mode == "RETURN"
    assert decoded[1].name == "RETURN_VALUE"


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


# ---------------------------------------------------------------------------
# F1 — ordinal_position: int | None
# ---------------------------------------------------------------------------


def test_ordinal_position_is_int() -> None:
    raw = (_hex("in"), _hex("p_id"), "procedure", _hex("sp"), _hex("INT"), _hex(""), _hex(""), 3)
    decoded = decode_mariadb_routine_parameter_detail_entries([raw])
    assert decoded[0].ordinal_position == 3
    assert isinstance(decoded[0].ordinal_position, int)


def test_ordinal_position_none_when_row_value_is_none() -> None:
    raw = (_hex("in"), _hex("p_id"), "procedure", _hex("sp"), _hex("INT"), _hex(""), _hex(""), None)
    decoded = decode_mariadb_routine_parameter_detail_entries([raw])
    assert decoded[0].ordinal_position is None


def test_to_public_row_carries_ordinal_position() -> None:
    raw = (_hex("in"), _hex("p_x"), "procedure", _hex("sp"), _hex("INT"), _hex(""), _hex(""), 7)
    decoded = decode_mariadb_routine_parameter_detail_entries([raw])
    public = decoded[0].to_public_row()
    assert public[-1] == 7


# ---------------------------------------------------------------------------
# F3 — _adapter_helpers puras
# ---------------------------------------------------------------------------


def _hex(text: str) -> str:
    return text.encode("utf-8").hex()


def test_build_columns_safe_sql_contains_hex_and_where() -> None:
    sql, params = build_columns_safe_sql("ventas", "pedidos")
    assert "HEX(COLUMN_NAME)" in sql
    assert "table_schema = %(schema)s" in sql
    assert "table_name = %(table)s" in sql
    assert "ORDER BY ordinal_position" in sql
    assert params == {"schema": "ventas", "table": "pedidos"}


def test_build_columns_safe_sql_binds_adversarial_values_instead_of_interpolating() -> None:
    """MEO-02 (AUDIT_CODE 2026-09-22): un escapado por duplicado de comillas simples sin
    escapar backslash es bypasseable bajo el sql_mode por defecto de MariaDB/MySQL. El fix
    bindea schema/table como parámetros reales en vez de interpolarlos en el SQL."""
    sql, params = build_columns_safe_sql("db\\'; DROP TABLE x; --", "ta'ble")

    assert "DROP TABLE" not in sql
    assert "db" not in sql
    assert "ta'ble" not in sql
    assert params == {"schema": "db\\'; DROP TABLE x; --", "table": "ta'ble"}


def test_build_view_definition_sql_uses_schema_condition() -> None:
    sql, params = build_view_definition_sql("my_db", "v_resumen")
    assert "TABLE_SCHEMA = %(schema)s" in sql
    assert "TABLE_NAME = %(view)s" in sql
    assert "LIMIT 1" in sql
    assert params == {"view": "v_resumen", "schema": "my_db"}


def test_build_view_definition_sql_empty_database_uses_database_function() -> None:
    sql, params = build_view_definition_sql("", "v_test")
    assert "TABLE_SCHEMA = DATABASE()" in sql
    assert params == {"view": "v_test"}


def test_process_view_result_returns_create_view() -> None:
    row = ("SELECT id FROM t",)
    result = process_view_result(row, "v_ids")
    assert result.startswith("CREATE OR REPLACE VIEW `v_ids` AS")
    assert "SELECT id FROM t" in result


def test_process_view_result_fallback_on_empty() -> None:
    assert "unavailable" in process_view_result(None, "v_x")
    assert "unavailable" in process_view_result(("",), "v_x")


def test_routine_entries_to_rows_sorts_by_type_then_name() -> None:
    def _make(name: str, rtype: str) -> MariaDBRoutineDetail:
        return MariaDBRoutineDetail(
            routine_name=name,
            routine_type=rtype,
            routine_comment="",
            definer="",
            security_type="",
            sql_data_access="",
            is_deterministic="",
            return_type="",
            sql_mode="",
            routine_definition="",
        )

    entries = [_make("z_proc", "PROCEDURE"), _make("a_func", "FUNCTION"), _make("b_proc", "PROCEDURE")]
    rows = routine_entries_to_rows(entries)
    assert rows[0] == ("a_func", "FUNCTION", "")
    assert rows[1][0] == "b_proc"
    assert rows[2][0] == "z_proc"


def test_routine_entries_to_rows_skips_empty_names() -> None:
    def _make(name: str) -> MariaDBRoutineDetail:
        return MariaDBRoutineDetail(
            routine_name=name,
            routine_type="PROCEDURE",
            routine_comment="",
            definer="",
            security_type="",
            sql_data_access="",
            is_deterministic="",
            return_type="",
            sql_mode="",
            routine_definition="",
        )

    rows = routine_entries_to_rows([_make(""), _make("  "), _make("sp_ok")])
    assert len(rows) == 1
    assert rows[0][0] == "sp_ok"


def test_build_routine_ddl_from_detail_delegates_to_ddl_builder() -> None:
    target = MariaDBRoutineDetail(
        routine_name="calcular",
        routine_type="FUNCTION",
        routine_comment="",
        definer="app@host",
        security_type="INVOKER",
        sql_data_access="READS SQL DATA",
        is_deterministic="YES",
        return_type="INT",
        sql_mode="",
        routine_definition="RETURN 1",
    )
    params: list[MariaDBRoutineParameterDetail] = []
    ddl = build_routine_ddl_from_detail(
        database="db",
        routine_name="calcular",
        routine_type="FUNCTION",
        target_row=target,
        parameters=params,
    )
    assert "calcular" in ddl
    assert "RETURN 1" in ddl
