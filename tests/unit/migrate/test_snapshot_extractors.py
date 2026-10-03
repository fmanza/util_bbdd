"""Comportamiento común de los extractores de ``migrate`` sobre el snapshot de ``metadata/`` (C3, ADR-003)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.metadata.model import Kind
from util_bbdd.migrate.extractors import (
    MariaDBSchemaExtractor,
    OracleSchemaExtractor,
    PostgreSQLSchemaExtractor,
    SQLServerSchemaExtractor,
)
from util_bbdd.migrate.extractors._snapshot import ROUTINE_KINDS, TABLE_KINDS, VIEW_KINDS, metadata_source

from ._snapshot_source import FakeSource, col, fake_manager, fk, index, pk, routine, table, view


def _pg(*objects: object) -> PostgreSQLSchemaExtractor:
    return PostgreSQLSchemaExtractor(fake_manager("postgresql", *objects))


class TestSource:
    def test_manager_metadata_source_is_used(self) -> None:
        manager = fake_manager("postgresql")
        assert metadata_source(manager) is manager.metadata_source

    def test_metadata_source_is_accepted_directly(self) -> None:
        source = FakeSource("postgresql")
        assert metadata_source(source) is source

    def test_object_without_batched_metadata_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="metadatos por lotes"):
            PostgreSQLSchemaExtractor(MagicMock(spec=["execute_custom_many"]))

    def test_first_read_invalidates_the_schema_once_and_reads_by_kind_group(self) -> None:
        source = FakeSource("postgresql", [table("t")])
        extractor = PostgreSQLSchemaExtractor(source)
        extractor.extract("s")
        extractor.extract_views("s")
        extractor.extract_routines("s")
        assert source.invalidations == ["s"]
        assert source.reads == [TABLE_KINDS, VIEW_KINDS, ROUTINE_KINDS]
        assert Kind.IDENTITY not in TABLE_KINDS  # la identidad va en ColumnMeta


class TestTables:
    def test_empty_schema(self) -> None:
        assert _pg().extract("s") == []

    def test_table_columns_pk_and_comment(self) -> None:
        tables = _pg(
            table("t", "tabla"),
            col("t", "id", 1, "integer", nullable=False),
            col("t", "name", 2, "character varying(20)", "character varying", length=20, comment="nombre"),
            pk("t", "id"),
        ).extract("s")
        (t,) = tables
        assert (t.name, t.original_name, t.schema, t.comment, t.primary_key) == ("t", "t", "s", "tabla", ["id"])
        assert [(c.name, c.is_primary_key, c.nullable, c.ordinal, c.comment) for c in t.columns] == [
            ("id", True, False, 1, ""),
            ("name", False, True, 2, "nombre"),
        ]
        assert t.columns[1].target_type == ""  # lo rellena el transformer

    def test_composite_pk_keeps_key_order(self) -> None:
        (t,) = _pg(table("t"), col("t", "a", 1, "integer"), col("t", "b", 2, "integer"), pk("t", "b", "a")).extract("s")
        assert t.primary_key == ["b", "a"]
        assert all(c.is_primary_key for c in t.columns)

    def test_foreign_keys_internal_external_and_rules(self) -> None:
        (t,) = _pg(
            table("c"),
            col("c", "a", 1, "integer"),
            col("c", "b", 2, "integer"),
            fk("c", "fk_in", ("b", "a"), "p", ("y", "x"), on_delete="CASCADE", on_update="SET NULL"),
            fk("c", "fk_out", ("a",), "other", ("id",), ref_schema="OTRO"),
        ).extract("s")
        internal, external = t.foreign_keys
        assert (internal.columns, internal.ref_columns, internal.on_delete, internal.on_update) == (
            ["b", "a"],
            ["y", "x"],
            "CASCADE",
            "SET NULL",
        )
        assert (internal.is_external, external.is_external) == (False, True)

    def test_same_schema_in_other_case_is_not_external(self) -> None:
        (t,) = OracleSchemaExtractor(
            fake_manager(
                "oracle", table("C"), col("C", "A", 1, "NUMBER"), fk("C", "FK", ("A",), "P", ("A",), ref_schema="HR")
            )
        ).extract("hr")
        assert t.foreign_keys[0].is_external is False

    def test_indexes_skip_primary_and_expressions_with_warning(self) -> None:
        (t,) = _pg(
            table("t"),
            col("t", "id", 1, "integer"),
            col("t", "name", 2, "text"),
            index("t", "t_pkey", "id", unique=True, primary=True),
            index("t", "ix_name", "name", "id"),
            index("t", "ux_name", "name", unique=True),
            index("t", "ix_lower", "lower(name)"),
        ).extract("s")
        assert [(i.name, i.columns, i.unique) for i in t.indexes] == [
            ("ix_name", ["name", "id"], False),
            ("ux_name", ["name"], True),
        ]
        (warning,) = t.warnings
        assert (warning.category, warning.code, warning.table) == ("INDEX", "INDEX_EXPRESSION_SKIPPED", "t")
        assert "lower(name)" in warning.message


class TestViews:
    def test_view_definition_columns_and_comment(self) -> None:
        (v,) = _pg(
            view("v", " SELECT id FROM t; ", "vista"),
            col("v", "id", 1, "integer"),
            view("mv", "SELECT 1", materialized=True),
        ).extract_views("s")
        assert (v.name, v.schema, v.query, v.columns, v.comment, v.warnings) == (
            "v",
            "s",
            "SELECT id FROM t;",
            ["id"],
            "vista",
            [],
        )

    def test_no_views(self) -> None:
        assert _pg().extract_views("s") == []


class TestRoutines:
    def test_functions_and_procedures_with_body_return_type_and_comment(self) -> None:
        f, p = _pg(
            routine("f", "FUNCTION", "CREATE FUNCTION f() ...", return_type="integer", comment="suma"),
            routine("p", "PROCEDURE", "CREATE PROCEDURE p() ..."),
        ).extract_routines("s")
        assert (f.name, f.routine_type, f.body, f.return_type, f.comment, f.schema) == (
            "f",
            "FUNCTION",
            "CREATE FUNCTION f() ...",
            "integer",
            "suma",
            "s",
        )
        assert (p.return_type, p.warnings) == ("", [])

    def test_routine_without_definition_warns(self) -> None:
        (r,) = SQLServerSchemaExtractor(fake_manager("sqlserver", routine("f", "FUNCTION"))).extract_routines("dbo")
        assert r.body == ""
        assert [(w.code, w.message) for w in r.warnings] == [
            ("ROUTINE_NO_BODY", "Body de 'f' no disponible en sys.sql_modules; emitir stub.")
        ]

    def test_overloads_are_kept(self) -> None:
        routines = MariaDBSchemaExtractor(
            fake_manager(
                "mariadb",
                routine("x", "FUNCTION", "CREATE FUNCTION x"),
                routine("x", "PROCEDURE", "CREATE PROCEDURE x"),
            )
        ).extract_routines("db")
        assert [(r.name, r.routine_type) for r in routines] == [("x", "FUNCTION"), ("x", "PROCEDURE")]
