"""Unit tests for metadata cache classes."""

from util_bbdd.metadata import DatabaseMetadataCache, RelationshipMetadataCache


def test_database_metadata_cache_set_get_uses_defensive_copy() -> None:
    cache = DatabaseMetadataCache()
    table_key = ("db", "users")
    source_pks = ["id"]

    cache.set_primary_keys(table_key, source_pks)
    source_pks.append("unexpected")

    assert cache.get_primary_keys(table_key) == ["id"]


def test_database_metadata_cache_clear_by_table_only_invalidates_target() -> None:
    cache = DatabaseMetadataCache()
    users_key = ("db", "users")
    orders_key = ("db", "orders")

    cache.set_columns(users_key, [("id", "int")])
    cache.set_columns(orders_key, [("id", "int")])
    cache._ddl_cache[users_key] = "CREATE TABLE users (...)"  # noqa: SLF001
    cache._ddl_cache[orders_key] = "CREATE TABLE orders (...)"  # noqa: SLF001

    cache.clear_by_table(context="db", table="users")

    assert cache.get_columns(users_key) is None
    assert cache.get_columns(orders_key) == [("id", "int")]
    assert users_key not in cache._ddl_cache  # noqa: SLF001
    assert orders_key in cache._ddl_cache  # noqa: SLF001


def test_database_metadata_cache_clear_all_resets_all_stats() -> None:
    cache = DatabaseMetadataCache()
    table_key = ("db", "users")
    routine_key = ("db", "sp_users", "PROCEDURE")

    cache._tables_cache["db"] = [("users",)]  # noqa: SLF001
    cache.set_columns(table_key, [("id", "int")])
    cache._routine_parameters_cache[routine_key] = [("IN", "p_id", "INT")]  # noqa: SLF001

    cache.clear_all()

    stats = cache.get_cache_stats()
    assert stats["tables"] == 0
    assert stats["columns"] == 0
    assert stats["routine_parameters"] == 0
    assert stats["total_entries"] == 0


def test_relationship_metadata_cache_uses_shared_database_cache() -> None:
    db_cache = DatabaseMetadataCache()
    rel_cache = RelationshipMetadataCache(db_cache=db_cache)
    table_key = ("db", "users")

    rel_cache.set_primary_keys_list(table_key, ["id"])
    rel_cache.set_unique_constraints_list(table_key, ["email"])
    rel_cache.set_is_primary_key("users", "id", True)

    rel_cache.clear_all()

    assert db_cache.get_primary_keys(table_key) == ["id"]
    assert db_cache.get_unique_constraints(table_key) == ["email"]
    assert rel_cache.get_cache_stats()["total_entries"] == 0


def test_relationship_metadata_cache_clear_by_table_removes_related_entries_only() -> None:
    rel_cache = RelationshipMetadataCache()
    rel_cache.set_cardinality("user_id", "id", "orders", "users", "1:N")
    rel_cache.set_cardinality("company_id", "id", "users", "companies", "1:N")
    rel_cache.set_is_primary_key("users", "id", True)
    rel_cache.set_is_primary_key("orders", "id", True)
    rel_cache.set_is_unique_column("users", "email", True)
    rel_cache.set_table_columns_typed("users", [("id", "int")])
    rel_cache.set_table_columns_typed("orders", [("id", "int")])

    rel_cache.clear_by_table("users")

    assert rel_cache.get_cardinality("user_id", "id", "orders", "users") is None
    assert rel_cache.get_cardinality("company_id", "id", "users", "companies") is None
    assert rel_cache.get_is_primary_key("users", "id") is None
    assert rel_cache.get_is_unique_column("users", "email") is None
    assert rel_cache.get_is_primary_key("orders", "id") is True
    assert rel_cache.get_table_columns_typed("users") is None
    assert rel_cache.get_table_columns_typed("orders") == [("id", "int")]


class TestRelationshipMetadataCacheCrossSchemaIsolation:
    """MDC-02 (AUDIT_CODE 2026-09-22): las 4 cachés de RelationshipMetadataCache
    indexaban solo por nombre de tabla, sin componente de schema/contexto -> colisión
    entre esquemas con tabla homónima (p.ej. "sales.orders" vs "archive.orders")."""

    def test_is_primary_key_does_not_collide_across_contexts(self) -> None:
        rel_cache = RelationshipMetadataCache()

        rel_cache.set_is_primary_key("orders", "id", True, context="sales")
        rel_cache.set_is_primary_key("orders", "id", False, context="archive")

        assert rel_cache.get_is_primary_key("orders", "id", context="sales") is True
        assert rel_cache.get_is_primary_key("orders", "id", context="archive") is False

    def test_is_unique_column_does_not_collide_across_contexts(self) -> None:
        rel_cache = RelationshipMetadataCache()

        rel_cache.set_is_unique_column("orders", "code", True, context="sales")
        rel_cache.set_is_unique_column("orders", "code", False, context="archive")

        assert rel_cache.get_is_unique_column("orders", "code", context="sales") is True
        assert rel_cache.get_is_unique_column("orders", "code", context="archive") is False

    def test_cardinality_does_not_collide_across_contexts(self) -> None:
        rel_cache = RelationshipMetadataCache()

        rel_cache.set_cardinality("user_id", "id", "orders", "users", "1:N", context="sales")
        rel_cache.set_cardinality("user_id", "id", "orders", "users", "M:N", context="archive")

        assert rel_cache.get_cardinality("user_id", "id", "orders", "users", context="sales") == "1:N"
        assert rel_cache.get_cardinality("user_id", "id", "orders", "users", context="archive") == "M:N"

    def test_table_columns_typed_does_not_collide_across_contexts(self) -> None:
        rel_cache = RelationshipMetadataCache()

        rel_cache.set_table_columns_typed("orders", [("id", "int")], context="sales")
        rel_cache.set_table_columns_typed("orders", [("id", "bigint")], context="archive")

        assert rel_cache.get_table_columns_typed("orders", context="sales") == [("id", "int")]
        assert rel_cache.get_table_columns_typed("orders", context="archive") == [("id", "bigint")]

    def test_context_defaults_to_empty_string_for_backward_compatibility(self) -> None:
        """Sin context explícito, el comportamiento previo (namespace único) se preserva."""
        rel_cache = RelationshipMetadataCache()

        rel_cache.set_is_primary_key("orders", "id", True)

        assert rel_cache.get_is_primary_key("orders", "id") is True
        assert rel_cache.get_is_primary_key("orders", "id", context="") is True

    def test_clear_by_table_without_context_clears_all_contexts(self) -> None:
        """Comportamiento retrocompatible: sin context, invalida en TODOS los schemas."""
        rel_cache = RelationshipMetadataCache()
        rel_cache.set_is_primary_key("orders", "id", True, context="sales")
        rel_cache.set_is_primary_key("orders", "id", True, context="archive")

        rel_cache.clear_by_table("orders")

        assert rel_cache.get_is_primary_key("orders", "id", context="sales") is None
        assert rel_cache.get_is_primary_key("orders", "id", context="archive") is None

    def test_clear_by_table_with_context_only_clears_that_context(self) -> None:
        rel_cache = RelationshipMetadataCache()
        rel_cache.set_is_primary_key("orders", "id", True, context="sales")
        rel_cache.set_is_primary_key("orders", "id", True, context="archive")
        rel_cache.set_table_columns_typed("orders", [("id", "int")], context="sales")
        rel_cache.set_table_columns_typed("orders", [("id", "int")], context="archive")
        rel_cache.set_cardinality("user_id", "id", "orders", "users", "1:N", context="sales")
        rel_cache.set_cardinality("user_id", "id", "orders", "users", "1:N", context="archive")

        rel_cache.clear_by_table("orders", context="sales")

        assert rel_cache.get_is_primary_key("orders", "id", context="sales") is None
        assert rel_cache.get_is_primary_key("orders", "id", context="archive") is True
        assert rel_cache.get_table_columns_typed("orders", context="sales") is None
        assert rel_cache.get_table_columns_typed("orders", context="archive") == [("id", "int")]
        assert rel_cache.get_cardinality("user_id", "id", "orders", "users", context="sales") is None
        assert rel_cache.get_cardinality("user_id", "id", "orders", "users", context="archive") == "1:N"
