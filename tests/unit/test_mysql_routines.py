"""Tests para módulo MySQL: rutinas."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from util_bbdd.metadata.mysql._mysql_models import MysqlRoutineDetail
from util_bbdd.metadata.mysql.routines import fetch_routine_parameters_sync, fetch_routines_sync


class TestFetchRoutinesSync:
    """Tests para fetch_routines_sync()."""

    def test_fetch_routines_requires_schema(self) -> None:
        mock_conn = MagicMock()

        result = fetch_routines_sync(mock_conn, None)
        assert result == []

    def test_fetch_routines_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert isinstance(result, list)

    def test_fetch_routines_returns_mysql_routine_detail(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        now = datetime.now()
        mock_cursor.fetchall.return_value = [("sp_test", "PROCEDURE", now)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert all(isinstance(r, MysqlRoutineDetail) for r in result)

    def test_fetch_routines_extracts_routine_info(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        now = datetime.now()
        mock_cursor.fetchall.return_value = [("sp_test", "PROCEDURE", now)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        routine = result[0]
        assert routine.routine_name == "sp_test"
        assert routine.routine_type == "PROCEDURE"
        assert routine.created_datetime == now

    def test_fetch_routines_function_type(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("fn_calc", "FUNCTION", None)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert result[0].routine_type == "FUNCTION"

    def test_fetch_routines_handles_null_datetime(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("sp_test", "PROCEDURE", None)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert result[0].created_datetime is None

    def test_fetch_routines_parses_datetime_from_string(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        dt_str = "2024-01-15 10:30:00"
        mock_cursor.fetchall.return_value = [("sp_test", "PROCEDURE", dt_str)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert result[0].created_datetime is not None

    def test_fetch_routines_multiple_routines(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("sp_test1", "PROCEDURE", None),
            ("sp_test2", "PROCEDURE", None),
            ("fn_calc", "FUNCTION", None),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert len(result) == 3


class TestFetchRoutineParametersSync:
    """Tests para fetch_routine_parameters_sync()."""

    def test_fetch_params_requires_schema_and_routine(self) -> None:
        mock_conn = MagicMock()

        assert fetch_routine_parameters_sync(mock_conn, None, None) == []
        assert fetch_routine_parameters_sync(mock_conn, "schema", None) == []

    def test_fetch_params_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "myschema", "sp_test")
        assert isinstance(result, list)

    def test_fetch_params_returns_tuples(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("p_id", "IN", "INT", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "myschema", "sp_test")
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_params_extracts_parameter_info(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("p_id", "IN", "INT", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "myschema", "sp_test")
        row = result[0]
        assert row[0] == "p_id"
        assert row[1] == "IN"
        assert row[2] == "INT"
        assert row[3] == 1

    def test_fetch_params_out_parameter(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("p_result", "OUT", "VARCHAR", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "myschema", "sp_test")
        assert result[0][1] == "OUT"

    def test_fetch_params_inout_parameter(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("p_value", "INOUT", "INT", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "myschema", "sp_test")
        assert result[0][1] == "INOUT"

    def test_fetch_params_multiple_parameters(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("p_id", "IN", "INT", 1),
            ("p_name", "IN", "VARCHAR", 2),
            ("p_result", "OUT", "VARCHAR", 3),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "myschema", "sp_test")
        assert len(result) == 3

    def test_fetch_params_handles_null_parameter_name(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(None, "IN", "INT", 1)]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "myschema", "sp_test")
        assert result[0][0] == ""  # Should default to empty
