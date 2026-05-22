"""Tests para extract_routines() del extractor SQL Server."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from util_bbdd.metadata.sqlserver._sqlserver_models import SqlServerRoutineDetail
from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor

_ROUTINES_PATH = "util_bbdd.migrate.extractors.sqlserver.fetch_routines_sync"
_BODY_PATH = "util_bbdd.migrate.extractors.sqlserver.fetch_routine_body_sync"


def _detail(name: str, routine_type: str = "PROCEDURE") -> SqlServerRoutineDetail:
    return SqlServerRoutineDetail(
        routine_name=name,
        routine_type=routine_type,
        object_id=1001,
        parameters_count=0,
    )


class TestSQLServerExtractRoutines:
    def test_empty_returns_empty(self) -> None:
        manager = MagicMock()
        with patch(_ROUTINES_PATH, return_value=[]), patch(_BODY_PATH, return_value=""):
            ext = SQLServerSchemaExtractor(manager)
            result = ext.extract_routines("dbo")
        assert result == []

    def test_procedure_with_body(self) -> None:
        detail = _detail("SP_TEST", "PROCEDURE")
        body = "CREATE PROCEDURE dbo.SP_TEST AS BEGIN SELECT 1 END"
        manager = MagicMock()
        with patch(_ROUTINES_PATH, return_value=[detail]), patch(_BODY_PATH, return_value=body):
            ext = SQLServerSchemaExtractor(manager)
            result = ext.extract_routines("dbo")
        assert len(result) == 1
        assert result[0].name == "SP_TEST"
        assert result[0].body == body
        assert result[0].warnings == []

    def test_procedure_without_body_emits_warning(self) -> None:
        detail = _detail("SP_EMPTY")
        manager = MagicMock()
        with patch(_ROUTINES_PATH, return_value=[detail]), patch(_BODY_PATH, return_value=""):
            ext = SQLServerSchemaExtractor(manager)
            result = ext.extract_routines("dbo")
        assert result[0].body == ""
        assert len(result[0].warnings) == 1
        assert "no disponible" in result[0].warnings[0].message

    def test_multiple_routines(self) -> None:
        details = [_detail("SP_A"), _detail("FN_B", "FUNCTION")]
        manager = MagicMock()
        with (
            patch(_ROUTINES_PATH, return_value=details),
            patch(_BODY_PATH, side_effect=["CREATE PROC SP_A AS ...", "CREATE FUNCTION FN_B ..."]),
        ):
            ext = SQLServerSchemaExtractor(manager)
            result = ext.extract_routines("dbo")
        assert len(result) == 2
        assert result[0].name == "SP_A"
        assert result[1].name == "FN_B"
