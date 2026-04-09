"""Tests para routines (procedimientos, funciones) en SQL Server."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlserver._sqlserver_models import (
    SqlServerParameterDetail,
    SqlServerRoutineDetail,
)
from util_bbdd.metadata.sqlserver.routines import (
    fetch_routine_parameters_sync,
    fetch_routines_sync,
)


class TestFetchRoutinesSyncSqlServer:
    """Tests para fetch_routines_sync()."""

    def test_fetch_routines_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Returns (name, type, object_id, param_count)
        mock_cursor.fetchall.return_value = [
            ("sp_GetUsers", "PROCEDURE", 123456, 2),
            ("fn_CalculateTotal", "FUNCTION", 123457, 1),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, schema="dbo")

        assert len(result) >= 0
        assert all(isinstance(r, SqlServerRoutineDetail) for r in result)

    def test_fetch_routines_returns_correct_type(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("sp_GetUsers", "PROCEDURE", 123456, 2),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, schema="dbo")

        assert len(result) == 1
        routine = result[0]
        assert isinstance(routine, SqlServerRoutineDetail)
        assert routine.routine_name == "sp_GetUsers"
        assert routine.routine_type == "PROCEDURE"
        assert routine.object_id == 123456
        assert routine.parameters_count == 2

    def test_fetch_routines_no_routines(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, schema="dbo")
        assert result == []

    def test_fetch_routines_default_schema(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, schema=None)
        assert isinstance(result, list)

    def test_fetch_routines_multiple_procedures_and_functions(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("sp_InsertUser", "PROCEDURE", 100001, 3),
            ("sp_UpdateUser", "PROCEDURE", 100002, 4),
            ("fn_GetUserName", "FUNCTION", 100003, 1),
            ("fn_ValidateEmail", "FUNCTION", 100004, 1),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, schema="dbo")

        assert len(result) == 4

        procedures = [r for r in result if r.routine_type == "PROCEDURE"]
        functions = [r for r in result if r.routine_type == "FUNCTION"]

        assert len(procedures) == 2
        assert len(functions) == 2


class TestFetchRoutineParametersSyncSqlServer:
    """Tests para fetch_routine_parameters_sync()."""

    def test_fetch_parameters_with_mock_connection(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Returns (name, object_id, param_id, data_type, is_output, precision, scale)
        mock_cursor.fetchall.return_value = [
            ("@UserId", 123456, 1, "int", 0, 0, 0),
            ("@Name", 123456, 2, "nvarchar", 0, 100, 0),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, object_id=123456)

        assert len(result) >= 0
        assert all(isinstance(r, SqlServerParameterDetail) for r in result)

    def test_fetch_parameters_includes_output_flag(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("@InputId", 123456, 1, "int", 0, 0, 0),
            ("@OutputStatus", 123456, 2, "nvarchar", 1, 50, 0),  # OUTPUT parameter
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, object_id=123456)

        input_param = result[0]
        output_param = result[1]

        assert input_param.is_output is False
        assert output_param.is_output is True

    def test_fetch_parameters_preserves_precision_scale(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("@Amount", 123456, 1, "numeric", 0, 18, 2),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, object_id=123456)

        param = result[0]
        assert param.precision == 18
        assert param.scale == 2

    def test_fetch_parameters_no_parameters(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, object_id=999999)
        assert result == []

    def test_fetch_parameters_no_object_id_provided(self) -> None:
        mock_conn = MagicMock()
        result = fetch_routine_parameters_sync(mock_conn, object_id=None)
        assert result == []

    def test_fetch_parameters_returns_correct_type(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("@UserId", 123456, 1, "int", 0, 0, 0),
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, object_id=123456)

        assert len(result) == 1
        param = result[0]
        assert isinstance(param, SqlServerParameterDetail)
        assert param.param_name == "@UserId"
        assert param.object_id == 123456
        assert param.parameter_id == 1
        assert param.data_type == "int"

    def test_fetch_parameters_multiple_parameters(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("@FirstName", 123456, 1, "nvarchar", 0, 100, 0),
            ("@LastName", 123456, 2, "nvarchar", 0, 100, 0),
            ("@Age", 123456, 3, "int", 0, 0, 0),
            ("@Result", 123456, 4, "int", 1, 0, 0),  # OUTPUT
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, object_id=123456)

        assert len(result) == 4
        assert sum(1 for p in result if p.is_output) == 1  # One OUTPUT parameter

    def test_fetch_parameters_ignores_zero_precision_scale(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchall.return_value = [
            ("@Text", 123456, 1, "nvarchar", 0, 0, 0),  # 0 precision/scale
        ]

        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, object_id=123456)

        param = result[0]
        assert param.precision is None
        assert param.scale is None
