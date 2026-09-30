"""Tests para extract_routines() del extractor SQL Server.

El extractor usa ``self._query()`` internamente, que llama a
``manager.execute_custom_many(sql, params)``.  Se hacen 2 llamadas (D1): la
primera devuelve el inventario de rutinas y la segunda el código de todas ellas
desde ``sys.sql_modules`` como filas ``(nombre, definición)``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor


def _extractor(
    routine_rows: list[tuple],
    body_rows_per_routine: list[list[tuple]] | None = None,
) -> SQLServerSchemaExtractor:
    """Crea extractor con manager mock.

    Args:
        routine_rows: Filas de la query de inventario (name, type_str, object_id, params_count).
        body_rows_per_routine: Lista de body_rows por rutina — ``[(definition,)]`` o ``[]``.
            Si es ``None``, se usa ``[]`` para cada rutina (sin body).
    """
    manager = MagicMock()
    responses: list = [iter(routine_rows)]
    per_routine = body_rows_per_routine if body_rows_per_routine is not None else [[] for _ in routine_rows]
    if routine_rows:
        bodies = [(row[0], body[0]) for row, rows in zip(routine_rows, per_routine, strict=True) for body in rows]
        responses.append(iter(bodies))
    manager.execute_custom_many.side_effect = responses
    return SQLServerSchemaExtractor(manager)


class TestSQLServerExtractRoutines:
    def test_empty_returns_empty(self) -> None:
        ext = _extractor([])
        assert ext.extract_routines("dbo") == []

    def test_procedure_with_body(self) -> None:
        body_text = "CREATE PROCEDURE dbo.SP_TEST AS BEGIN SELECT 1 END"
        ext = _extractor(
            [("SP_TEST", "PROCEDURE", 1001, 0)],
            [[(body_text,)]],
        )
        result = ext.extract_routines("dbo")
        assert len(result) == 1
        r = result[0]
        assert r.name == "SP_TEST"
        assert r.routine_type == "PROCEDURE"
        assert r.body == body_text
        assert r.warnings == []

    def test_procedure_without_body_emits_warning(self) -> None:
        ext = _extractor(
            [("SP_EMPTY", "PROCEDURE", 1002, 0)],
            [[]],  # sys.sql_modules no devuelve filas
        )
        result = ext.extract_routines("dbo")
        assert result[0].body == ""
        assert len(result[0].warnings) == 1
        assert "no disponible" in result[0].warnings[0].message

    def test_multiple_routines(self) -> None:
        ext = _extractor(
            [("SP_A", "PROCEDURE", 1001, 0), ("FN_B", "FUNCTION", 1002, 0)],
            [
                [("CREATE PROCEDURE dbo.SP_A AS BEGIN SELECT 1 END",)],
                [("CREATE FUNCTION dbo.FN_B() RETURNS INT AS BEGIN RETURN 1 END",)],
            ],
        )
        result = ext.extract_routines("dbo")
        assert len(result) == 2
        assert result[0].name == "SP_A"
        assert result[0].routine_type == "PROCEDURE"
        assert result[1].name == "FN_B"
        assert result[1].routine_type == "FUNCTION"

    def test_scalar_function_extracted_as_function_type(self) -> None:
        """Verifica que funciones escalares (tipo FN) se extraen con routine_type=FUNCTION.

        Antes del fix, build_sqlserver_routines_query() usaba sys.procedures
        que excluye silenciosamente funciones (FN/IF/TF). El fix usa sys.objects
        con type IN ('P','FN','IF','TF'), que sí las incluye.
        """
        body_text = "CREATE FUNCTION dbo.FN_GET_NAME(@id INT) RETURNS NVARCHAR(100) AS BEGIN RETURN 'x' END"
        ext = _extractor(
            [("FN_GET_NAME", "FUNCTION", 2001, 1)],
            [[(body_text,)]],
        )
        result = ext.extract_routines("dbo")
        assert len(result) == 1
        r = result[0]
        assert r.name == "FN_GET_NAME"
        assert r.routine_type == "FUNCTION"
        assert r.body == body_text
        assert r.warnings == []

    def test_inline_tvf_extracted_as_function_type(self) -> None:
        """Verifica que TVF inline (tipo IF) se extrae con routine_type=FUNCTION."""
        body_text = "CREATE FUNCTION dbo.FN_TVF(@id INT) RETURNS TABLE AS RETURN SELECT 1 AS val"
        ext = _extractor(
            [("FN_TVF", "FUNCTION", 2002, 1)],
            [[(body_text,)]],
        )
        result = ext.extract_routines("dbo")
        assert len(result) == 1
        assert result[0].routine_type == "FUNCTION"

    def test_unknown_type_row_included_with_unknown_type(self) -> None:
        """Filas con tipo UNKNOWN (type no reconocido) son incluidas tal cual."""
        ext = _extractor(
            [("OBJ_X", "UNKNOWN", 3001, 0)],
            [[]],
        )
        result = ext.extract_routines("dbo")
        assert len(result) == 1
        assert result[0].routine_type == "UNKNOWN"


def test_bodies_come_from_one_query() -> None:
    """D1 (0.21.0): con N rutinas, 2 consultas en total (antes 1 + N)."""
    manager = MagicMock()
    routines = [("SP_A", "PROCEDURE", 1, 0), ("SP_B", "PROCEDURE", 2, 0), ("FN_C", "FUNCTION", 3, 0)]
    manager.execute_custom_many.side_effect = [iter(routines), iter([("FN_C", "C"), ("SP_A", "A")])]
    result = {r.name: r.body for r in SQLServerSchemaExtractor(manager).extract_routines("dbo")}
    assert result == {"SP_A": "A", "SP_B": "", "FN_C": "C"}
    assert manager.execute_custom_many.call_count == 2
