"""Tests para extract_routines() del extractor Oracle."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.migrate.extractors.oracle import OracleSchemaExtractor

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _manager_with_rows(rows: list[list[tuple]]) -> MagicMock:
    """Crea un manager mock que devuelve distintas listas de filas en orden."""
    manager = MagicMock()
    manager.execute_custom_many.side_effect = [iter(r) for r in rows]
    return manager


def _extractor(rows_routines: list[tuple], rows_body: list[tuple] | None = None) -> OracleSchemaExtractor:
    manager = MagicMock()
    call_responses = [iter(rows_routines)]
    if rows_body is not None:
        call_responses.append(iter(rows_body))
    manager.execute_custom_many.side_effect = call_responses
    return OracleSchemaExtractor(manager)


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestOracleExtractRoutines:
    def test_empty_schema_returns_empty_list(self) -> None:
        ext = _extractor(rows_routines=[])
        result = ext.extract_routines("MY_SCHEMA")
        assert result == []

    def test_procedure_with_body(self) -> None:
        routine_rows = [("SP_HELLO", "PROCEDURE", 1001)]
        body_rows = [(1, "PROCEDURE SP_HELLO AS\n"), (2, "BEGIN\n"), (3, "  NULL;\n"), (4, "END;\n")]
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [
            iter(routine_rows),
            iter(body_rows),
        ]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_routines("MY_SCHEMA")
        assert len(result) == 1
        r = result[0]
        assert r.name == "SP_HELLO"
        assert r.routine_type == "PROCEDURE"
        assert "SP_HELLO" in r.body
        assert r.is_package_member is False

    def test_function_with_body(self) -> None:
        routine_rows = [("FN_CALC", "FUNCTION", 1002)]
        body_rows = [(1, "FUNCTION FN_CALC RETURN NUMBER AS\n"), (2, "BEGIN\n"), (3, "  RETURN 1;\n"), (4, "END;\n")]
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [
            iter(routine_rows),
            iter(body_rows),
        ]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_routines("MY_SCHEMA")
        assert len(result) == 1
        assert result[0].routine_type == "FUNCTION"

    def test_procedure_without_body_emits_warning(self) -> None:
        routine_rows = [("SP_EMPTY", "PROCEDURE", 1003)]
        body_rows: list[tuple] = []
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [
            iter(routine_rows),
            iter(body_rows),
        ]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_routines("MY_SCHEMA")
        assert len(result) == 1
        assert result[0].body == ""
        assert any("no disponible" in w.message for w in result[0].warnings)

    def test_package_body_fetches_and_stores_body(self) -> None:
        routine_rows = [("PKG_UTIL", "PACKAGE BODY", 1005)]
        body_rows = [
            (1, "CREATE OR REPLACE PACKAGE BODY PKG_UTIL AS\n"),
            (2, "  PROCEDURE GET_DATA IS\n"),
            (3, "  BEGIN\n"),
            (4, "    SELECT 1 FROM DUAL;\n"),
            (5, "  END;\n"),
            (6, "END PKG_UTIL;\n"),
        ]
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [iter(routine_rows), iter(body_rows)]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_routines("MY_SCHEMA")
        assert len(result) == 1
        r = result[0]
        assert r.is_package_member is True
        assert r.package_name == "PKG_UTIL"
        assert "PKG_UTIL" in r.body
        assert r.body != ""

    def test_package_spec_has_no_body(self) -> None:
        routine_rows = [("PKG_UTIL", "PACKAGE", 1004)]
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [iter(routine_rows)]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_routines("MY_SCHEMA")
        assert len(result) == 1
        assert result[0].is_package_member is True
        assert result[0].body == ""

    def test_unknown_type_skipped(self) -> None:
        routine_rows = [("OBJ_X", "TRIGGER", 1006)]
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [iter(routine_rows)]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_routines("MY_SCHEMA")
        assert result == []

    def test_invalid_row_skipped(self) -> None:
        # Fila demasiado corta (< 3 elementos)
        routine_rows = [("SP_BAD",)]
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [iter(routine_rows)]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_routines("MY_SCHEMA")
        assert result == []
