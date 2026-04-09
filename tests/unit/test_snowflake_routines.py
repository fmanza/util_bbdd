"""Tests para introspección de routines (UDFs, procedures) en Snowflake."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from util_bbdd.metadata.snowflake._snowflake_models import SnowflakeRoutineDetail
from util_bbdd.metadata.snowflake.routines import fetch_routine_parameters_sync, fetch_routines_sync


class TestFetchRoutinesSync:
    """Tests para fetch_routines_sync()."""

    def test_fetch_routines_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("CALCULATE_TOTAL", "FUNCTION", datetime(2024, 1, 1, 12, 0), "SELECT 1", "SQL"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_fetch_routines_returns_routine_detail_objects(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("CALCULATE_TOTAL", "FUNCTION", datetime(2024, 1, 1), "SELECT 1", "SQL"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        assert isinstance(result[0], SnowflakeRoutineDetail)

    def test_fetch_routines_includes_routine_name(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("MY_FUNCTION", "FUNCTION", datetime(2024, 1, 1), "SELECT 1", "SQL"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        assert result[0].routine_name == "MY_FUNCTION"

    def test_fetch_routines_includes_routine_type(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("MY_FUNCTION", "function", datetime(2024, 1, 1), "SELECT 1", "SQL"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        # Type should be normalized to uppercase
        assert result[0].routine_type == "FUNCTION"

    def test_fetch_routines_includes_procedure_type(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("MY_PROCEDURE", "PROCEDURE", datetime(2024, 1, 1), None, "SQL"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        assert result[0].routine_type == "PROCEDURE"

    def test_fetch_routines_includes_created_datetime(self) -> None:
        created = datetime(2024, 3, 15, 10, 30, 45)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("MY_FUNCTION", "FUNCTION", created, "SELECT 1", "SQL"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        assert result[0].created_datetime == created

    def test_fetch_routines_includes_language(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("MY_FUNCTION", "FUNCTION", datetime(2024, 1, 1), "SELECT 1", "JAVASCRIPT"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        assert result[0].language == "JAVASCRIPT"

    def test_fetch_routines_multiple_routines(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("FUNC1", "FUNCTION", datetime(2024, 1, 1), "SELECT 1", "SQL"),
            ("PROC1", "PROCEDURE", datetime(2024, 1, 2), None, "SQL"),
            ("FUNC_JS", "FUNCTION", datetime(2024, 1, 3), "return 1;", "JAVASCRIPT"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        assert len(result) == 3

    def test_fetch_routines_empty_database(self) -> None:
        result = fetch_routines_sync(MagicMock(), None, "PUBLIC")
        assert result == []

    def test_fetch_routines_empty_schema(self) -> None:
        result = fetch_routines_sync(MagicMock(), "MYDB", None)
        assert result == []

    def test_fetch_routines_system_schema_excluded(self) -> None:
        result = fetch_routines_sync(MagicMock(), "MYDB", "INFORMATION_SCHEMA")
        assert result == []

    def test_fetch_routines_connection_error_returns_empty(self) -> None:
        """If query fails (e.g., older Snowflake version), return empty list."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Query not supported")

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        assert result == []

    def test_fetch_routines_handles_datetime_string(self) -> None:
        """Should handle datetime returned as string."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # datetime as ISO string from some drivers
        mock_cursor.fetchall.return_value = [
            ("MY_FUNCTION", "FUNCTION", "2024-01-15T10:30:45", "SELECT 1", "SQL"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        assert result[0].created_datetime == datetime(2024, 1, 15, 10, 30, 45)

    def test_fetch_routines_handles_missing_language(self) -> None:
        """If language is not provided, default to SQL."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("MY_FUNCTION", "FUNCTION", datetime(2024, 1, 1), "SELECT 1", None),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "MYDB", "PUBLIC")
        assert result[0].language == "SQL"


class TestFetchRoutineParametersSync:
    """Tests para fetch_routine_parameters_sync()."""

    def test_fetch_routine_parameters_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_ID", "IN", "NUMBER", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "MYDB", "PUBLIC", "MY_FUNCTION")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_fetch_routine_parameters_returns_tuples_with_4_elements(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_ID", "IN", "NUMBER", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "MYDB", "PUBLIC", "MY_FUNCTION")
        assert len(result[0]) == 4

    def test_fetch_routine_parameters_includes_name(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_ID", "IN", "NUMBER", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "MYDB", "PUBLIC", "MY_FUNCTION")
        assert result[0][0] == "P_ID"

    def test_fetch_routine_parameters_includes_mode(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_ID", "IN", "NUMBER", 1),
            ("P_RESULT", "OUT", "VARCHAR", 2),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "MYDB", "PUBLIC", "MY_PROCEDURE")
        assert result[0][1] == "IN"
        assert result[1][1] == "OUT"

    def test_fetch_routine_parameters_includes_data_type(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_ID", "IN", "NUMBER", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "MYDB", "PUBLIC", "MY_FUNCTION")
        assert result[0][2] == "NUMBER"

    def test_fetch_routine_parameters_includes_ordinal(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_ID", "IN", "NUMBER", 1),
            ("P_NAME", "IN", "VARCHAR", 2),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "MYDB", "PUBLIC", "MY_FUNCTION")
        assert result[0][3] == 1
        assert result[1][3] == 2

    def test_fetch_routine_parameters_multiple_parameters(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_ID", "IN", "NUMBER", 1),
            ("P_NAME", "IN", "VARCHAR", 2),
            ("P_RESULT", "OUT", "VARCHAR", 3),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "MYDB", "PUBLIC", "MY_PROCEDURE")
        assert len(result) == 3

    def test_fetch_routine_parameters_sorted_by_ordinal(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_NAME", "IN", "VARCHAR", 2),
            ("P_ID", "IN", "NUMBER", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "MYDB", "PUBLIC", "MY_FUNCTION")
        # Should be sorted by ordinal position
        assert result[0][3] == 1
        assert result[1][3] == 2

    def test_fetch_routine_parameters_empty_database(self) -> None:
        result = fetch_routine_parameters_sync(MagicMock(), None, "PUBLIC", "MY_FUNCTION")
        assert result == []

    def test_fetch_routine_parameters_empty_schema(self) -> None:
        result = fetch_routine_parameters_sync(MagicMock(), "MYDB", None, "MY_FUNCTION")
        assert result == []

    def test_fetch_routine_parameters_empty_routine_name(self) -> None:
        result = fetch_routine_parameters_sync(MagicMock(), "MYDB", "PUBLIC", None)
        assert result == []

    def test_fetch_routine_parameters_system_schema_excluded(self) -> None:
        result = fetch_routine_parameters_sync(MagicMock(), "MYDB", "INFORMATION_SCHEMA", "MY_FUNCTION")
        assert result == []

    def test_fetch_routine_parameters_connection_error_returns_empty(self) -> None:
        """If query fails, return empty list."""
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Query not supported")

        result = fetch_routine_parameters_sync(mock_conn, "MYDB", "PUBLIC", "MY_FUNCTION")
        assert result == []

    def test_fetch_routine_parameters_variant_type(self) -> None:
        """Test handling of VARIANT type (semi-structured data parameter)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("P_DATA", "IN", "VARIANT", 1),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routine_parameters_sync(mock_conn, "MYDB", "PUBLIC", "MY_FUNCTION")
        assert result[0][2] == "VARIANT"
