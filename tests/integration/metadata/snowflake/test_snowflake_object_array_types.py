"""Integration tests for Snowflake OBJECT & ARRAY Types — Phase 3.

Tests Phase 3 of v0.8.0 Type System improvements:
- Parse Snowflake OBJECT<k1: T1, k2: T2> syntax
- Parse Snowflake ARRAY<T> syntax
- Handle nested OBJECT and ARRAY types
- Handle edge cases (case sensitivity, malformed syntax, etc.)

Test Cases:
    1. Simple OBJECT<k: T>
    2. OBJECT with 5+ fields
    3. Nested OBJECT
    4. Simple ARRAY<T>
    5. ARRAY<OBJECT<...>>
    6. ARRAY<ARRAY<...>> (deeply nested)
    7. Mixed OBJECT + ARRAY + primitives
    8. Snowflake function return types (OBJECT/ARRAY)
    9. Case sensitivity handling (Snowflake uppercases)
    10. Error handling (malformed type syntax)
"""

from unittest.mock import MagicMock

from util_bbdd.metadata.snowflake.types_advanced import (
    parse_snowflake_array_syntax,
    parse_snowflake_object_syntax,
    query_snowflake_column_schema,
)

# ============================================================================
# TEST CASE 1: Simple OBJECT<k: T>
# ============================================================================


def test_parse_simple_object() -> None:
    """Verify simple OBJECT type parsing."""
    type_str = "OBJECT<customer_id: INTEGER, name: VARCHAR>"

    result = parse_snowflake_object_syntax(type_str)

    assert result is not None
    assert result["type"] == "object"
    assert "customer_id" in result["properties"]
    assert "name" in result["properties"]
    assert result["properties"]["customer_id"]["type"] == "integer"
    assert result["properties"]["name"]["type"] == "string"


# ============================================================================
# TEST CASE 2: OBJECT with 5+ fields
# ============================================================================


def test_parse_object_with_many_fields() -> None:
    """Verify OBJECT with multiple fields."""
    type_str = """OBJECT<
        id: INTEGER,
        name: VARCHAR,
        email: VARCHAR,
        created_at: TIMESTAMP_NTZ,
        updated_at: TIMESTAMP_NTZ,
        is_active: BOOLEAN,
        metadata: VARIANT
    >"""

    result = parse_snowflake_object_syntax(type_str)

    assert result is not None
    assert result["type"] == "object"
    # Should have 7 properties
    assert len(result["properties"]) == 7
    assert "id" in result["properties"]
    assert "metadata" in result["properties"]
    assert result["properties"]["is_active"]["type"] == "boolean"


# ============================================================================
# TEST CASE 3: Nested OBJECT
# ============================================================================


def test_parse_nested_object() -> None:
    """Verify nested OBJECT type parsing."""
    type_str = "OBJECT<id: INTEGER, address: OBJECT<street: VARCHAR, city: VARCHAR, zip: VARCHAR>>"

    result = parse_snowflake_object_syntax(type_str)

    assert result is not None
    assert result["type"] == "object"
    assert "id" in result["properties"]
    assert "address" in result["properties"]
    # address should be object type
    address_type = result["properties"]["address"]["type"]
    assert address_type == "object"
    # address should have nested properties
    assert "properties" in result["properties"]["address"]
    assert "street" in result["properties"]["address"]["properties"]


# ============================================================================
# TEST CASE 4: Simple ARRAY<T>
# ============================================================================


def test_parse_simple_array() -> None:
    """Verify simple ARRAY type parsing."""
    type_str = "ARRAY<VARCHAR>"

    result = parse_snowflake_array_syntax(type_str)

    assert result is not None
    assert result["type"] == "array"
    assert "element_type" in result
    assert result["element_type"]["type"] == "string"


# ============================================================================
# TEST CASE 5: ARRAY<OBJECT<...>>
# ============================================================================


def test_parse_array_of_objects() -> None:
    """Verify ARRAY containing OBJECT types."""
    type_str = "ARRAY<OBJECT<id: INTEGER, status: VARCHAR>>"

    result = parse_snowflake_array_syntax(type_str)

    assert result is not None
    assert result["type"] == "array"
    assert result["element_type"]["type"] == "object"
    # Verify nested object properties
    assert "id" in result["element_type"]["properties"]
    assert "status" in result["element_type"]["properties"]


# ============================================================================
# TEST CASE 6: ARRAY<ARRAY<...>> (Deeply Nested)
# ============================================================================


def test_parse_array_of_arrays() -> None:
    """Verify deeply nested ARRAY<ARRAY<T>>."""
    type_str = "ARRAY<ARRAY<VARCHAR>>"

    result = parse_snowflake_array_syntax(type_str)

    assert result is not None
    assert result["type"] == "array"
    # Element type is array
    assert result["element_type"]["type"] == "array"
    # Inner element type is string
    assert result["element_type"]["element_type"]["type"] == "string"


# ============================================================================
# TEST CASE 7: Mixed OBJECT + ARRAY + Primitives
# ============================================================================


def test_parse_complex_mixed_type() -> None:
    """Verify complex OBJECT with mixed nested types."""
    type_str = """OBJECT<
        id: INTEGER,
        name: VARCHAR,
        tags: ARRAY<VARCHAR>,
        metadata: OBJECT<key: VARCHAR, value: VARIANT>,
        scores: ARRAY<DOUBLE>
    >"""

    result = parse_snowflake_object_syntax(type_str)

    assert result is not None
    assert result["type"] == "object"
    # Check primitive field
    assert result["properties"]["id"]["type"] == "integer"
    assert result["properties"]["name"]["type"] == "string"
    # Check array field
    assert result["properties"]["tags"]["type"] == "array"
    assert result["properties"]["tags"]["element_type"]["type"] == "string"
    # Check nested object field
    assert result["properties"]["metadata"]["type"] == "object"
    # Check array of doubles
    assert result["properties"]["scores"]["type"] == "array"
    assert result["properties"]["scores"]["element_type"]["type"] == "float"


# ============================================================================
# TEST CASE 8: Snowflake Function Return Types
# ============================================================================


def test_parse_function_return_object_type() -> None:
    """Verify parsing of Snowflake function return types (OBJECT/ARRAY)."""
    # Snowflake UDF return types like: OBJECT<result: INTEGER, status: VARCHAR>
    type_str = "OBJECT<result: INTEGER, status: VARCHAR, error_message: VARCHAR>"

    result = parse_snowflake_object_syntax(type_str)

    assert result is not None
    assert result["type"] == "object"
    assert len(result["properties"]) == 3


def test_parse_function_return_array_type() -> None:
    """Verify parsing of ARRAY function return types."""
    # Array return type: ARRAY<OBJECT<...>>
    type_str = "ARRAY<OBJECT<id: INTEGER, data: VARCHAR>>"

    result = parse_snowflake_array_syntax(type_str)

    assert result is not None
    assert result["type"] == "array"
    assert result["element_type"]["type"] == "object"


# ============================================================================
# TEST CASE 9: Case Sensitivity Handling
# ============================================================================


def test_case_sensitivity_lowercase() -> None:
    """Verify parsing with lowercase OBJECT/ARRAY keywords."""
    type_str = "object<id: integer, name: varchar>"

    result = parse_snowflake_object_syntax(type_str)

    assert result is not None
    assert result["type"] == "object"
    assert result["properties"]["id"]["type"] == "integer"


def test_case_sensitivity_uppercase() -> None:
    """Verify parsing with uppercase OBJECT/ARRAY keywords."""
    type_str = "OBJECT<ID: INTEGER, NAME: VARCHAR>"

    result = parse_snowflake_object_syntax(type_str)

    assert result is not None
    assert result["type"] == "object"
    # Property names should be normalized to lowercase
    assert "id" in result["properties"]
    assert "name" in result["properties"]


def test_case_sensitivity_mixed() -> None:
    """Verify parsing with mixed case keywords."""
    type_str = "ObJeCt<Id: InTeGeR, Name: VaRcHaR>"

    result = parse_snowflake_object_syntax(type_str)

    assert result is not None
    assert result["type"] == "object"
    assert "id" in result["properties"]


# ============================================================================
# TEST CASE 10: Error Handling (Malformed Syntax)
# ============================================================================


def test_error_handling_malformed_object() -> None:
    """Verify graceful handling of malformed OBJECT syntax."""
    # Missing closing bracket
    type_str = "OBJECT<id: INTEGER, name: VARCHAR"

    result = parse_snowflake_object_syntax(type_str)

    # Should return None (graceful degradation)
    assert result is None


def test_error_handling_invalid_property_format() -> None:
    """Verify handling of invalid property format."""
    # Invalid property format (missing colon)
    type_str = "OBJECT<id INTEGER, name VARCHAR>"

    result = parse_snowflake_object_syntax(type_str)

    # Should return None or empty properties
    assert result is None or len(result.get("properties", {})) == 0


def test_error_handling_empty_object() -> None:
    """Verify handling of empty OBJECT."""
    type_str = "OBJECT<>"

    result = parse_snowflake_object_syntax(type_str)

    # Should return None for empty object
    assert result is None


def test_error_handling_empty_array() -> None:
    """Verify handling of malformed ARRAY with no element type."""
    type_str = "ARRAY<>"

    result = parse_snowflake_array_syntax(type_str)

    # Should return None
    assert result is None


def test_error_handling_non_object_type() -> None:
    """Verify handling of non-OBJECT type string."""
    type_str = "INTEGER"

    result = parse_snowflake_object_syntax(type_str)

    # Should return None (not an OBJECT)
    assert result is None


def test_error_handling_non_array_type() -> None:
    """Verify handling of non-ARRAY type string."""
    type_str = "VARCHAR"

    result = parse_snowflake_array_syntax(type_str)

    # Should return None (not an ARRAY)
    assert result is None


# ============================================================================
# TEST CASE 11: Manager Interface Integration
# ============================================================================


def test_query_snowflake_column_schema_object() -> None:
    """Verify integration with manager adapter (OBJECT type)."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Mock adapter returns column type from INFORMATION_SCHEMA
    mock_adapter._execute_metadata_many.return_value = [
        ("OBJECT<customer_id: INTEGER, name: VARCHAR>",),
    ]

    result = query_snowflake_column_schema("sales", "customers", "customer_data", mock_adapter)

    assert result is not None
    assert result["type"] == "object"
    assert result["source"] == "type_definition"
    assert "customer_id" in result["properties"]


def test_query_snowflake_column_schema_array() -> None:
    """Verify integration with manager adapter (ARRAY type)."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Mock adapter returns column type
    mock_adapter._execute_metadata_many.return_value = [
        ("ARRAY<OBJECT<id: INTEGER, status: VARCHAR>>",),
    ]

    result = query_snowflake_column_schema("analytics", "events", "event_list", mock_adapter)

    assert result is not None
    assert result["type"] == "array"
    assert result["element_type"]["type"] == "object"
    assert result["source"] == "type_definition"


def test_query_snowflake_column_schema_primitive() -> None:
    """Verify non-OBJECT/ARRAY types return None."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Mock adapter returns primitive type
    mock_adapter._execute_metadata_many.return_value = [
        ("VARCHAR",),
    ]

    result = query_snowflake_column_schema("db", "table", "col", mock_adapter)

    # Should return None (not OBJECT/ARRAY)
    assert result is None


def test_query_snowflake_column_schema_null() -> None:
    """Verify handling of NULL/empty column type."""
    mock_adapter = MagicMock()
    mock_adapter.logger = MagicMock()

    # Mock adapter returns NULL
    mock_adapter._execute_metadata_many.return_value = [
        (None,),
    ]

    result = query_snowflake_column_schema("db", "table", "col", mock_adapter)

    # Should return None
    assert result is None
