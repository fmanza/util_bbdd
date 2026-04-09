"""Tests para rutinas (procedures/functions) Oracle."""

from __future__ import annotations

from util_bbdd.metadata.oracle._oracle_models import OracleParameterDetail, OracleRoutineDetail
from util_bbdd.metadata.oracle.routines import (
    decode_oracle_routine_parameter_rows,
    filter_routine_parameters,
    parameter_rows_to_public_format,
    routine_rows_to_public_format,
)


class TestOracleRoutineDetail:
    """Tests para OracleRoutineDetail model."""

    def test_routine_detail_creation(self) -> None:
        routine = OracleRoutineDetail(
            routine_name="get_user",
            routine_type="FUNCTION",
            routine_owner="MYAPP",
            object_id=12345,
        )
        assert routine.routine_name == "get_user"
        assert routine.routine_type == "FUNCTION"
        assert routine.routine_owner == "MYAPP"

    def test_routine_detail_matches(self) -> None:
        routine = OracleRoutineDetail(
            routine_name="get_user",
            routine_type="FUNCTION",
            routine_owner="MYAPP",
        )
        assert routine.matches(routine_name="get_user", routine_type="FUNCTION") is True
        assert routine.matches(routine_name="get_user", routine_type="PROCEDURE") is False

    def test_routine_detail_matches_case_insensitive(self) -> None:
        routine = OracleRoutineDetail(
            routine_name="GET_USER",
            routine_type="FUNCTION",
            routine_owner="MYAPP",
        )
        assert routine.matches(routine_name="get_user", routine_type="function") is True

    def test_routine_detail_to_dict(self) -> None:
        routine = OracleRoutineDetail(
            routine_name="get_user",
            routine_type="FUNCTION",
            routine_owner="MYAPP",
            object_id=12345,
        )
        result = routine.to_dict()
        assert result["routine_name"] == "get_user"
        assert result["routine_type"] == "FUNCTION"
        assert result["object_id"] == 12345


class TestOracleParameterDetail:
    """Tests para OracleParameterDetail model."""

    def test_parameter_detail_creation(self) -> None:
        param = OracleParameterDetail(
            param_name="p_user_id",
            routine_name="get_user",
            routine_type="FUNCTION",
            routine_owner="MYAPP",
            in_out="IN",
            data_type="NUMBER",
            data_precision=10,
            data_scale=0,
        )
        assert param.param_name == "p_user_id"
        assert param.in_out == "IN"
        assert param.data_type == "NUMBER"

    def test_parameter_detail_matches(self) -> None:
        param = OracleParameterDetail(
            param_name="p_user_id",
            routine_name="get_user",
            routine_type="FUNCTION",
            routine_owner="MYAPP",
            in_out="IN",
            data_type="NUMBER",
        )
        assert param.matches(routine_name="get_user", routine_type="FUNCTION") is True
        assert param.matches(routine_name="get_user", routine_type="PROCEDURE") is False

    def test_parameter_detail_to_public_row(self) -> None:
        param = OracleParameterDetail(
            param_name="p_user_id",
            routine_name="get_user",
            routine_type="FUNCTION",
            routine_owner="MYAPP",
            in_out="IN",
            data_type="NUMBER",
            ordinal_position=1,
        )
        row = param.to_public_row()
        assert row[0] == "IN"
        assert row[1] == "p_user_id"
        assert row[2] == "NUMBER"
        assert row[3] == 1

    def test_parameter_detail_to_dict(self) -> None:
        param = OracleParameterDetail(
            param_name="p_user_id",
            routine_name="get_user",
            routine_type="FUNCTION",
            routine_owner="MYAPP",
            in_out="IN",
            data_type="NUMBER",
        )
        result = param.to_dict()
        assert result["param_name"] == "p_user_id"
        assert result["in_out"] == "IN"


class TestDecodeRoutineParameterRows:
    """Tests para decode_oracle_routine_parameter_rows()."""

    def test_decode_empty_rows(self) -> None:
        result = decode_oracle_routine_parameter_rows("get_user", "FUNCTION", [])
        assert result == []

    def test_decode_single_in_parameter(self) -> None:
        rows = [
            ("p_user_id", 1, "IN", "NUMBER", 10, 0, None, 12345, 1),
        ]
        result = decode_oracle_routine_parameter_rows("get_user", "FUNCTION", rows)
        assert len(result) == 1
        assert result[0].param_name == "p_user_id"
        assert result[0].in_out == "IN"

    def test_decode_out_parameter(self) -> None:
        rows = [
            ("p_result", 1, "OUT", "VARCHAR2", 100, None, None, 12345, 1),
        ]
        result = decode_oracle_routine_parameter_rows("get_user", "FUNCTION", rows)
        assert result[0].in_out == "OUT"

    def test_decode_inout_parameter(self) -> None:
        rows = [
            ("p_status", 1, "INOUT", "VARCHAR2", 10, None, None, 12345, 1),
        ]
        result = decode_oracle_routine_parameter_rows("get_user", "FUNCTION", rows)
        assert result[0].in_out == "INOUT"

    def test_decode_multiple_parameters(self) -> None:
        rows = [
            ("p_user_id", 1, "IN", "NUMBER", 10, 0, None, 12345, 1),
            ("p_dept_id", 2, "IN", "NUMBER", 10, 0, None, 12345, 2),
            ("p_result", 3, "OUT", "VARCHAR2", 100, None, None, 12345, 3),
        ]
        result = decode_oracle_routine_parameter_rows("get_user_dept", "FUNCTION", rows)
        assert len(result) == 3
        assert result[0].ordinal_position == 1
        assert result[1].ordinal_position == 2
        assert result[2].ordinal_position == 3

    def test_decode_parameter_with_precision_scale(self) -> None:
        rows = [
            ("p_price", 1, "IN", "NUMBER", None, 10, 2, 12345, 1),
        ]
        result = decode_oracle_routine_parameter_rows("calc_price", "FUNCTION", rows)
        assert result[0].data_precision == 10
        assert result[0].data_scale == 2

    def test_decode_skips_null_names(self) -> None:
        rows = [
            (None, 1, "IN", "NUMBER", 10, 0, None, 12345, 1),
            ("p_valid", 2, "IN", "VARCHAR2", 100, None, None, 12345, 2),
        ]
        result = decode_oracle_routine_parameter_rows("test_func", "FUNCTION", rows)
        assert len(result) == 1


class TestFilterRoutineParameters:
    """Tests para filter_routine_parameters()."""

    def test_filter_empty_list(self) -> None:
        result = filter_routine_parameters([], "get_user", "FUNCTION")
        assert result == []

    def test_filter_single_match(self) -> None:
        params = [
            OracleParameterDetail(
                param_name="p_id",
                routine_name="get_user",
                routine_type="FUNCTION",
                routine_owner="MYAPP",
                in_out="IN",
                data_type="NUMBER",
            ),
        ]
        result = filter_routine_parameters(params, "get_user", "FUNCTION")
        assert len(result) == 1

    def test_filter_multiple_routines(self) -> None:
        params = [
            OracleParameterDetail(
                param_name="p_id",
                routine_name="get_user",
                routine_type="FUNCTION",
                routine_owner="MYAPP",
                in_out="IN",
                data_type="NUMBER",
            ),
            OracleParameterDetail(
                param_name="p_name",
                routine_name="insert_user",
                routine_type="PROCEDURE",
                routine_owner="MYAPP",
                in_out="IN",
                data_type="VARCHAR2",
            ),
        ]
        result = filter_routine_parameters(params, "get_user", "FUNCTION")
        assert len(result) == 1
        assert result[0].routine_name == "get_user"

    def test_filter_case_insensitive(self) -> None:
        params = [
            OracleParameterDetail(
                param_name="p_id",
                routine_name="GET_USER",
                routine_type="FUNCTION",
                routine_owner="MYAPP",
                in_out="IN",
                data_type="NUMBER",
            ),
        ]
        result = filter_routine_parameters(params, "get_user", "function")
        assert len(result) == 1


class TestRoutineRowsToPublicFormat:
    """Tests para routine_rows_to_public_format()."""

    def test_empty_routines(self) -> None:
        result = routine_rows_to_public_format([])
        assert result == []

    def test_single_routine(self) -> None:
        routines = [
            OracleRoutineDetail(
                routine_name="get_user",
                routine_type="FUNCTION",
                routine_owner="MYAPP",
            ),
        ]
        result = routine_rows_to_public_format(routines)
        assert len(result) == 1
        assert result[0] == ("get_user", "FUNCTION", "MYAPP")

    def test_multiple_routines(self) -> None:
        routines = [
            OracleRoutineDetail(
                routine_name="get_user",
                routine_type="FUNCTION",
                routine_owner="MYAPP",
            ),
            OracleRoutineDetail(
                routine_name="insert_user",
                routine_type="PROCEDURE",
                routine_owner="MYAPP",
            ),
        ]
        result = routine_rows_to_public_format(routines)
        assert len(result) == 2
        assert result[0][0] == "get_user"
        assert result[1][0] == "insert_user"


class TestParameterRowsToPublicFormat:
    """Tests para parameter_rows_to_public_format()."""

    def test_empty_parameters(self) -> None:
        result = parameter_rows_to_public_format([])
        assert result == []

    def test_single_parameter(self) -> None:
        params = [
            OracleParameterDetail(
                param_name="p_id",
                routine_name="get_user",
                routine_type="FUNCTION",
                routine_owner="MYAPP",
                in_out="IN",
                data_type="NUMBER",
                ordinal_position=1,
            ),
        ]
        result = parameter_rows_to_public_format(params)
        assert len(result) == 1
        assert result[0] == ("IN", "p_id", "NUMBER", 1)

    def test_multiple_parameters(self) -> None:
        params = [
            OracleParameterDetail(
                param_name="p_id",
                routine_name="get_user",
                routine_type="FUNCTION",
                routine_owner="MYAPP",
                in_out="IN",
                data_type="NUMBER",
                ordinal_position=1,
            ),
            OracleParameterDetail(
                param_name="p_result",
                routine_name="get_user",
                routine_type="FUNCTION",
                routine_owner="MYAPP",
                in_out="OUT",
                data_type="VARCHAR2",
                ordinal_position=2,
            ),
        ]
        result = parameter_rows_to_public_format(params)
        assert len(result) == 2
        assert result[0][1] == "p_id"
        assert result[1][1] == "p_result"
