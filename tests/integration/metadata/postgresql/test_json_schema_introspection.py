"""Integration tests for JSON Schema Introspection — Phase 2 (PostgreSQL).

Tests Phase 2 of v0.8.0 Type System improvements:
- Extract JSON schema from CHECK constraints
- Infer JSON schema from column sampling
- Handle edge cases (JSONB, nested objects, arrays, errors)

Test Cases:
    1. JSON column with CHECK constraint
    2. JSON column sampling (no constraint)
    3. JSONB column type variant
    4. Nested JSON schema (object within object)
    5. JSON array schema
    6. Error handling (no JSON values, large table)
"""

from unittest.mock import MagicMock

from util_bbdd.metadata.postgresql.types_advanced import query_json_column_schema

# ============================================================================
# TEST CASE 1: JSON with CHECK Constraint
# ============================================================================


def test_json_column_with_check_constraint() -> None:
    """Verify JSON schema extraction from CHECK constraint."""
    # Setup: Mock adapter returns CHECK clause with embedded schema
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # First call: query_check_constraints returns a CHECK constraint
    check_clause = """JSON_SCHEMA_VALID('{"type": "object", "properties": {
        "user_id": {"type": "integer"},
        "timestamp": {"type": "string", "format": "date-time"},
        "status": {"type": "string", "enum": ["active", "inactive"]}
    }, "required": ["user_id", "status"]}', payload)"""

    mock_adapter._execute_metadata_many.side_effect = [
        [(check_clause,)],  # First call: CHECK constraints
    ]

    # Execute
    result = query_json_column_schema("public", "events", "payload", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert result["source"] == "constraint"
    assert "user_id" in result["properties"]
    assert "timestamp" in result["properties"]
    assert "status" in result["properties"]
    assert set(result["required"]) == {"user_id", "status"}


# ============================================================================
# TEST CASE 2: JSON Column Sampling (No Constraint)
# ============================================================================


def test_json_column_sampling_no_constraint() -> None:
    """Verify JSON schema inference from column sampling."""
    # Setup: Mock adapter returns:
    # 1. Empty list for CHECK constraints (no constraint)
    # 2. Sample rows with known structure
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    sample_rows = [
        ('{"user_id": 1, "name": "Alice", "status": "active"}',),
        ('{"user_id": 2, "name": "Bob", "status": "active"}',),
        ('{"user_id": 3, "name": "Charlie", "status": "inactive"}',),
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # First call: no CHECK constraints
        sample_rows,  # Second call: sample rows
    ]

    # Execute
    result = query_json_column_schema("public", "events", "payload", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert result["source"] == "sampling"
    assert result["sample_count"] == 3
    assert "user_id" in result["properties"]
    assert "name" in result["properties"]
    assert "status" in result["properties"]
    # user_id, name, status present in all 3 rows → should be required
    assert "user_id" in result["required"]
    assert "status" in result["required"]


# ============================================================================
# TEST CASE 3: JSONB Column Type
# ============================================================================


def test_jsonb_column_type() -> None:
    """Verify JSONB variant works same as JSON."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    sample_rows = [
        ('{"id": 1, "data": "value1"}',),
        ('{"id": 2, "data": "value2"}',),
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK constraints
        sample_rows,  # Sample rows
    ]

    # Execute (column is JSONB, but parsing logic is same)
    result = query_json_column_schema("public", "documents", "content", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert "id" in result["properties"]
    assert "data" in result["properties"]


# ============================================================================
# TEST CASE 4: Nested JSON Schema
# ============================================================================


def test_nested_json_schema() -> None:
    """Verify nested objects within JSON are captured."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # JSON with nested object structure
    sample_rows = [
        ('{"user": {"id": 1, "name": "Alice"}, "action": "login"}',),
        ('{"user": {"id": 2, "name": "Bob"}, "action": "logout"}',),
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK constraint
        sample_rows,
    ]

    # Execute
    result = query_json_column_schema("public", "audit_log", "event_data", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert "user" in result["properties"]
    assert "action" in result["properties"]
    # user property should be detected as object type
    user_type = result["properties"]["user"].get("type")
    assert user_type in ("object", "mixed")


# ============================================================================
# TEST CASE 5: JSON Array Schema
# ============================================================================


def test_json_array_schema() -> None:
    """Verify JSON arrays are detected and schema inferred."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # JSON array of objects
    sample_rows = [
        ('[{"id": 1, "status": "active"}, {"id": 2, "status": "inactive"}]',),
        ('[{"id": 3, "status": "active"}]',),
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK constraint
        sample_rows,
    ]

    # Execute
    result = query_json_column_schema("public", "batch_events", "items", mock_adapter)

    # Assertions
    assert result is not None
    # Top level is array
    assert result["type"] == "array"
    # Element type should be detected
    assert "element_type" in result


# ============================================================================
# TEST CASE 6: Error Handling (No JSON Values)
# ============================================================================


def test_error_handling_no_json_values() -> None:
    """Verify graceful handling of columns with no JSON values."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Empty sample (no values)
    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK constraint
        [],  # No sample values (all NULL or no rows)
    ]

    # Execute
    result = query_json_column_schema("public", "events", "empty_column", mock_adapter)

    # Assertions
    assert result is None


# ============================================================================
# TEST CASE 7: Mixed Types (Edge Case)
# ============================================================================


def test_mixed_types_json_schema() -> None:
    """Verify handling of JSON with inconsistent types across rows."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # JSON with inconsistent type for 'value' field
    sample_rows = [
        ('{"id": 1, "value": 100}',),  # value is number
        ('{"id": 2, "value": "text"}',),  # value is string
        ('{"id": 3, "value": null}',),  # value is null
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK constraint
        sample_rows,
    ]

    # Execute
    result = query_json_column_schema("public", "mixed_events", "payload", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert "id" in result["properties"]
    assert "value" in result["properties"]
    # value property should show mixed type (number, string, null)
    value_type = result["properties"]["value"].get("type")
    assert value_type in ("mixed", "number", "string")
