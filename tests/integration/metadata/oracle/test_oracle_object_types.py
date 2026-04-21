"""Integration tests for Oracle OBJECT Type Introspection — Phase 4a.

Tests Phase 4a of v0.8.0 Type System improvements:
- Parse Oracle user-defined OBJECT types
- Extract field-level metadata (names, types, ordinal position, nullable, precision/scale)
- Handle nested OBJECT types, nullable fields, and precision/scale
- Graceful degradation on errors (return None instead of raising)
- Version compatibility (9i through 21c)

Test Cases:
    1. Simple OBJECT type (id INT, name VARCHAR2)
    2. OBJECT with nullable fields (mix NULL/NOT NULL)
    3. Nested OBJECT types (OBJECT containing OBJECT)
    4. OBJECT with precision/scale (NUMBER(10,2))
    5. Multiple OBJECT types in schema
    6. Type not found (graceful degradation)
    7. Malformed type name (invalid format)
    8. Version compatibility (9i/10g/11g+)
    9. Error handling graceful (adapter query fails)

Each test uses MagicMock for adapter (unittest.mock.MagicMock, no pytest-mock).
"""

from unittest.mock import MagicMock

from util_bbdd.metadata.oracle.types_advanced import (
    ObjectTypeField,
    ObjectTypeInfo,
    parse_object_type_structure,
)

# ============================================================================
# TEST CASE 1: Simple OBJECT Type (id INT, name VARCHAR2)
# ============================================================================


def test_parse_simple_object_type() -> None:
    """Verify simple OBJECT type parsing with basic fields.

    Tests parsing of a simple OBJECT type:
        CREATE TYPE customer_type AS OBJECT (
            id INT,
            name VARCHAR2(100)
        );
    """
    # Arrange: Mock adapter returns rows for CUSTOMER_TYPE
    # Row format: (type_name, owner, attr_name, attr_type, attr_no, nullable, precision, scale)
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("CUSTOMER_TYPE", "SYS", "id", "NUMBER", 1, False, 10, 0),
        ("CUSTOMER_TYPE", "SYS", "name", "VARCHAR2", 2, True, 100, None),
    ]

    # Act
    result = parse_object_type_structure("CUSTOMER_TYPE", mock_adapter)

    # Assert: Basic structure
    assert result is not None
    assert isinstance(result, ObjectTypeInfo)
    assert result.type_name == "CUSTOMER_TYPE"
    assert result.owner == "SYS"
    assert len(result.fields) == 2

    # Assert: Field 1 (id)
    assert result.fields[0].name == "id"
    assert result.fields[0].type_name == "NUMBER"
    assert result.fields[0].ordinal_position == 1
    assert result.fields[0].is_nullable is False
    assert result.fields[0].precision == 10
    assert result.fields[0].scale == 0

    # Assert: Field 2 (name)
    assert result.fields[1].name == "name"
    assert result.fields[1].type_name == "VARCHAR2"
    assert result.fields[1].ordinal_position == 2
    assert result.fields[1].is_nullable is True
    assert result.fields[1].precision == 100


# ============================================================================
# TEST CASE 2: OBJECT with Nullable Fields (Mix NULL/NOT NULL)
# ============================================================================


def test_parse_object_with_nullable_fields() -> None:
    """Verify handling of nullable vs not-null fields.

    Tests OBJECT with mixed nullable constraints:
        CREATE TYPE address_type AS OBJECT (
            street VARCHAR2(255) NOT NULL,
            city VARCHAR2(100),
            zip_code VARCHAR2(10) NOT NULL
        );
    """
    # Arrange
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("ADDRESS_TYPE", "SYS", "street", "VARCHAR2", 1, False, 255, None),
        ("ADDRESS_TYPE", "SYS", "city", "VARCHAR2", 2, True, 100, None),
        ("ADDRESS_TYPE", "SYS", "zip_code", "VARCHAR2", 3, False, 10, None),
    ]

    # Act
    result = parse_object_type_structure("ADDRESS_TYPE", mock_adapter)

    # Assert
    assert result is not None
    assert len(result.fields) == 3
    assert result.fields[0].is_nullable is False  # street NOT NULL
    assert result.fields[1].is_nullable is True  # city NULL
    assert result.fields[2].is_nullable is False  # zip_code NOT NULL


# ============================================================================
# TEST CASE 3: Nested OBJECT Types (OBJECT containing OBJECT)
# ============================================================================


def test_parse_nested_object() -> None:
    """Verify parsing of OBJECT containing nested OBJECT field.

    Tests OBJECT with nested type reference:
        CREATE TYPE person_type AS OBJECT (
            id NUMBER(10,0),
            name VARCHAR2(100),
            address address_type
        );
    """
    # Arrange: Mock adapter returns person_type with address_type nested field
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("PERSON_TYPE", "SYS", "id", "NUMBER", 1, False, 10, 0),
        ("PERSON_TYPE", "SYS", "name", "VARCHAR2", 2, True, 100, None),
        ("PERSON_TYPE", "SYS", "address", "ADDRESS_TYPE", 3, True, None, None),
    ]

    # Act
    result = parse_object_type_structure("PERSON_TYPE", mock_adapter)

    # Assert
    assert result is not None
    assert len(result.fields) == 3
    assert result.fields[2].name == "address"
    assert result.fields[2].type_name == "ADDRESS_TYPE"
    assert result.fields[2].is_nullable is True


# ============================================================================
# TEST CASE 4: OBJECT with Precision/Scale (NUMBER(10,2))
# ============================================================================


def test_parse_object_with_precision() -> None:
    """Verify handling of numeric precision and scale.

    Tests OBJECT with numeric precision/scale:
        CREATE TYPE product_type AS OBJECT (
            product_id NUMBER(10,0),
            price NUMBER(10,2),
            quantity NUMBER(5,0)
        );
    """
    # Arrange
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("PRODUCT_TYPE", "SYS", "product_id", "NUMBER", 1, False, 10, 0),
        ("PRODUCT_TYPE", "SYS", "price", "NUMBER", 2, False, 10, 2),
        ("PRODUCT_TYPE", "SYS", "quantity", "NUMBER", 3, False, 5, 0),
    ]

    # Act
    result = parse_object_type_structure("PRODUCT_TYPE", mock_adapter)

    # Assert
    assert result is not None
    assert len(result.fields) == 3

    # Field 1: product_id NUMBER(10,0)
    assert result.fields[0].precision == 10
    assert result.fields[0].scale == 0

    # Field 2: price NUMBER(10,2)
    assert result.fields[1].precision == 10
    assert result.fields[1].scale == 2

    # Field 3: quantity NUMBER(5,0)
    assert result.fields[2].precision == 5
    assert result.fields[2].scale == 0


# ============================================================================
# TEST CASE 5: Multiple OBJECT Types in Schema
# ============================================================================


def test_parse_multiple_objects_in_schema() -> None:
    """Verify parsing multiple distinct OBJECT types independently.

    Tests parsing of 3 separate types, each parsed distinctly.
    """
    # Type 1: SIMPLE_TYPE
    mock_adapter_1 = MagicMock()
    mock_adapter_1._execute_metadata_many.return_value = [
        ("SIMPLE_TYPE", "SYS", "id", "NUMBER", 1, False, 10, 0),
    ]

    # Type 2: COMPLEX_TYPE
    mock_adapter_2 = MagicMock()
    mock_adapter_2._execute_metadata_many.return_value = [
        ("COMPLEX_TYPE", "APP", "field1", "VARCHAR2", 1, True, 50, None),
        ("COMPLEX_TYPE", "APP", "field2", "DATE", 2, True, None, None),
        ("COMPLEX_TYPE", "APP", "field3", "NUMBER", 3, False, 15, 2),
    ]

    # Type 3: EXTENDED_TYPE
    mock_adapter_3 = MagicMock()
    mock_adapter_3._execute_metadata_many.return_value = [
        ("EXTENDED_TYPE", "ADMIN", "x", "INTEGER", 1, False, None, None),
        ("EXTENDED_TYPE", "ADMIN", "y", "INTEGER", 2, False, None, None),
        ("EXTENDED_TYPE", "ADMIN", "z", "FLOAT", 3, True, None, None),
    ]

    # Act
    result1 = parse_object_type_structure("SIMPLE_TYPE", mock_adapter_1)
    result2 = parse_object_type_structure("COMPLEX_TYPE", mock_adapter_2)
    result3 = parse_object_type_structure("EXTENDED_TYPE", mock_adapter_3)

    # Assert
    assert result1.type_name == "SIMPLE_TYPE"
    assert len(result1.fields) == 1

    assert result2.type_name == "COMPLEX_TYPE"
    assert result2.owner == "APP"
    assert len(result2.fields) == 3

    assert result3.type_name == "EXTENDED_TYPE"
    assert result3.owner == "ADMIN"
    assert len(result3.fields) == 3


# ============================================================================
# TEST CASE 6: OBJECT Type Not Found (Graceful Degradation)
# ============================================================================


def test_object_type_not_found() -> None:
    """Verify graceful degradation when type not found in dba_types.

    When a type doesn't exist, the adapter returns empty rows.
    Expected: parse_object_type_structure() returns None (not exception).
    """
    # Arrange: Adapter returns no rows (type not found)
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = []

    # Act
    result = parse_object_type_structure("NONEXISTENT_TYPE", mock_adapter)

    # Assert: Graceful degradation
    assert result is None

    # Verify logging: debug message for not found
    mock_adapter.logger.debug.assert_called()


# ============================================================================
# TEST CASE 7: Malformed Type Name (Invalid Format)
# ============================================================================


def test_malformed_type_name() -> None:
    """Verify handling of invalid type name formats.

    Invalid formats:
        - Too long (>30 chars)
        - Starts with number
        - Contains special chars (invalid)
        - Empty string
    """
    # Arrange
    mock_adapter = MagicMock()

    # Act & Assert: Type name too long (>30 chars)
    result = parse_object_type_structure("INVALID_TYPE_NAME_THAT_IS_WAY_TOO_LONG", mock_adapter)
    assert result is None

    # Act & Assert: Type name starts with number
    result = parse_object_type_structure("123_INVALID", mock_adapter)
    assert result is None

    # Act & Assert: Empty type name
    result = parse_object_type_structure("", mock_adapter)
    assert result is None

    # Verify logging: warning messages for invalid format
    assert mock_adapter.logger.warning.call_count >= 3


# ============================================================================
# TEST CASE 8: Version Compatibility (9i/10g/11g+)
# ============================================================================


def test_oracle_version_compatibility() -> None:
    """Verify parsing works across Oracle versions (9i, 10g, 11g, 12c+).

    Different Oracle versions may have slight differences in system catalog
    columns, but the core functionality should be version-agnostic.
    """
    # Arrange: Simulating Oracle 9i format (basic fields)
    mock_adapter_9i = MagicMock()
    mock_adapter_9i._execute_metadata_many.return_value = [
        ("LEGACY_TYPE", "SYS", "field1", "VARCHAR2", 1, True, 255, None),
    ]

    # Simulating Oracle 11g format (with precision/scale)
    mock_adapter_11g = MagicMock()
    mock_adapter_11g._execute_metadata_many.return_value = [
        ("MODERN_TYPE", "SYS", "id", "NUMBER", 1, False, 10, 0),
        ("MODERN_TYPE", "SYS", "amount", "DECIMAL", 2, False, 15, 2),
    ]

    # Act
    result_9i = parse_object_type_structure("LEGACY_TYPE", mock_adapter_9i)
    result_11g = parse_object_type_structure("MODERN_TYPE", mock_adapter_11g)

    # Assert
    assert result_9i is not None
    assert result_9i.type_name == "LEGACY_TYPE"
    assert len(result_9i.fields) == 1

    assert result_11g is not None
    assert result_11g.type_name == "MODERN_TYPE"
    assert len(result_11g.fields) == 2


# ============================================================================
# TEST CASE 9: Error Handling (Adapter Query Fails)
# ============================================================================


def test_error_handling_graceful() -> None:
    """Verify graceful error handling when adapter query fails.

    When adapter._execute_metadata_many() raises exception,
    parse_object_type_structure() should catch and return None.
    """
    # Arrange: Mock adapter raises exception
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.side_effect = Exception("Database connection failed")

    # Act
    result = parse_object_type_structure("TEST_TYPE", mock_adapter)

    # Assert: Graceful degradation
    assert result is None

    # Verify logging: warning with exception info
    mock_adapter.logger.warning.assert_called()


# ============================================================================
# TEST UTILITIES: ObjectTypeField.to_dict() and ObjectTypeInfo.to_dict()
# ============================================================================


def test_object_type_field_to_dict() -> None:
    """Verify ObjectTypeField serialization to dict.

    Tests the to_dict() method for proper API response formatting.
    """
    # Arrange
    field = ObjectTypeField(
        name="id",
        type_name="NUMBER",
        ordinal_position=1,
        is_nullable=False,
        precision=10,
        scale=0,
    )

    # Act
    result = field.to_dict()

    # Assert
    assert result["name"] == "id"
    assert result["type"] == "NUMBER"
    assert result["ordinal_position"] == 1
    assert result["nullable"] is False
    assert result["precision"] == 10
    assert result["scale"] == 0


def test_object_type_info_to_dict() -> None:
    """Verify ObjectTypeInfo serialization to dict.

    Tests the to_dict() method for API response with nested fields.
    """
    # Arrange
    fields = [
        ObjectTypeField("id", "NUMBER", 1, False, 10, 0),
        ObjectTypeField("name", "VARCHAR2", 2, True, 100, None),
    ]
    info = ObjectTypeInfo(type_name="CUSTOMER_TYPE", owner="SYS", fields=fields)

    # Act
    result = info.to_dict()

    # Assert
    assert result["type_name"] == "CUSTOMER_TYPE"
    assert result["owner"] == "SYS"
    assert len(result["fields"]) == 2
    assert result["fields"][0]["name"] == "id"
    assert result["fields"][1]["name"] == "name"
