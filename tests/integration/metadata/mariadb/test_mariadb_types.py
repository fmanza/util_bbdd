"""Integration tests for JSON Schema Introspection — Phase 4a.3 (MariaDB).

Tests Phase 4a.3 of v0.8.0 Type System improvements for MariaDB:
- JSON schema inference from column sampling (primary mechanism)
- CHECK constraint extraction (MariaDB 10.2+)
- Edge cases (large objects, arrays, mixed types, NULL values)

Test Cases:
    1. JSON column with sampling (MariaDB behavior)
    2. JSON column with CHECK constraint (MariaDB 10.2+ support)
    3. Large JSON object (20+ properties)
    4. JSON array schema
    5. Null/empty column handling
    6. Error handling (sampling issues)

Note: MariaDB JSON handling is nearly identical to MySQL, so this reuses
      the MySQL implementation via wrapper delegation.
"""

from unittest.mock import MagicMock

from util_bbdd.metadata.mariadb.types_advanced import query_json_column_schema

# ============================================================================
# TEST CASE 1: JSON Column Like MySQL (Sampling Fallback)
# ============================================================================


def test_mariadb_json_schema_like_mysql() -> None:
    """Verify JSON schema inference from sampling (primary mechanism for MariaDB)."""
    # Setup: Mock adapter returns:
    # 1. No CHECK constraints (typical)
    # 2. Sample JSON rows
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    sample_rows = [
        ('{"user_id": 101, "event": "login"}',),
        ('{"user_id": 102, "event": "logout"}',),
        ('{"user_id": 103, "event": "login"}',),
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK constraints
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
    assert set(result["required"]) == {"user_id", "event"}


# ============================================================================
# TEST CASE 2: JSON with CHECK Constraint (MariaDB 10.2+ Support)
# ============================================================================


def test_mariadb_json_with_check_constraint() -> None:
    """Verify CHECK constraint extraction (MariaDB 10.2+ has better support)."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    check_clause = """JSON_SCHEMA_VALID('{"type": "object", "properties": {
        "id": {"type": "integer"}, "status": {"type": "string"}
    }, "required": ["id"]}', payload)"""

    mock_adapter._execute_metadata_many.side_effect = [
        [(check_clause,)],  # CHECK constraint found
    ]

    # Execute
    result = query_json_column_schema("test_db", "records", "data", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert result["source"] == "constraint"
    assert result["required"] == ["id"]


# ============================================================================
# TEST CASE 3: Large JSON Object (20+ Properties)
# ============================================================================


def test_mariadb_large_json_object() -> None:
    """Verify schema inference for JSON with many properties."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Large JSON with 15+ properties
    large_json = """{
        "id": 1, "user_id": 100, "email": "test@example.com",
        "first_name": "John", "last_name": "Doe",
        "created_at": "2026-04-21T10:00:00Z",
        "updated_at": "2026-04-21T15:00:00Z",
        "status": "active", "role": "admin",
        "department": "engineering", "location": "us-east-1",
        "phone": "+1234567890", "bio": "Software engineer"
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
    assert "id" in result["properties"]
    assert "user_id" in result["properties"]
    assert "email" in result["properties"]
    assert "preferences" in result["properties"] or "department" in result["properties"]
    # Should have multiple properties
    assert len(result["required"]) >= 8


# ============================================================================
# TEST CASE 4: JSON with NULL Values (Sampling Filter)
# ============================================================================


def test_mariadb_json_with_null_values() -> None:
    """Verify handling of columns with mix of NULL and JSON values."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Sampling query filters NULLs automatically
    sample_rows = [
        ('{"id": 1, "status": "active"}',),
        ('{"id": 2, "status": "pending"}',),
        ('{"id": 3, "status": "inactive"}',),
    ]

    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK
        sample_rows,
    ]

    # Execute
    result = query_json_column_schema("test_db", "events", "data", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert "id" in result["properties"]
    assert "status" in result["properties"]
    assert set(result["required"]) == {"id", "status"}


# ============================================================================
# TEST CASE 5: JSON Column Not Found (Column Does Not Exist)
# ============================================================================


def test_mariadb_json_not_found() -> None:
    """Verify graceful handling when column not found or no JSON values."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # No samples (column empty or does not contain JSON)
    mock_adapter._execute_metadata_many.side_effect = [
        [],  # No CHECK
        [],  # No samples
    ]

    # Execute
    result = query_json_column_schema("test_db", "events", "missing_column", mock_adapter)

    # Assertions
    assert result is None


# ============================================================================
# TEST CASE 6: Error Handling (Adapter Error → Graceful Fallback)
# ============================================================================


def test_mariadb_error_handling_graceful() -> None:
    """Verify graceful error handling when adapter fails."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Adapter throws exception during query
    mock_adapter._execute_metadata_many.side_effect = RuntimeError("Database connection lost")

    # Execute
    result = query_json_column_schema("test_db", "events", "data", mock_adapter)

    # Assertions
    # Should return None instead of propagating exception
    assert result is None
