"""Integration tests for PostgreSQL Composite Type Introspection — Phase 1.

Tests Phase 1 of v0.8.0 Type System improvements:
- Parse PostgreSQL user-defined composite types
- Extract field-level metadata (names, types, ordinal position)
- Handle nested composites and edge cases

Test Cases:
    1. Simple composite type (3 fields)
    2. Nested composite type
    3. Composite with array field
    4. Nullable vs not-null fields
    5. Multiple composites in schema
    6. Composite with domain types
    7. Error handling (type not found)
    8. Performance (50+ fields)
"""

from unittest.mock import MagicMock

from util_bbdd.metadata.postgresql.types_advanced import (
    CompositeTypeInfo,
    get_composite_types,
    parse_composite_type_structure,
)

# ============================================================================
# TEST CASE 1: Simple Composite Type (3 fields)
# ============================================================================


def test_parse_simple_composite_type() -> None:
    """Verify simple composite type parsing."""
    # Setup: Mock adapter returns rows for address_type (street, city, zip)
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("street", 1043, "varchar", 1, "postgres", False, 255, None, None),
        ("city", 1043, "varchar", 2, "postgres", False, 100, None, None),
        ("zip", 1043, "varchar", 3, "postgres", False, 10, None, None),
    ]

    # Execute
    result = parse_composite_type_structure("public", "address_type", mock_adapter)

    # Assert
    assert result is not None
    assert isinstance(result, CompositeTypeInfo)
    assert result.name == "address_type"
    assert result.schema == "public"
    assert len(result.fields) == 3
    assert result.fields[0].name == "street"
    assert result.fields[0].type_name == "varchar"
    assert result.fields[0].max_length == 255
    assert result.fields[1].name == "city"
    assert result.fields[2].name == "zip"
    assert result.fields[2].max_length == 10


def test_parse_simple_composite_to_dict() -> None:
    """Verify composite type dict serialization."""
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("street", 1043, "varchar", 1, "postgres", False, 255, None, None),
        ("city", 1043, "varchar", 2, "postgres", False, 100, None, None),
    ]

    result = parse_composite_type_structure("public", "address_type", mock_adapter)

    # Convert to dict
    result_dict = result.to_dict()

    assert result_dict["name"] == "address_type"
    assert result_dict["schema"] == "public"
    assert len(result_dict["fields"]) == 2
    assert result_dict["fields"][0]["name"] == "street"
    assert result_dict["fields"][0]["type"] == "varchar"


# ============================================================================
# TEST CASE 2: Nested Composite Type
# ============================================================================


def test_parse_nested_composite_type() -> None:
    """Verify nested composite type (person with address field)."""
    # Mock: person_type (name varchar, age integer, address address_type)
    # Note: address field type would be the OID of address_type
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("name", 1043, "varchar", 1, "postgres", False, 255, None, None),
        ("age", 23, "integer", 2, "postgres", False, None, None, None),
        ("address", 100_000, "address_type", 3, "postgres", False, None, None, None),
    ]

    result = parse_composite_type_structure("public", "person_type", mock_adapter)

    assert result is not None
    assert len(result.fields) == 3
    assert result.fields[2].name == "address"
    assert result.fields[2].type_name == "address_type"


# ============================================================================
# TEST CASE 3: Composite with ARRAY Field
# ============================================================================


def test_composite_with_array_field() -> None:
    """Verify composite containing integer[] field."""
    # tag_list (title varchar, tags integer[])
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("title", 1043, "varchar", 1, "postgres", False, 255, None, None),
        ("tags", 1007, "integer", 2, "postgres", True, None, None, None),  # is_array=True
    ]

    result = parse_composite_type_structure("public", "tag_list", mock_adapter)

    assert result is not None
    assert len(result.fields) == 2
    assert result.fields[1].name == "tags"
    assert result.fields[1].is_array is True


# ============================================================================
# TEST CASE 4: Nullable Fields
# ============================================================================


def test_composite_nullable_fields() -> None:
    """Verify all composite fields tracked as nullable (default PostgreSQL)."""
    # PostgreSQL: composite fields are nullable by default
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("id", 23, "integer", 1, "postgres", False, None, None, None),
        ("name", 1043, "varchar", 2, "postgres", False, 255, None, None),
        ("email", 1043, "varchar", 3, "postgres", False, 255, None, None),
    ]

    result = parse_composite_type_structure("public", "user_record", mock_adapter)

    assert result is not None
    # All fields should be nullable
    for field in result.fields:
        assert field.is_nullable is True


# ============================================================================
# TEST CASE 5: Multiple Composites in Schema
# ============================================================================


def test_get_composite_types_multiple() -> None:
    """Verify listing multiple composite types in schema."""
    mock_adapter = MagicMock()

    # First call: list composite types
    mock_adapter._execute_metadata_many.side_effect = [
        # List composite types query result
        [
            ("address_type", "public", "postgres"),
            ("contact_type", "public", "postgres"),
            ("location_type", "public", "postgres"),
        ],
        # Detail queries for each type (we'll short-circuit with empty results)
        [],
        [],
        [],
    ]

    result = get_composite_types("public", mock_adapter)

    # Should return list (though details empty due to mock setup)
    assert isinstance(result, list)


# ============================================================================
# TEST CASE 6: Composite with Domain Types
# ============================================================================


def test_composite_with_domain_field() -> None:
    """Verify composite field using domain type (custom type)."""
    # email_record (primary email_domain, secondary email_domain)
    # where email_domain is a domain type based on varchar
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("primary", 100_001, "email_domain", 1, "postgres", False, 255, None, None),
        ("secondary", 100_001, "email_domain", 2, "postgres", False, 255, None, None),
    ]

    result = parse_composite_type_structure("public", "email_record", mock_adapter)

    assert result is not None
    assert len(result.fields) == 2
    assert result.fields[0].type_name == "email_domain"


# ============================================================================
# TEST CASE 7: Error Handling (Type Not Found)
# ============================================================================


def test_parse_nonexistent_composite_type() -> None:
    """Verify None returned for non-existent composite type."""
    # Mock: empty result (type not found)
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = []

    result = parse_composite_type_structure("public", "nonexistent_type", mock_adapter)

    assert result is None


def test_parse_composite_with_database_error() -> None:
    """Verify graceful error handling on database error."""
    # Mock: raise exception
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.side_effect = Exception("Connection lost")

    result = parse_composite_type_structure("public", "address_type", mock_adapter)

    assert result is None
    # Logger should have error message
    mock_adapter.logger.error.assert_called()


# ============================================================================
# TEST CASE 8: Performance (Composite with 50+ Fields)
# ============================================================================


def test_parse_composite_with_many_fields() -> None:
    """Verify handling of composite type with 50+ fields."""
    # Generate 60 fields
    rows = [
        (
            f"field_{i:03d}",
            1043,  # varchar OID
            "varchar",
            i + 1,
            "postgres",
            False,
            255,
            None,
            None,
        )
        for i in range(60)
    ]
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = rows

    result = parse_composite_type_structure("public", "huge_record", mock_adapter)

    assert result is not None
    assert len(result.fields) == 60
    # Verify ordinal positions correct
    for i, field in enumerate(result.fields):
        assert field.ordinal_position == i + 1
