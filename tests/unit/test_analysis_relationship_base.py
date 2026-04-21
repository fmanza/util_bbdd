"""Unit tests for relationship graph base behavior."""

from pathlib import Path
from typing import cast

from util_bbdd.analysis.base import (
    DatabaseRelationshipGraphBase,
    GraphDocument,
    GraphEdge,
    GraphLevel,
    GraphNode,
    HiddenLevelsSummary,
    LevelDirection,
    TableRelation,
)
from util_bbdd.managers import SyncDatabaseManager


class _FakeDbManager:
    def __init__(self, db_type: str, tables: list[str], fk_by_table: dict[str, list[tuple]]) -> None:
        self.db_type = db_type
        self._tables = tables
        self._fk_by_table = fk_by_table
        self.database = "test_db"

    def get_tables(self) -> list[tuple[str]]:
        return [(table_name,) for table_name in self._tables]

    def get_foreign_keys(self, table_name: str) -> list[tuple]:
        return self._fk_by_table.get(table_name, [])

    def get_query_context_database(self) -> str:
        return self.database


def test_analyze_table_relations_includes_outgoing_and_incoming_non_mariadb() -> None:
    manager = _FakeDbManager(
        db_type="postgresql",
        tables=["users", "orders", "companies"],
        fk_by_table={
            "users": [("fk_users_company", "company_id", "companies", "id")],
            "orders": [("fk_orders_user", "user_id", "users", "id")],
            "companies": [],
        },
    )
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))

    relations = graph.analyze_table_relations("users")

    summary = {(r.source_table, r.target_table, r.constraint_name) for r in relations}
    assert len(relations) == 2
    assert summary == {
        ("users", "companies", "fk_users_company"),
        ("orders", "users", "fk_orders_user"),
    }
    assert graph.tables == {"users", "orders", "companies"}
    assert DatabaseRelationshipGraphBase.__module__ == "util_bbdd.analysis.base"


def test_analyze_table_relations_mariadb_uses_expected_fk_indexes() -> None:
    manager = _FakeDbManager(
        db_type="mariadb",
        tables=["orders", "order_items"],
        fk_by_table={
            "orders": [],
            "order_items": [("fk_items_orders", "order_items", "order_id", "orders", "id")],
        },
    )
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))

    relations = graph.analyze_table_relations("orders")

    assert len(relations) == 1
    relation = relations[0]
    assert relation.source_table == "order_items"
    assert relation.target_table == "orders"
    assert relation.source_column == "order_id"
    assert relation.target_column == "id"


def test_extract_target_table_depends_on_database_type() -> None:
    pg_graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, _FakeDbManager("postgresql", [], {})))
    mariadb_graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, _FakeDbManager("mariadb", [], {})))

    assert pg_graph._extract_target_table(("fk_any", "col", "users", "id")) == "users"
    assert mariadb_graph._extract_target_table(("fk_any", "orders", "user_id", "users", "id")) == "users"


def test_split_relations_for_visualization_keeps_order_and_balances_chunks() -> None:
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, _FakeDbManager("postgresql", [], {})))
    relations = [TableRelation("t0", f"t{idx}", f"fk_{idx}", "id", "id") for idx in range(11)]

    chunks = graph._split_relations_for_visualization(relations, max_subnodes=10)
    merged = [item for chunk in chunks for item in chunk]

    assert [len(chunk) for chunk in chunks] == [6, 5]
    assert merged == relations


def test_generate_relationship_report_returns_expected_counts_and_metadata() -> None:
    manager = _FakeDbManager(
        db_type="postgresql",
        tables=["users", "orders", "companies"],
        fk_by_table={
            "users": [("fk_users_company", "company_id", "companies", "id")],
            "orders": [("fk_orders_user", "user_id", "users", "id")],
            "companies": [],
        },
    )
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, manager))

    report = graph.generate_relationship_report("users")

    assert report["table_name"] == "users"
    assert report["database_type"] == "postgresql"
    assert report["total_relations"] == 2
    assert report["outgoing_relations"]["count"] == 1
    assert report["incoming_relations"]["count"] == 1
    assert set(report["related_tables"]) == {"orders", "companies"}


def test_build_subset_document_filters_relations_preserving_document_metadata() -> None:
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, _FakeDbManager("postgresql", [], {})))
    rel_users_orders = TableRelation("users", "orders", "fk_orders_users", "user_id", "id")
    rel_orders_items = TableRelation("orders", "items", "fk_items_orders", "order_id", "id")
    edge_users_orders = GraphEdge(relation=rel_users_orders, depth=1, direction=LevelDirection.OUTGOING)
    edge_orders_items = GraphEdge(relation=rel_orders_items, depth=2, direction=LevelDirection.OUTGOING)
    document = GraphDocument(
        root_table="users",
        nodes={
            "users": GraphNode(table_name="users", is_root=True),
            "orders": GraphNode(table_name="orders"),
            "items": GraphNode(table_name="items"),
        },
        levels=[
            GraphLevel(
                depth=1, direction=LevelDirection.OUTGOING, edges=[edge_users_orders], tables={"users", "orders"}
            ),
            GraphLevel(
                depth=2, direction=LevelDirection.OUTGOING, edges=[edge_orders_items], tables={"orders", "items"}
            ),
        ],
        edges=[edge_users_orders, edge_orders_items],
        relations=[rel_users_orders, rel_orders_items],
        tables={"users", "orders", "items"},
        max_depth=2,
        direction=LevelDirection.OUTGOING,
        hidden_levels=HiddenLevelsSummary(incoming_hidden_levels=0, outgoing_hidden_levels=1),
        total_incoming_levels=0,
        total_outgoing_levels=3,
    )

    subset = graph._build_subset_document(document, [rel_users_orders])

    assert subset.relations == [rel_users_orders]
    assert subset.edges == [edge_users_orders]
    assert subset.tables == {"users", "orders"}
    assert set(subset.nodes) == {"users", "orders"}
    assert subset.max_depth == 2
    assert subset.hidden_levels.outgoing_hidden_levels == 1
    assert subset.total_outgoing_levels == 3


def test_generate_all_tables_batch_registers_success_and_error() -> None:
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, _FakeDbManager("postgresql", [], {})))

    def _generate_for_table(table_name: str) -> list[Path]:
        if table_name == "broken":
            raise RuntimeError("boom")
        return [Path(f"{table_name}.png")]

    results = graph._generate_all_tables_batch(
        table_names=["users", "broken"],
        skip_tables_without_relations=False,
        max_depth=None,
        direction=None,
        generate_for_table=_generate_for_table,
        error_prefix="Error batch para tabla",
    )

    assert results["users"]["status"] == "success"
    assert results["users"]["files"] == ["users.png"]
    assert results["users"]["count"] == 1
    assert results["broken"]["status"] == "error"
    assert results["broken"]["error"] == "boom"
    assert results["broken"]["files"] == []
