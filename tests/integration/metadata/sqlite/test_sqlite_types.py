"""Integration tests for SQLite JSON Schema Introspection — Phase 4b.2.

Tests Phase 4b.2 of v0.8.0 Type System improvements for SQLite:
- JSON schema inference from column sampling (primary mechanism)
- SQLite: Typeless database (no built-in schema like PostgreSQL/Oracle)
- JSON support: SQLite 3.38+ (JSONB-like storage)
- Edge cases (empty tables, NULL values, non-JSON columns, errors)

Test Strategy (Mock-based):
    - Mock adapter returns sampled rows with JSON values
    - Verify: schema inference works, logging occurs, None returned for non-JSON
    - Test edge cases (empty, NULL, mixed types, errors)
    - Graceful error handling (adapter failures)

Test Cases:
    1. test_sqlite_json_type_detection() — Detect JSON column from sampling
    2. test_sqlite_json_schema_inference() — Sample-based schema inference
    3. test_sqlite_json_array_schema() — ARRAY element typing
    4. test_sqlite_non_json_column() — Non-JSON column → None
    5. test_sqlite_empty_table_json_schema() — Empty table handling
    6. test_sqlite_error_handling_graceful() — Adapter error → None
"""

from unittest.mock import MagicMock, patch

from util_bbdd.metadata.sqlite.types_advanced import query_json_column_schema

# ============================================================================
# TEST CASE 1: JSON Type Detection (Sampling-Based)
# ============================================================================


def test_sqlite_json_type_detection() -> None:
    """Verify JSON column detection from sampling (primary mechanism for SQLite).

    SQLite is typeless: we detect JSON columns by sampling and attempting
    to infer schema from actual values. This test verifies the basic detection.
    """
    # Setup: Mock adapter returns JSON rows
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    sample_rows = [
        ('{"user_id": 101, "event": "login"}',),
        ('{"user_id": 102, "event": "logout"}',),
        ('{"user_id": 103, "event": "login"}',),
    ]

    mock_adapter._execute_metadata_many.return_value = sample_rows

    # Execute
    result = query_json_column_schema("main", "events", "data", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert result["source"] == "sampling_inference"
    assert result["sample_count"] == 3
    assert "user_id" in result["properties"]
    assert "event" in result["properties"]
    assert set(result["required"]) == {"user_id", "event"}
    mock_adapter._execute_metadata_many.assert_called_once()


# ============================================================================
# TEST CASE 2: JSON Schema Inference
# ============================================================================


def test_sqlite_json_schema_inference() -> None:
    """Verify sample-based schema inference for JSON columns."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Diverse JSON samples with varying keys
    sample_rows = [
        ('{"id": 1, "name": "Alice", "active": true}',),
        ('{"id": 2, "name": "Bob", "active": false}',),
        ('{"id": 3, "name": "Charlie", "active": true}',),
    ]

    mock_adapter._execute_metadata_many.return_value = sample_rows

    # Execute
    result = query_json_column_schema("main", "users", "profile", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "object"
    assert "id" in result["properties"]
    assert "name" in result["properties"]
    assert "active" in result["properties"]
    # All three keys present in all samples → required
    assert set(result["required"]) == {"id", "name", "active"}
    # Type inference
    assert result["properties"]["id"]["type"] == "number"
    assert result["properties"]["name"]["type"] == "string"
    assert result["properties"]["active"]["type"] == "boolean"


# ============================================================================
# TEST CASE 3: JSON Array Schema
# ============================================================================


def test_sqlite_json_array_schema() -> None:
    """Verify schema inference for JSON arrays (not objects)."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # JSON array samples
    sample_rows = [
        ("[1, 2, 3]",),
        ("[4, 5, 6]",),
        ("[7, 8, 9]",),
    ]

    mock_adapter._execute_metadata_many.return_value = sample_rows

    # Execute
    result = query_json_column_schema("main", "data", "numbers", mock_adapter)

    # Assertions
    assert result is not None
    assert result["type"] == "array"
    assert result["element_type"] == "number"
    assert result["sample_count"] == 3


# ============================================================================
# TEST CASE 4: Non-JSON Column → None
# ============================================================================


def test_sqlite_non_json_column() -> None:
    """Verify graceful None return for non-JSON columns."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Plain text values (not JSON) - these get inferred as "string" type
    # which should be rejected as non-structured
    sample_rows = [
        ("just text",),
        ("more text",),
        ("plain string",),
    ]

    mock_adapter._execute_metadata_many.return_value = sample_rows

    # Execute
    result = query_json_column_schema("main", "logs", "message", mock_adapter)

    # Assertions
    assert result is None, "Expected None for non-JSON column (scalar type)"


# ============================================================================
# TEST CASE 5: Empty Table (No Data)
# ============================================================================


def test_sqlite_empty_table_json_schema() -> None:
    """Verify graceful handling for empty tables or columns."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # No samples (empty table or column)
    mock_adapter._execute_metadata_many.return_value = []

    # Execute with patched module logger
    with patch("util_bbdd.metadata.sqlite.types_advanced.logger") as mock_logger:
        result = query_json_column_schema("main", "empty_table", "data", mock_adapter)

        # Assertions
        assert result is None
        # Verify logging occurred (no data found)
        assert mock_logger.debug.called


# ============================================================================
# TEST CASE 6: Error Handling (Adapter Failure)
# ============================================================================


def test_sqlite_error_handling_graceful() -> None:
    """Verify graceful error handling when adapter raises exception.

    Tests that query_json_column_schema never propagates exceptions from adapter,
    always returning None with appropriate logging.
    """
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Adapter raises an exception (e.g., table not found, query error)
    mock_adapter._execute_metadata_many.side_effect = RuntimeError("Failed to query SQLite")

    # Execute with patched module logger
    with patch("util_bbdd.metadata.sqlite.types_advanced.logger") as mock_logger:
        result = query_json_column_schema("main", "missing_table", "data", mock_adapter)

        # Assertions
        assert result is None, "Expected None on adapter error"
        # Verify error was logged as warning
        assert mock_logger.warning.called

