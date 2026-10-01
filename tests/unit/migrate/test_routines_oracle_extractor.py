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


def _body(name: str, routine_type: str, lines: list[tuple]) -> list[tuple]:
    """Filas de la consulta de cuerpos por schema (D1): (name, type, line, text)."""
    return [(name, routine_type, line, text) for line, text in lines]


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
        routine_rows = [("SP_HELLO", "PROCEDURE", None)]
        body_rows = _body(
            "SP_HELLO", "PROCEDURE", [(1, "PROCEDURE SP_HELLO AS\n"), (2, "BEGIN\n"), (3, "  NULL;\n"), (4, "END;\n")]
        )
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
        routine_rows = [("FN_CALC", "FUNCTION", None)]
        body_rows = _body(
            "FN_CALC",
            "FUNCTION",
            [(1, "FUNCTION FN_CALC RETURN NUMBER AS\n"), (2, "BEGIN\n"), (3, "  RETURN 1;\n"), (4, "END;\n")],
        )
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
        routine_rows = [("SP_EMPTY", "PROCEDURE", None)]
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
        routine_rows = [("PKG_UTIL", "PACKAGE BODY", None)]
        body_rows = _body(
            "PKG_UTIL",
            "PACKAGE BODY",
            [
                (1, "CREATE OR REPLACE PACKAGE BODY PKG_UTIL AS\n"),
                (2, "  PROCEDURE GET_DATA IS\n"),
                (3, "  BEGIN\n"),
                (4, "    SELECT 1 FROM DUAL;\n"),
                (5, "  END;\n"),
                (6, "END PKG_UTIL;\n"),
            ],
        )
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
        routine_rows = [("PKG_UTIL", "PACKAGE", None)]
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [iter(routine_rows), iter([])]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_routines("MY_SCHEMA")
        assert len(result) == 1
        assert result[0].is_package_member is True
        assert result[0].body == ""

    def test_unknown_type_skipped(self) -> None:
        routine_rows = [("OBJ_X", "TRIGGER", None)]
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [iter(routine_rows), iter([])]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_routines("MY_SCHEMA")
        assert result == []

    def test_invalid_row_skipped(self) -> None:
        # Fila demasiado corta (< 3 elementos)
        routine_rows = [("SP_BAD",)]
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [iter(routine_rows), iter([])]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_routines("MY_SCHEMA")
        assert result == []


class TestOracleRoutineNamesHotfixR4:
    """Hotfix R4 (0.23.1): en ALL_PROCEDURES el nombre de una rutina suelta está en object_name (procedure_name es
    NULL); antes salía con nombre '' y sin cuerpo, y el package de un miembro tomaba el nombre del miembro."""

    def test_standalone_routine_takes_object_name_and_create(self) -> None:
        ext = _extractor(
            [("SP_HELLO", "PROCEDURE", None)],
            _body("SP_HELLO", "PROCEDURE", [(1, "PROCEDURE SP_HELLO AS\n"), (2, "BEGIN NULL; END;")]),
        )
        [routine] = ext.extract_routines("MY_SCHEMA")
        assert routine.name == "SP_HELLO" and routine.original_name == "SP_HELLO"
        assert routine.body == "CREATE OR REPLACE PROCEDURE SP_HELLO AS\nBEGIN NULL; END;"
        assert not any(w.code == "ROUTINE_NO_BODY" for w in routine.warnings)

    def test_package_member_takes_procedure_name_and_package_object_name(self) -> None:
        ext = _extractor([("PKG_UTIL", "PACKAGE", None), ("PKG_UTIL", "PACKAGE", "GET_DATA")], [])
        package, member = ext.extract_routines("MY_SCHEMA")
        assert (package.name, package.package_name) == ("PKG_UTIL", "PKG_UTIL")
        assert (member.name, member.package_name, member.is_package_member) == ("GET_DATA", "PKG_UTIL", True)
        assert member.body == ""


class TestOracleRoutineBodiesInOneQuery:
    """D1 (0.21.0): los cuerpos de todas las rutinas salen de una sola consulta a ALL_SOURCE (antes una por rutina)."""

    def test_bodies_are_split_by_name_and_type_with_two_queries_in_total(self) -> None:
        routine_rows = [("SP_A", "PROCEDURE", None), ("FN_B", "FUNCTION", None), ("PKG_C", "PACKAGE BODY", None)]
        body_rows = (
            _body("FN_B", "FUNCTION", [(1, "FUNCTION FN_B "), (2, "RETURN 1")])
            + _body("PKG_C", "PACKAGE BODY", [(1, "PACKAGE BODY PKG_C")])
            + _body("PKG_C", "PACKAGE", [(1, "PACKAGE PKG_C -- spec, no se lee")])
            + _body("SP_A", "PROCEDURE", [(1, "PROCEDURE SP_A "), (2, "IS BEGIN NULL; END;")])
        )
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [iter(routine_rows), iter(body_rows)]
        result = {r.name: r.body for r in OracleSchemaExtractor(manager).extract_routines("MY_SCHEMA")}
        # R4: las rutinas sueltas llevan «CREATE OR REPLACE» (ALL_SOURCE no lo guarda)
        assert result == {
            "SP_A": "CREATE OR REPLACE PROCEDURE SP_A IS BEGIN NULL; END;",
            "FN_B": "CREATE OR REPLACE FUNCTION FN_B RETURN 1",
            "PKG_C": "PACKAGE BODY PKG_C",
        }
        assert manager.execute_custom_many.call_count == 2

    def test_no_routines_no_body_query(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.side_effect = [iter([])]
        assert OracleSchemaExtractor(manager).extract_routines("MY_SCHEMA") == []
        assert manager.execute_custom_many.call_count == 1
