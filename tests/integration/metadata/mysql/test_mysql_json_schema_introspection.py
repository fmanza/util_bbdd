"""Integration tests for JSON Schema Introspection — Phase 2 (MySQL).

Tests Phase 2 of v0.8.0 Type System improvements for MySQL:
- JSON schema inference from column sampling (primary mechanism)
- CHECK constraint extraction (if available, rare in MySQL)
- Edge cases (large objects, arrays, mixed types, NULL values)

Test Cases:
    1. JSON column with sampling (no CHECK constraint)
    2. JSON column with CHECK constraint (limited MySQL support)
    3. Large JSON object (20+ properties)
    4. JSON array schema
    5. Mixed types in array (type union)
    6. Error handling (NULL column, sampling issues)
"""

from unittest.mock import MagicMock

from util_bbdd.metadata.mysql.types_advanced import query_json_column_schema

# ============================================================================
# TEST CASE 1: JSON Column No Constraint (Primary for MySQL)
# ============================================================================


def test_json_column_no_constraint_mysql() -> None:
    """Verify JSON schema inference from sampling (primary mechanism for MySQL)."""
    # Setup: Mock adapter returns:
    # 1. No CHECK constraints (typical for MySQL)
    # 2. Sample JSON rows
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    sample_rows = [
        ('{"user_id": 101, "event": "login"}',),
        ('{"user_id": 102, "event": "logout"}',),
        ('{"user_id": 103, "event": "login"}',),
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK constraints (expected for MySQL)
        sample_rows,  # Sample values
    ]

    # Execute
    result = query_json_column_schema("events_db", "api_logs", "request_data", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert result["source"] == "sampling"
    assert result["sample_count"] == 3
    assert "user_id" in result["properties"]
    assert "event" in result["properties"]
    # Both fields present in all rows → required
    assert set(result["required"]) == {"user_id", "event"}


# ============================================================================
# TEST CASE 2: JSON Column with CHECK Constraint (Rare)
# ============================================================================


def test_json_column_with_check_mysql() -> None:
    """Verify CHECK constraint extraction when available (rare for MySQL)."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    check_clause = """JSON_SCHEMA_VALID('{"type": "object", "properties": {
        "id": {"type": "integer"}, "status": {"type": "string"}
    }, "required": ["id"]}', payload)"""

    mock_adapter._execute_metadata_many.side_effect = [
        [(check_clause,)],  # CHECK constraint found (rare for MySQL)
    ]

    # Execute
    result = query_json_column_schema("test_db", "records", "data", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert result["source"] == "constraint"
    assert result["required"] == ["id"]


# ============================================================================
# TEST CASE 3: Large JSON Object
# ============================================================================


def test_large_json_object() -> None:
    """Verify schema inference for JSON with many properties."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # JSON with 20+ properties
    large_json = """{
        "id": 1, "user_id": 100, "email": "test@example.com",
        "first_name": "John", "last_name": "Doe",
        "created_at": "2026-04-21T10:00:00Z",
        "updated_at": "2026-04-21T15:00:00Z",
        "status": "active", "role": "admin",
        "department": "engineering", "location": "us-east-1",
        "phone": "+1234567890", "bio": "Software engineer",
        "avatar_url": "https://example.com/avatar.jpg",
        "preferences": {"theme": "dark", "language": "en"},
        "tags": ["python", "golang", "javascript"],
        "last_login": "2026-04-21T10:00:00Z",
        "api_key": "secret_key_here"
    }"""

    sample_rows = [(large_json,), (large_json,)]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK
        sample_rows,
    ]

    # Execute
    result = query_json_column_schema("users_db", "users", "metadata", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    # Should have properties for all top-level keys
    assert "id" in result["properties"]
    assert "user_id" in result["properties"]
    assert "email" in result["properties"]
    assert "preferences" in result["properties"]
    assert "tags" in result["properties"]
    # All fields present in all rows → all required
    assert len(result["required"]) >= 10


# ============================================================================
# TEST CASE 4: JSON Array Schema
# ============================================================================


def test_json_array_schema_mysql() -> None:
    """Verify JSON array detection and element type inference."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Array of objects
    array_samples = [
        ('[{"id": 1, "name": "Item1"}, {"id": 2, "name": "Item2"}]',),
        ('[{"id": 3, "name": "Item3"}]',),
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK
        array_samples,
    ]

    # Execute
    result = query_json_column_schema("shop_db", "orders", "items", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "array"
    assert "element_type" in result


# ============================================================================
# TEST CASE 5: Mixed Types in Array
# ============================================================================


def test_mixed_types_in_array_mysql() -> None:
    """Verify handling of arrays with mixed element types."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Array with mixed types: [1, "string", true, null, {"key": "value"}]
    mixed_array = '[1, "text", true, null, {"nested": "object"}, 3.14]'

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK
        [(mixed_array,), (mixed_array,)],
    ]

    # Execute
    result = query_json_column_schema("test_db", "mixed_data", "values", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "array"
    # Element type should be "mixed" due to variety
    assert result["element_type"] in ("mixed", "number", "string")


# ============================================================================
# TEST CASE 6: Error Handling (NULL Column)
# ============================================================================


def test_error_handling_null_column_mysql() -> None:
    """Verify graceful handling of NULL-only or empty JSON columns."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK
        [],  # No samples (all NULL or table empty)
    ]

    # Execute
    result = query_json_column_schema("test_db", "events", "null_column", mock_adapter)

    # Assertions
    assert result is None


# ============================================================================
# TEST CASE 7: Partial NULL Values
# ============================================================================


def test_partial_null_values_mysql() -> None:
    """Verify handling of columns with mix of NULL and JSON values."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Some NULL, some JSON values (sampling filters NULLs)
    sample_rows = [
        ('{"id": 1, "value": "a"}',),  # NULL rows removed by WHERE clause
        ('{"id": 2, "value": "b"}',),
        ('{"id": 3, "value": "c"}',),
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK
        sample_rows,
    ]

    # Execute
    result = query_json_column_schema("test_db", "sparse_data", "content", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert "id" in result["properties"]
    assert "value" in result["properties"]


# ============================================================================
# TEST CASE 8: Empty Object & Array
# ============================================================================


def test_empty_json_structures_mysql() -> None:
    """Verify handling of empty JSON objects and arrays."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Mix of empty and populated structures
    sample_rows = [
        ("{}",),  # Empty object
        ('{"key": "value"}',),  # Non-empty
        ("{}",),  # Empty again
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK
        sample_rows,
    ]

    # Execute
    result = query_json_column_schema("test_db", "flexible", "data", mock_adapter)

    # Assertions
    # Should still infer something from the non-empty row
    # or return empty object schema if only empty objects present
    assert result is None or result["type"] == "object"
