"""Tests del nuevo documento de grafo multinivel."""

from __future__ import annotations

from typing import cast

from util_bbdd.analysis.base import DatabaseRelationshipGraphBase, LevelDirection, TableVisualType
from util_bbdd.managers import SyncDatabaseManager


class _FakeDbManager:
    def __init__(
        self,
        db_type: str,
        tables: list[str],
        fk_by_table: dict[str, list[tuple]],
        columns_by_table: dict[str, list[tuple[str, str]]] | None = None,
    ) -> None:
        self.db_type = db_type
        self._tables = tables
        self._fk_by_table = fk_by_table
        self._columns_by_table = columns_by_table or {}
        self.database = "test_db"

    def get_tables(self) -> list[tuple[str]]:
        return [(table_name,) for table_name in self._tables]

    def get_foreign_keys(self, table_name: str) -> list[tuple]:
        return self._fk_by_table.get(table_name, [])

    def get_columns(self, table_name: str) -> list[tuple[str, str]]:
        return self._columns_by_table.get(table_name, [])

    def get_query_context_database(self) -> str:
        return self.database


def test_build_graph_document_tracks_incoming_and_outgoing_levels() -> None:
    manager = _FakeDbManager(
        db_type="postgresql",
        tables=["users", "orders", "companies", "payments", "sessions"],
        fk_by_table={
            "users": [("fk_users_company", "company_id", "companies", "id")],
            "orders": [("fk_orders_user", "user_id", "users", "id")],
            "companies": [],
            "payments": [("fk_payments_order", "order_id", "orders", "id")],
            "sessions": [("fk_sessions_user", "user_id", "users", "id")],
        },
    )
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))

    document = graph.build_graph_document("users", max_depth=2, direction=LevelDirection.BOTH)

    assert document.root_table == "users"
    assert document.total_outgoing_levels == 1
    assert document.total_incoming_levels == 2
    assert document.hidden_levels.outgoing_hidden_levels == 0
    assert document.hidden_levels.incoming_hidden_levels == 0
    assert {relation.constraint_name for relation in document.relations} == {
        "fk_users_company",
        "fk_orders_user",
        "fk_sessions_user",
        "fk_payments_order",
    }


def test_build_graph_document_reports_hidden_levels_when_depth_is_capped() -> None:
    manager = _FakeDbManager(
        db_type="postgresql",
        tables=["users", "orders", "payments"],
        fk_by_table={
            "users": [],
            "orders": [("fk_orders_user", "user_id", "users", "id")],
            "payments": [("fk_payments_order", "order_id", "orders", "id")],
        },
    )
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))

    document = graph.build_graph_document("users", max_depth=1, direction=LevelDirection.INCOMING)

    assert document.total_incoming_levels == 2
    assert document.hidden_levels.incoming_hidden_levels == 1
    assert len(document.relations) == 1


def test_build_graph_document_handles_cycles_without_infinite_recursion() -> None:
    manager = _FakeDbManager(
        db_type="postgresql",
        tables=["a", "b"],
        fk_by_table={
            "a": [("fk_a_b", "b_id", "b", "id")],
            "b": [("fk_b_a", "a_id", "a", "id")],
        },
    )
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))

    document = graph.build_graph_document("a", max_depth=3, direction=LevelDirection.OUTGOING)

    assert document.total_outgoing_levels == 2
    assert {relation.constraint_name for relation in document.relations} == {"fk_a_b", "fk_b_a"}


def test_build_graph_document_preserves_incoming_levels_in_both_direction_cycles() -> None:
    manager = _FakeDbManager(
        db_type="postgresql",
        tables=["a", "b", "c"],
        fk_by_table={
            "a": [("fk_a_b", "b_id", "b", "id")],
            "b": [("fk_b_c", "c_id", "c", "id")],
            "c": [("fk_c_a", "a_id", "a", "id")],
        },
    )
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))

    document = graph.build_graph_document("a", max_depth=5, direction=LevelDirection.BOTH)

    incoming_depths = sorted(level.depth for level in document.levels if level.direction == LevelDirection.INCOMING)
    outgoing_depths = sorted(level.depth for level in document.levels if level.direction == LevelDirection.OUTGOING)

    assert outgoing_depths == [1, 2, 3]
    assert incoming_depths == [1, 2, 3]
    assert document.total_outgoing_levels == 3
    assert document.total_incoming_levels == 3
    assert document.hidden_levels.outgoing_hidden_levels == 0
    assert document.hidden_levels.incoming_hidden_levels == 0
    assert {relation.constraint_name for relation in document.relations} == {"fk_a_b", "fk_b_c", "fk_c_a"}


def test_build_graph_document_classifies_association_and_entity_nodes() -> None:
    manager = _FakeDbManager(
        db_type="postgresql",
        tables=["users", "roles", "user_roles"],
        fk_by_table={
            "users": [],
            "roles": [],
            "user_roles": [
                ("fk_user_roles_user", "user_id", "users", "id"),
                ("fk_user_roles_role", "role_id", "roles", "id"),
            ],
        },
        columns_by_table={
            "users": [("id", "integer"), ("name", "varchar")],
            "roles": [("id", "integer"), ("name", "varchar")],
            "user_roles": [("user_id", "integer"), ("role_id", "integer")],
        },
    )
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))

    document = graph.build_graph_document("user_roles", max_depth=1, direction=LevelDirection.BOTH)

    assert document.nodes["user_roles"].visual_type == TableVisualType.ASSOCIATION
    assert document.nodes["users"].visual_type == TableVisualType.ENTITY
    assert document.nodes["roles"].visual_type == TableVisualType.ENTITY


def test_build_graph_document_classifies_hierarchy_nodes() -> None:
    manager = _FakeDbManager(
        db_type="postgresql",
        tables=["categories"],
        fk_by_table={
            "categories": [("fk_categories_parent", "parent_id", "categories", "id")],
        },
        columns_by_table={
            "categories": [("id", "integer"), ("parent_id", "integer"), ("name", "varchar")],
        },
    )
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))

    document = graph.build_graph_document("categories", max_depth=1, direction=LevelDirection.BOTH)

    assert document.nodes["categories"].visual_type == TableVisualType.HIERARCHY


def test_build_graph_document_classifies_association_with_composite_pk_and_extra_columns() -> None:
    manager = _FakeDbManager(
        db_type="postgresql",
        tables=["users", "roles", "user_roles"],
        fk_by_table={
            "users": [],
            "roles": [],
            "user_roles": [
                ("fk_user_roles_user", "user_id", "users", "id"),
                ("fk_user_roles_role", "role_id", "roles", "id"),
            ],
        },
        columns_by_table={
            "users": [("id", "integer")],
            "roles": [("id", "integer")],
            "user_roles": [
                ("user_id", "integer"),
                ("role_id", "integer"),
                ("created_at", "timestamp"),
                ("assigned_by", "integer"),
            ],
        },
    )
    manager.get_primary_keys = lambda table_name: (
        [("user_id",), ("role_id",)] if table_name == "user_roles" else [("id",)]
    )  # type: ignore[attr-defined]
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))

    document = graph.build_graph_document("user_roles", max_depth=1, direction=LevelDirection.BOTH)

    assert document.nodes["user_roles"].visual_type == TableVisualType.ASSOCIATION
