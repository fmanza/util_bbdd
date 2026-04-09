"""Tests para módulo Redshift: routines (UDFs).

Redshift soporta principalmente funciones UDF (User Defined Functions).
Soporte limitado para procedimientos en ciertos versiones.
Introspección de parámetros es limitada.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from util_bbdd.metadata.redshift.routines import (
    fetch_routine_parameters_sync,
    fetch_routines_sync,
)


class TestFetchRoutinesSync:
    """Tests para fetch_routines_sync()."""

    def test_fetch_routines_requires_schema(self) -> None:
        mock_conn = MagicMock()

        result = fetch_routines_sync(mock_conn, None)
        assert result == []

    def test_fetch_routines_rejects_system_schema(self) -> None:
        """Debe rechazar schemas del sistema."""
        mock_conn = MagicMock()

        result = fetch_routines_sync(mock_conn, "pg_catalog")
        assert result == []

    def test_fetch_routines_returns_list(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert isinstance(result, list)

    def test_fetch_routines_returns_details(self) -> None:
        """Debe retornar RedshiftRoutineDetail."""
        from util_bbdd.metadata.redshift._redshift_models import RedshiftRoutineDetail

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        created_dt = datetime(2024, 1, 1, 12, 0, 0)
        mock_cursor.fetchall.return_value = [
            ("my_function", "FUNCTION", created_dt, "myschema"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert len(result) == 1
        assert isinstance(result[0], RedshiftRoutineDetail)

    def test_fetch_routines_extracts_fields(self) -> None:
        """Extrae nombre, tipo y fecha de creación."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        created_dt = datetime(2024, 1, 1, 12, 0, 0)
        mock_cursor.fetchall.return_value = [
            ("my_function", "FUNCTION", created_dt, "myschema"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert result[0].routine_name == "my_function"
        assert result[0].routine_type == "FUNCTION"
        assert result[0].created_datetime == created_dt

    def test_fetch_routines_handles_none_created_datetime(self) -> None:
        """Debe manejar casos donde created no se obtiene."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("my_function", "FUNCTION", None, "myschema"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert result[0].routine_name == "my_function"
        assert result[0].created_datetime is None

    def test_fetch_routines_parses_datetime_string(self) -> None:
        """Debe parsear datetime como string si es necesario."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        dt_str = "2024-01-01T12:00:00"
        mock_cursor.fetchall.return_value = [
            ("my_function", "FUNCTION", dt_str, "myschema"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert result[0].routine_name == "my_function"
        assert isinstance(result[0].created_datetime, datetime)

    def test_fetch_routines_multiple_functions(self) -> None:
        """Redshift puede tener múltiples UDFs en un schema."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        created_dt = datetime(2024, 1, 1, 12, 0, 0)
        mock_cursor.fetchall.return_value = [
            ("my_function", "FUNCTION", created_dt, "myschema"),
            ("another_function", "FUNCTION", created_dt, "myschema"),
            ("my_procedure", "PROCEDURE", created_dt, "myschema"),
        ]
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert len(result) == 3

    def test_fetch_routines_handles_empty_result(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        result = fetch_routines_sync(mock_conn, "myschema")
        assert result == []


class TestFetchRoutineParametersSync:
    """Tests para fetch_routine_parameters_sync().

    Nota: Redshift tiene soporte limitado para introspección de parámetros.
    """

    def test_fetch_routine_parameters_requires_schema_and_routine(self) -> None:
        mock_conn = MagicMock()

        result = fetch_routine_parameters_sync(mock_conn, None, None)
        assert result == []

        result = fetch_routine_parameters_sync(mock_conn, "myschema", None)
        assert result == []

        result = fetch_routine_parameters_sync(mock_conn, None, "my_function")
        assert result == []

    def test_fetch_routine_parameters_rejects_system_schema(self) -> None:
        """Debe rechazar schemas del sistema."""
        mock_conn = MagicMock()

        result = fetch_routine_parameters_sync(mock_conn, "pg_catalog", "my_function")
        assert result == []

    def test_fetch_routine_parameters_returns_empty_list(self) -> None:
        """Redshift tiene soporte limitado - por ahora retorna lista vacía."""
        mock_conn = MagicMock()

        result = fetch_routine_parameters_sync(mock_conn, "myschema", "my_function")
        # Redshift no expone parámetros via information_schema
        assert result == []

    def test_fetch_routine_parameters_note_limitation(self) -> None:
        """Documentar limitación de Redshift respecto a parámetros."""
        # Redshift no proporciona un mecanismo standar SQL para introspeccionar
        # parámetros de UDFs. Sería necesario parser de DDL.
        mock_conn = MagicMock()
        result = fetch_routine_parameters_sync(mock_conn, "myschema", "my_function")
        assert isinstance(result, list)
        assert len(result) == 0
