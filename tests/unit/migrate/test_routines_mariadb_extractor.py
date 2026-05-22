"""Tests para extract_routines() del extractor MariaDB."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.migrate.extractors.mariadb import MariaDBSchemaExtractor


def _extractor(routine_rows: list[tuple]) -> MariaDBSchemaExtractor:
    manager = MagicMock()
    manager.execute_custom_many.return_value = iter(routine_rows)
    return MariaDBSchemaExtractor(manager)


class TestMariaDBExtractRoutines:
    def test_empty_returns_empty(self) -> None:
        ext = _extractor([])
        assert ext.extract_routines("db1") == []

    def test_procedure_with_body(self) -> None:
        rows = [("SP_TEST", "PROCEDURE", "db1", "BEGIN\n  SELECT 1;\nEND", None)]
        ext = _extractor(rows)
        result = ext.extract_routines("db1")
        assert len(result) == 1
        r = result[0]
        assert r.name == "SP_TEST"
        assert r.routine_type == "PROCEDURE"
        assert "SELECT 1" in r.body
        assert r.warnings == []

    def test_function_with_return_type(self) -> None:
        rows = [("FN_CALC", "FUNCTION", "db1", "BEGIN\n  RETURN 42;\nEND", "INT")]
        ext = _extractor(rows)
        result = ext.extract_routines("db1")
        assert result[0].return_type == "INT"
        assert result[0].routine_type == "FUNCTION"

    def test_no_body_emits_warning(self) -> None:
        rows = [("SP_EMPTY", "PROCEDURE", "db1", None, None)]
        ext = _extractor(rows)
        result = ext.extract_routines("db1")
        assert result[0].body == ""
        assert len(result[0].warnings) == 1

    def test_unknown_type_skipped(self) -> None:
        rows = [("EV_DAILY", "EVENT", "db1", "DO SOMETHING", None)]
        ext = _extractor(rows)
        assert ext.extract_routines("db1") == []

    def test_short_row_skipped(self) -> None:
        rows = [("SP_BAD",)]
        ext = _extractor(rows)
        assert ext.extract_routines("db1") == []
