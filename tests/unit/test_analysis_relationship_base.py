"""Unit tests for relationship graph base behavior."""

from typing import cast

from util_bbdd.analysis.base import DatabaseRelationshipGraphBase, TableRelation
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
    relations = [
        TableRelation("t0", f"t{idx}", f"fk_{idx}", "id", "id")
        for idx in range(11)
    ]

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
