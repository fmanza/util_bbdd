"""Tests para extract_routines() del extractor SQL Server.

El extractor usa ``self._query()`` internamente, que llama a
``manager.execute_custom_many(sql, params)``.  Se hacen 1 + N llamadas:
la primera devuelve el inventario de rutinas y las N siguientes devuelven
el body de cada una desde ``sys.sql_modules``.
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
    for body_rows in per_routine:
        responses.append(iter(body_rows))
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
