"""Tests para módulo PostgreSQL: routines, procedimientos y parámetros."""

from __future__ import annotations

from util_bbdd.metadata.postgresql._postgres_models import PgParameterDetail, PgRoutineDetail
from util_bbdd.metadata.postgresql.routines import (
    build_postgres_routine_ddl,
    build_public_postgres_routine_parameter_entry_rows,
    decode_postgres_parameter_rows,
    decode_postgres_routine_rows,
    fetch_routine_parameters_sql,
    fetch_routines_sql,
    filter_postgres_routine_parameter_entries,
    routine_entries_to_rows,
)


class TestRoutinesSql:
    """Tests para queries SQL de rutinas."""

    def test_fetch_routines_sql_default_schema(self) -> None:
        sql = fetch_routines_sql()
        assert isinstance(sql, str)
        assert "%(schema)s" in sql or "public" in sql

    def test_fetch_routines_sql_specific_schema(self) -> None:
        sql = fetch_routines_sql("auth")
        assert isinstance(sql, str)
        assert "%(schema)s" in sql

    def test_fetch_routines_sql_includes_pg_proc(self) -> None:
        sql = fetch_routines_sql()
        assert "pg_proc" in sql

    def test_fetch_routines_sql_includes_routine_type(self) -> None:
        sql = fetch_routines_sql()
        assert "prokind" in sql
        assert "FUNCTION" in sql or "function" in sql.lower()

    def test_fetch_routines_sql_skips_functiondef_for_aggregates(self) -> None:
        """Hotfix 2026-10-02: pg_get_functiondef falla con agregados y hacía fallar la consulta entera.

        Reproducción contra PostgreSQL real: tests/integration/test_postgresql_routines_aggregates.py.
        """
        sql = fetch_routines_sql()
        assert "CASE WHEN p.prokind = 'a' THEN NULL ELSE pg_get_functiondef(p.oid) END" in sql
        assert sql.count("pg_get_functiondef") == 1  # ninguna llamada sin proteger

    def test_fetch_routine_parameters_sql_valid(self) -> None:
        sql = fetch_routine_parameters_sql()
        assert isinstance(sql, str)
        assert "information_schema.parameters" in sql


class TestRoutineDecoding:
    """Tests para decodificación de rutinas."""

    def test_decode_postgres_routine_rows_empty(self) -> None:
        rows: list = []
        result = decode_postgres_routine_rows(rows)
        assert result == []

    def test_decode_postgres_routine_rows_function(self) -> None:
        rows = [
            (
                "calculate_total",
                "FUNCTION",
                "app_user",
                "BEGIN\n  RETURN price * quantity;\nEND;",
                "numeric",
                False,  # is_aggregate
                False,  # is_window
                False,  # security_definer
            )
        ]
        result = decode_postgres_routine_rows(rows)
        assert len(result) == 1
        assert result[0].routine_name == "calculate_total"
        assert result[0].routine_type == "FUNCTION"
        assert result[0].routine_owner == "app_user"
        assert not result[0].is_aggregate
        assert not result[0].is_window

    def test_decode_postgres_routine_rows_aggregate_function(self) -> None:
        rows = [
            (
                "my_agg",
                "AGGREGATE",
                "postgres",
                "definition",
                "text",
                True,  # is_aggregate
                False,
                False,
            )
        ]
        result = decode_postgres_routine_rows(rows)
        assert result[0].is_aggregate

    def test_decode_postgres_routine_rows_handles_partial_rows(self) -> None:
        rows = [
            ("func1", "FUNCTION"),  # Fila incompleta - será filtrada (< 5 elementos)
            ("func2", "PROCEDURE", "owner", "def", "text", False, False, False),  # Completa
        ]
        result = decode_postgres_routine_rows(rows)
        # Solo la fila completa debe ser decodificada
        assert len(result) == 1
        assert result[0].routine_name == "func2"

    def test_decode_postgres_routine_rows_filters_empty_names(self) -> None:
        rows = [
            ("", "FUNCTION", "", "", "", False, False, False),
            ("valid_func", "FUNCTION", "owner", "def", "text", False, False, False),
        ]
        result = decode_postgres_routine_rows(rows)
        assert len(result) == 1
        assert result[0].routine_name == "valid_func"


class TestParameterDecoding:
    """Tests para decodificación de parámetros."""

    def test_decode_postgres_parameter_rows_empty(self) -> None:
        rows: list = []
        result = decode_postgres_parameter_rows(rows)
        assert result == []

    def test_decode_postgres_parameter_rows_single_parameter(self) -> None:
        rows = [
            (1, "IN", "user_id", "integer", None)  # ordinal, mode, name, data_type, default
        ]
        result = decode_postgres_parameter_rows(rows)
        assert len(result) == 1
        assert result[0].mode == "IN"
        assert result[0].name == "user_id"
        assert result[0].data_type == "integer"
        assert result[0].ordinal_position == 1

    def test_decode_postgres_parameter_rows_multiple_modes(self) -> None:
        rows = [
            (1, "IN", "input_val", "text", None),
            (2, "OUT", "result_val", "text", None),
            (3, "INOUT", "io_val", "integer", "10"),
        ]
        result = decode_postgres_parameter_rows(rows)
        assert len(result) == 3
        assert result[0].mode == "IN"
        assert result[1].mode == "OUT"
        assert result[2].mode == "INOUT"
        assert result[2].default_value == "10"

    def test_decode_postgres_parameter_rows_with_defaults(self) -> None:
        rows = [
            (1, "IN", "limit_val", "integer", "100"),
            (2, "IN", "offset_val", "integer", "0"),
        ]
        result = decode_postgres_parameter_rows(rows)
        assert result[0].default_value == "100"
        assert result[1].default_value == "0"


class TestParameterFiltering:
    """Tests para filtrado de parámetros."""

    def test_filter_postgres_routine_parameter_entries_by_routine(self) -> None:
        params = [
            PgParameterDetail("IN", "user_id", "get_user", "FUNCTION", "integer", 1),
            PgParameterDetail("IN", "limit_val", "list_users", "FUNCTION", "integer", 1),
            PgParameterDetail("OUT", "result", "get_user", "FUNCTION", "text", 2),
        ]
        filtered = filter_postgres_routine_parameter_entries(params, routine_name="get_user", routine_type="FUNCTION")
        assert len(filtered) == 2
        assert all(p.routine_name == "get_user" for p in filtered)

    def test_filter_postgres_routine_parameter_entries_case_insensitive(self) -> None:
        params = [
            PgParameterDetail("IN", "id", "GetUser", "Function", "integer", 1),
        ]
        filtered = filter_postgres_routine_parameter_entries(params, routine_name="getuser", routine_type="function")
        assert len(filtered) == 1

    def test_filter_postgres_routine_parameter_entries_empty_result(self) -> None:
        params = [
            PgParameterDetail("IN", "id", "other_func", "FUNCTION", "integer", 1),
        ]
        filtered = filter_postgres_routine_parameter_entries(params, routine_name="get_user", routine_type="FUNCTION")
        assert len(filtered) == 0


class TestParameterPublicRows:
    """Tests para conversión a filas públicas."""

    def test_build_public_postgres_routine_parameter_entry_rows_empty(self) -> None:
        entries: list[PgParameterDetail] = []
        rows = build_public_postgres_routine_parameter_entry_rows(entries)
        assert rows == []

    def test_build_public_postgres_routine_parameter_entry_rows_single(self) -> None:
        entries = [PgParameterDetail("IN", "user_id", "get_user", "FUNCTION", "integer", 1)]
        rows = build_public_postgres_routine_parameter_entry_rows(entries)
        assert len(rows) == 1
        assert rows[0] == ("IN", "user_id", "integer", None, 1)

    def test_build_public_postgres_routine_parameter_entry_rows_multiple_ordered_by_position(
        self,
    ) -> None:
        entries = [
            PgParameterDetail("IN", "p2", "func", "FUNCTION", "text", 2),
            PgParameterDetail("IN", "p1", "func", "FUNCTION", "integer", 1),
            PgParameterDetail("OUT", "result", "func", "FUNCTION", "text", 3),
        ]
        rows = build_public_postgres_routine_parameter_entry_rows(entries)
        # Deben estar ordenadas por ordinal_position
        assert rows[0][4] == 1  # p1
        assert rows[1][4] == 2  # p2
        assert rows[2][4] == 3  # result


class TestRoutineEntriesToRows:
    """Tests para conversión de rutinas a filas públicas."""

    def test_routine_entries_to_rows_empty(self) -> None:
        entries: list[PgRoutineDetail] = []
        rows = routine_entries_to_rows(entries)
        assert rows == []

    def test_routine_entries_to_rows_single_function(self) -> None:
        entries = [PgRoutineDetail("calculate_total", "FUNCTION", "app_user", "definition", "numeric")]
        rows = routine_entries_to_rows(entries)
        assert len(rows) == 1
        assert rows[0] == ("calculate_total", "FUNCTION", "app_user")

    def test_routine_entries_to_rows_multiple_sorted(self) -> None:
        entries = [
            PgRoutineDetail("z_func", "PROCEDURE", "owner1", "def", "void"),
            PgRoutineDetail("a_func", "FUNCTION", "owner2", "def", "text"),
            PgRoutineDetail("m_func", "FUNCTION", "owner3", "def", "text"),
        ]
        rows = routine_entries_to_rows(entries)
        # Deben estar ordenadas por tipo y luego por nombre
        assert rows[0][0] == "a_func"  # FUNCTION primero
        assert rows[1][0] == "m_func"

    def test_routine_entries_to_rows_filters_empty_names(self) -> None:
        entries = [
            PgRoutineDetail("", "FUNCTION", "owner", "def", "text"),
            PgRoutineDetail("valid", "FUNCTION", "owner", "def", "text"),
        ]
        rows = routine_entries_to_rows(entries)
        assert len(rows) == 1
        assert rows[0][0] == "valid"


class TestRoutineDDLBuilder:
    """Tests para construcción de DDL de rutinas."""

    def test_build_postgres_routine_ddl_function_minimal(self) -> None:
        ddl = build_postgres_routine_ddl(
            schema="public",
            routine_name="my_func",
            routine_type="FUNCTION",
            routine_definition="RETURN 42;",
        )
        assert isinstance(ddl, str)
        assert "RETURN 42;" in ddl

    def test_build_postgres_routine_ddl_with_owner(self) -> None:
        ddl = build_postgres_routine_ddl(
            schema="public",
            routine_name="my_func",
            routine_type="FUNCTION",
            routine_definition="RETURN 42;",
            routine_owner="app_user",
        )
        assert "Owner: app_user" in ddl or "app_user" in ddl

    def test_build_postgres_routine_ddl_security_definer(self) -> None:
        ddl = build_postgres_routine_ddl(
            schema="public",
            routine_name="secure_func",
            routine_type="FUNCTION",
            routine_definition="RETURN 42;",
            security_definer=True,
        )
        assert "SECURITY" in ddl or "DEFINER" in ddl

    def test_build_postgres_routine_ddl_aggregate_flag(self) -> None:
        ddl = build_postgres_routine_ddl(
            schema="public",
            routine_name="my_agg",
            routine_type="AGGREGATE",
            routine_definition="definition",
            is_aggregate=True,
        )
        assert "AGGREGATE" in ddl

    def test_build_postgres_routine_ddl_no_definition_fallback(self) -> None:
        ddl = build_postgres_routine_ddl(
            schema="public",
            routine_name="missing_func",
            routine_type="FUNCTION",
            routine_definition="",
        )
        assert "unavailable" in ddl.lower() or "definition" in ddl.lower()


class TestRoutineModels:
    """Tests para modelos de rutinas."""

    def test_pg_routine_detail_matches_same_name_and_type(self) -> None:
        routine = PgRoutineDetail("calc", "FUNCTION", "owner", "def", "numeric")
        assert routine.matches(routine_name="calc", routine_type="FUNCTION")

    def test_pg_routine_detail_matches_case_insensitive(self) -> None:
        routine = PgRoutineDetail("Calc", "Function", "owner", "def", "numeric")
        assert routine.matches(routine_name="CALC", routine_type="function")

    def test_pg_routine_detail_to_dict(self) -> None:
        routine = PgRoutineDetail("calc", "FUNCTION", "owner", "def", "numeric")
        d = routine.to_dict()
        assert d["routine_name"] == "calc"
        assert d["routine_type"] == "FUNCTION"
        assert d["routine_owner"] == "owner"

    def test_pg_parameter_detail_matches(self) -> None:
        param = PgParameterDetail("IN", "id", "get_user", "FUNCTION", "integer", 1)
        assert param.matches(routine_name="get_user", routine_type="FUNCTION")

    def test_pg_parameter_detail_to_public_row(self) -> None:
        param = PgParameterDetail("IN", "id", "get_user", "FUNCTION", "integer", 1, "10")
        row = param.to_public_row()
        assert row == ("IN", "id", "integer", "10", 1)

    def test_pg_parameter_detail_to_dict(self) -> None:
        param = PgParameterDetail("OUT", "result", "func", "PROCEDURE", "text", 1, None)
        d = param.to_dict()
        assert d["mode"] == "OUT"
        assert d["name"] == "result"
        assert d["routine_name"] == "func"
        assert d["ordinal_position"] == 1
