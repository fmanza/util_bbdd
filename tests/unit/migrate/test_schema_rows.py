"""H1 (auditoría 0.21.0): agrupar filas por objeto sin perder tablas por diferencias de mayúsculas.

Las consultas por tabla anteriores a D1 filtraban con ``TABLE_NAME = …``, que en MySQL/MariaDB
(``information_schema``) y en SQL Server (collation por defecto) no distingue mayúsculas. Agrupando por el nombre
exacto, si dos vistas del catálogo devolvieran la misma tabla con distinta capitalización (p. ej. MySQL con
``lower_case_table_names=2``), la tabla se quedaba sin columnas sin aviso.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.migrate.extractors._schema_rows import group_by_object
from util_bbdd.migrate.extractors.mariadb import MariaDBSchemaExtractor


class TestForObject:
    def test_exact_name_wins(self) -> None:
        grouped = group_by_object([("T", 1), ("t", 2)])
        assert grouped.for_object("T") == [(1,)] and grouped.for_object("t") == [(2,)]

    def test_falls_back_to_the_only_case_insensitive_match(self) -> None:
        assert group_by_object([("clientes", "id")]).for_object("Clientes") == [("id",)]

    def test_ambiguous_case_insensitive_match_is_not_guessed(self) -> None:
        assert group_by_object([("ab", 1), ("AB", 2)]).for_object("Ab") == []

    def test_unknown_object_has_no_rows(self) -> None:
        assert group_by_object([("t", 1)]).for_object("otra") == []


def test_extractor_finds_columns_when_the_catalog_changes_the_case() -> None:
    manager = MagicMock()

    def side_effect(sql: str, params: dict) -> list:
        if "INFORMATION_SCHEMA.TABLES" in sql:
            return [("Clientes", "")]
        if "INFORMATION_SCHEMA.COLUMNS" in sql:  # otra vista del catálogo, otra capitalización
            return [("clientes", "id", "int", None, 10, 0, "NO", None, "", "", 1)]
        if "CONSTRAINT_NAME = 'PRIMARY'" in sql:
            return [("CLIENTES", "id")]
        return []

    manager.execute_custom_many.side_effect = side_effect
    [table] = MariaDBSchemaExtractor(manager).extract("s")
    assert [c.name for c in table.columns] == ["id"] and table.primary_key == ["id"]
