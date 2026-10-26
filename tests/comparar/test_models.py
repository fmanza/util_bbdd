"""Tests para los modelos de datos de comparación de esquemas."""

from __future__ import annotations

import json

from typing import Any

import pytest

from util_bbdd.comparar import SchemaDiffValidationError
from util_bbdd.comparar.models import (
    ColumnDiff,
    CommentDiff,
    ForeignKeyDiff,
    IndexDiff,
    RoutineDiff,
    SchemaDiff,
    TableDiff,
    ViewDiff,
)


class TestColumnDiff:
    def test_frozen_dataclass(self) -> None:
        diff = ColumnDiff(column_name="id", attribute="type", source_value="INT", target_value="BIGINT")
        assert diff.column_name == "id"
        assert diff.attribute == "type"
        assert diff.source_value == "INT"
        assert diff.target_value == "BIGINT"

    def test_equality(self) -> None:
        a = ColumnDiff(column_name="id", attribute="type", source_value="INT", target_value="BIGINT")
        b = ColumnDiff(column_name="id", attribute="type", source_value="INT", target_value="BIGINT")
        assert a == b


class TestTableDiff:
    def test_added_table(self) -> None:
        diff = TableDiff(table_name="users", status="added")
        assert diff.table_name == "users"
        assert diff.status == "added"
        assert diff.column_diffs == ()
        assert diff.index_diffs == ()
        assert diff.fk_diffs == ()

    def test_modified_table_with_children(self) -> None:
        col = ColumnDiff(column_name="name", attribute="type", source_value="VARCHAR(50)", target_value="VARCHAR(100)")
        idx = IndexDiff(index_name="idx_name", table_name="users", status="added", source_columns="name")
        fk = ForeignKeyDiff(fk_name="fk_role", table_name="users", status="removed")
        comment = CommentDiff(object_name="users", column_name=None, source_comment="tabla", target_comment="")

        diff = TableDiff(
            table_name="users",
            status="modified",
            column_diffs=(col,),
            index_diffs=(idx,),
            fk_diffs=(fk,),
            comment_diffs=(comment,),
        )
        assert len(diff.column_diffs) == 1
        assert len(diff.index_diffs) == 1
        assert len(diff.fk_diffs) == 1
        assert len(diff.comment_diffs) == 1


class TestSchemaDiff:
    def test_empty_diff_has_no_differences(self) -> None:
        diff = SchemaDiff(source_label="A", target_label="B")
        assert not diff.has_differences
        assert diff.total_differences == 0

    def test_diff_with_tables_has_differences(self) -> None:
        diff = SchemaDiff(
            source_label="A",
            target_label="B",
            table_diffs=(TableDiff(table_name="orders", status="added"),),
        )
        assert diff.has_differences
        assert diff.total_differences == 1

    def test_diff_with_all_types(self) -> None:
        diff = SchemaDiff(
            source_label="A",
            target_label="B",
            table_diffs=(TableDiff(table_name="users", status="added"),),
            view_diffs=(ViewDiff(view_name="v_users", status="removed"),),
            routine_diffs=(RoutineDiff(routine_name="sp_sync", routine_type="PROCEDURE", status="modified"),),
        )
        assert diff.total_differences == 3

    def test_frozen(self) -> None:
        diff = SchemaDiff(source_label="A", target_label="B")
        try:
            diff.source_label = "C"  # type: ignore[misc]
            raised = False
        except AttributeError:
            raised = True
        assert raised


class TestViewDiff:
    def test_view_added(self) -> None:
        diff = ViewDiff(view_name="v_report", status="added", source_definition="CREATE VIEW v_report AS SELECT 1")
        assert diff.view_name == "v_report"
        assert diff.status == "added"
        assert diff.target_definition == ""


class TestRoutineDiff:
    def test_routine_modified(self) -> None:
        diff = RoutineDiff(
            routine_name="sp_sync",
            routine_type="PROCEDURE",
            status="modified",
            source_definition="CREATE PROCEDURE sp_sync() BEGIN END",
            target_definition="CREATE PROCEDURE sp_sync() BEGIN SELECT 1; END",
        )
        assert diff.status == "modified"
        assert diff.routine_type == "PROCEDURE"


class TestSchemaDiffSerialization:
    """G24: ``SchemaDiff.to_dict`` / ``from_dict`` versionados con *round trip* exacto."""

    @staticmethod
    def _full_diff() -> SchemaDiff:
        table = TableDiff(
            table_name="clientes",
            status="modified",
            column_diffs=(ColumnDiff("nombre", "type", "VARCHAR(50)", "VARCHAR(100)"),),
            index_diffs=(IndexDiff("ix_nombre", "clientes", "modified", "nombre", "nombre, id", True, False),),
            fk_diffs=(ForeignKeyDiff("fk_pais", "clientes", "removed", "pais_id", "", "paises", "", "id", ""),),
            comment_diffs=(CommentDiff("clientes", None, "Clientes", "Clientes activos"),),
        )
        return SchemaDiff(
            source_label="postgresql [public]",
            target_label="oracle [APP]",
            table_diffs=(table, TableDiff("paises", "added")),
            view_diffs=(ViewDiff("v_resumen", "modified", "SELECT 1", "SELECT 2"),),
            routine_diffs=(RoutineDiff("calcula", "FUNCTION", "removed", "CREATE FUNCTION calcula ..."),),
            summary="Tablas: 2",
            source_short_label="pg_public",
            target_short_label="ora_APP",
        )

    def test_round_trip_through_json_is_exact(self) -> None:
        diff = self._full_diff()
        data = json.loads(json.dumps(diff.to_dict()))
        assert data["format"] == "util_bbdd.schema_diff"
        assert data["format_version"] == 1
        assert SchemaDiff.from_dict(data) == diff

    def test_empty_diff_round_trip(self) -> None:
        diff = SchemaDiff(source_label="a", target_label="b")
        assert SchemaDiff.from_dict(diff.to_dict()) == diff

    def test_unknown_version_is_a_clear_error(self) -> None:
        data = self._full_diff().to_dict() | {"format_version": 2}
        with pytest.raises(SchemaDiffValidationError, match="format_version 2"):
            SchemaDiff.from_dict(data)

    @pytest.mark.parametrize("data", [{}, {"format": "otro", "format_version": 1}, ["no", "dict"]])
    def test_not_a_serialized_diff(self, data: Any) -> None:
        with pytest.raises(SchemaDiffValidationError):
            SchemaDiff.from_dict(data)

    def test_missing_required_field_names_its_path(self) -> None:
        data = self._full_diff().to_dict()
        del data["table_diffs"][0]["column_diffs"][0]["attribute"]
        with pytest.raises(SchemaDiffValidationError, match=r"table_diffs\[0\]\.column_diffs\[0\]\.attribute"):
            SchemaDiff.from_dict(data)

    @pytest.mark.parametrize(
        ("path", "value"),
        [
            (("table_diffs", 1, "status"), "renamed"),
            (("table_diffs", 0, "index_diffs", 0, "source_unique"), "yes"),
            (("view_diffs",), "v_resumen"),
            (("source_label",), None),
        ],
    )
    def test_wrong_value_type_is_rejected(self, path: tuple[str | int, ...], value: object) -> None:
        data = self._full_diff().to_dict()
        node: Any = data
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        with pytest.raises(SchemaDiffValidationError, match=str(path[-1])):
            SchemaDiff.from_dict(data)

    def test_unknown_keys_and_missing_defaults_are_tolerated(self) -> None:
        data = {"format": "util_bbdd.schema_diff", "format_version": 1, "source_label": "a", "target_label": "b"}
        data["campo_futuro"] = "x"
        assert SchemaDiff.from_dict(data) == SchemaDiff(source_label="a", target_label="b")
