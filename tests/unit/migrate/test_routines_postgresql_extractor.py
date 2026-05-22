"""Tests para extract_routines() del extractor PostgreSQL."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.migrate.extractors.postgresql import PostgreSQLSchemaExtractor


def _extractor(routine_rows: list[tuple]) -> PostgreSQLSchemaExtractor:
    manager = MagicMock()
    manager.execute_custom_many.return_value = iter(routine_rows)
    return PostgreSQLSchemaExtractor(manager)


class TestPostgreSQLExtractRoutines:
    def test_empty_returns_empty(self) -> None:
        ext = _extractor([])
        assert ext.extract_routines("public") == []

    def test_function_with_body(self) -> None:
        rows = [
            (
                "fn_hello",
                "FUNCTION",
                "owner",
                "CREATE OR REPLACE FUNCTION fn_hello() RETURNS void ...",
                "void",
                0,
                0,
                False,
            )
        ]
        ext = _extractor(rows)
        result = ext.extract_routines("public")
        assert len(result) == 1
        assert result[0].name == "fn_hello"
        assert result[0].routine_type == "FUNCTION"
        assert "fn_hello" in result[0].body

    def test_procedure_type(self) -> None:
        rows = [("proc_test", "PROCEDURE", "owner", "CREATE OR REPLACE PROCEDURE proc_test() ...", "", 0, 0, False)]
        ext = _extractor(rows)
        result = ext.extract_routines("public")
        assert result[0].routine_type == "PROCEDURE"

    def test_aggregate_skipped(self) -> None:
        rows = [("agg_sum", "AGGREGATE", "owner", "...", "int8", 1, 0, False)]
        ext = _extractor(rows)
        assert ext.extract_routines("public") == []

    def test_window_skipped(self) -> None:
        rows = [("win_rank", "WINDOW", "owner", "...", "int4", 0, 1, False)]
        ext = _extractor(rows)
        assert ext.extract_routines("public") == []

    def test_no_body_emits_warning(self) -> None:
        rows = [("fn_empty", "FUNCTION", "owner", None, "void", 0, 0, False)]
        ext = _extractor(rows)
        result = ext.extract_routines("public")
        assert result[0].body == ""
        assert len(result[0].warnings) == 1

    def test_short_row_skipped(self) -> None:
        rows = [("fn_bad",)]
        ext = _extractor(rows)
        assert ext.extract_routines("public") == []
