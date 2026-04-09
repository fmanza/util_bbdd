"""Tests para los modelos de datos de comparación de esquemas."""

from __future__ import annotations

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
