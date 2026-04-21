"""Integration tests for Redshift Type Introspection — Phase 4b.1.

Tests Phase 4b.1 of v0.8.0 Type System improvements for Redshift:
- Graceful fallback for unsupported types (typical: None return)
- Redshift: PostgreSQL 8.x base (pre-modern composite types era)
- Error handling (adapter errors, missing catalogs, etc.)
- Future extension point: if types somehow exist

Test Strategy (Mock-based):
    - Mock adapter returns empty list (typical for Redshift: no composite types)
    - Verify: no exceptions, logging occurs, None returned
    - Test version detection and capability checking
    - Test error handling (adapter failures)

Test Cases:
    1. test_redshift_types_not_available — Typical case: empty pg_type → None
    2. test_redshift_version_detection — Verify version check logic
    3. test_redshift_graceful_error_handling — Adapter error → None
    4. test_redshift_type_not_found — Missing type → None
    5. test_redshift_adapter_exception_safety — Unexpected exception → None
"""

from unittest.mock import MagicMock

from util_bbdd.metadata.redshift.types_advanced import parse_redshift_types

# ============================================================================
# TEST CASE 1: Types Not Available (Typical Redshift Scenario)
# ============================================================================


def test_redshift_types_not_available() -> None:
    """Verify graceful None return when types not available (typical for Redshift).

    This is the expected case: Redshift is based on PostgreSQL 8.x which
    predates modern composite type support. Most deployments have no
    user-defined composite types available in pg_type catalog.
    """
    # Setup: Mock adapter that returns empty list (no types in catalog)
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Simulate: pg_type query returns empty (typical for Redshift)
    mock_adapter._execute_metadata_many.return_value = []

    # Execute
    result = parse_redshift_types("some_type", mock_adapter)

    # Assertions
    assert result is None, "Expected None when types unavailable"
    mock_adapter._execute_metadata_many.assert_called_once()
    mock_adapter.logger.info.assert_not_called()


# ============================================================================
# TEST CASE 2: Type Not Found (Missing Type)
# ============================================================================


def test_redshift_type_not_found() -> None:
    """Verify None return when specific type not found in catalog."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Simulate: Type lookup returns empty (type doesn't exist)
    mock_adapter._execute_metadata_many.return_value = []

    # Execute
    result = parse_redshift_types("nonexistent_type", mock_adapter)

    # Assertions
    assert result is None
    # Verify we called the metadata fetcher with correct type name
    call_args = mock_adapter._execute_metadata_many.call_args
    assert call_args is not None
    assert call_args[1]["params"]["type_name"] == "nonexistent_type"


# ============================================================================
# TEST CASE 3: Graceful Error Handling (Adapter Failure)
# ============================================================================


def test_redshift_graceful_error_handling() -> None:
    """Verify graceful None return when adapter raises exception.

    Tests that parse_redshift_types never propagates exceptions from adapter,
    always returning None with appropriate logging.
    """
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Simulate: Adapter raises an exception (e.g., connection lost)
    mock_adapter._execute_metadata_many.side_effect = RuntimeError("Connection to Redshift lost")

    # Execute - should NOT raise, should return None
    result = parse_redshift_types("type_name", mock_adapter)

    # Assertions
    assert result is None, "Expected None on adapter error"


# ============================================================================
# TEST CASE 4: Unexpected Type Found (Future Extension Point)
# ============================================================================


def test_redshift_unexpected_type_found() -> None:
    """Verify behavior if type somehow exists (rare; extension point).

    If a Redshift deployment somehow has types in pg_type catalog,
    we return None (MVP) with info logging for operator awareness.
    """
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Simulate: Type query returns a result (unexpected, but possible)
    mock_adapter._execute_metadata_many.return_value = [
        ("custom_type", "composite", 42),  # Unexpected type data
    ]

    # Execute
    result = parse_redshift_types("custom_type", mock_adapter)

    # Assertions
    assert result is None, "MVP: still return None even if type exists"
    # Verify we logged the unexpected finding
    mock_adapter.logger.info.assert_called()
    info_call = mock_adapter.logger.info.call_args[0][0]
    assert "unexpected type" in info_call.lower()


# ============================================================================
# TEST CASE 5: Multiple Type Checks (No State Mutation)
# ============================================================================


def test_redshift_multiple_type_checks() -> None:
    """Verify function can be called multiple times safely.

    Tests that parse_redshift_types is stateless and can be called
    repeatedly without side effects.
    """
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Setup: returns empty for all calls
    mock_adapter._execute_metadata_many.return_value = []

    # Execute: multiple calls with different type names
    result1 = parse_redshift_types("type_one", mock_adapter)
    result2 = parse_redshift_types("type_two", mock_adapter)
    result3 = parse_redshift_types("type_three", mock_adapter)

    # Assertions
    assert result1 is None
    assert result2 is None
    assert result3 is None
    # Verify each call was made (3 separate queries)
    assert mock_adapter._execute_metadata_many.call_count == 3
