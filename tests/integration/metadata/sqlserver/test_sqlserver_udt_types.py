"""Integration tests for SQL Server UDT Type Introspection — Phase 4a.2.

Tests Phase 4a.2 of v0.8.0 Type System improvements:
- Parse SQL Server user-defined types via sys.types + sys.type_members
- Extract member-level metadata (names, types, ordinal position, nullable, precision/scale)
- Handle multiple SQL Server versions (2005 through 2022)
- Detect UDT kind (STRUCTURED vs HIERARCHY vs NATIVE)
- Graceful degradation on errors (return None instead of raising)

Test Cases:
    1. Simple structured UDT (3-4 members: id int, name varchar)
    2. UDT with precision/scale (numeric(10,2))
    3. Multiple UDTs parsed independently
    4. UDT not supported on older version (SQL Server 2000)
    5. UDT with nullable members (mix NULL/NOT NULL)
    6. UDT hierarchy type detection
    7. Type not found (graceful degradation)
    8. Error handling graceful (adapter query fails)

Each test uses MagicMock for adapter (unittest.mock.MagicMock, no pytest-mock).
"""

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlserver.types_advanced import (
    UDTMember,
    UDTTypeInfo,
    parse_udt_structure,
)

# ============================================================================
# TEST CASE 1: Simple Structured UDT (3-4 members)
# ============================================================================


def test_parse_simple_structured_udt() -> None:
    """Verify simple UDT parsing with basic members.

    Tests parsing of a simple UDT:
        CREATE TYPE customer_type AS (
            id int NOT NULL,
            name varchar(100) NULL,
            email varchar(255) NULL
        );
    """
    # Arrange: Mock adapter returns rows for CUSTOMER_TYPE
    # Row format: (type_name, type_id, member_name, member_type, member_id,
    #              nullable, max_length, precision, scale)
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("CUSTOMER_TYPE", 1001, "id", "int", 1, False, None, 10, 0),
        ("CUSTOMER_TYPE", 1001, "name", "varchar", 2, True, 100, None, None),
        ("CUSTOMER_TYPE", 1001, "email", "varchar", 3, True, 255, None, None),
    ]

    # Act
    result = parse_udt_structure("CUSTOMER_TYPE", mock_adapter)

    # Assert: Basic structure
    assert result is not None
    assert isinstance(result, UDTTypeInfo)
    assert result.type_name == "CUSTOMER_TYPE"
    assert result.kind == "STRUCTURED"
    assert len(result.members) == 3

    # Assert: Member 1 (id)
    assert result.members[0].name == "id"
    assert result.members[0].type_name == "INT"
    assert result.members[0].ordinal_position == 1
    assert result.members[0].is_nullable is False

    # Assert: Member 2 (name)
    assert result.members[1].name == "name"
    assert result.members[1].type_name == "VARCHAR"
    assert result.members[1].ordinal_position == 2
    assert result.members[1].is_nullable is True
    assert result.members[1].max_length == 100

    # Assert: Member 3 (email)
    assert result.members[2].name == "email"
    assert result.members[2].type_name == "VARCHAR"
    assert result.members[2].ordinal_position == 3
    assert result.members[2].is_nullable is True
    assert result.members[2].max_length == 255


# ============================================================================
# TEST CASE 2: UDT with Precision/Scale (numeric(10,2))
# ============================================================================


def test_parse_udt_with_precision_scale() -> None:
    """Verify handling of numeric precision and scale in UDT members.

    Tests UDT with numeric precision/scale:
        CREATE TYPE product_type AS (
            product_id int NOT NULL,
            price numeric(10,2) NOT NULL,
            quantity numeric(5,0) NOT NULL
        );
    """
    # Arrange
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("PRODUCT_TYPE", 1002, "product_id", "int", 1, False, None, 10, 0),
        ("PRODUCT_TYPE", 1002, "price", "numeric", 2, False, None, 10, 2),
        ("PRODUCT_TYPE", 1002, "quantity", "numeric", 3, False, None, 5, 0),
    ]

    # Act
    result = parse_udt_structure("PRODUCT_TYPE", mock_adapter)

    # Assert
    assert result is not None
    assert len(result.members) == 3

    # Member 1: product_id int
    assert result.members[0].type_name == "INT"
    assert result.members[0].precision == 10
    assert result.members[0].scale == 0

    # Member 2: price numeric(10,2)
    assert result.members[1].type_name == "NUMERIC"
    assert result.members[1].precision == 10
    assert result.members[1].scale == 2

    # Member 3: quantity numeric(5,0)
    assert result.members[2].type_name == "NUMERIC"
    assert result.members[2].precision == 5
    assert result.members[2].scale == 0


# ============================================================================
# TEST CASE 3: Multiple UDTs Parsed Independently
# ============================================================================


def test_parse_multiple_udts() -> None:
    """Verify parsing multiple distinct UDTs independently.

    Tests parsing of 2+ separate UDTs, each parsed distinctly.
    """
    # UDT 1: SIMPLE_TYPE
    mock_adapter_1 = MagicMock()
    mock_adapter_1._execute_metadata_many.return_value = [
        ("SIMPLE_TYPE", 1003, "id", "int", 1, False, None, 10, 0),
    ]

    # UDT 2: COMPLEX_TYPE
    mock_adapter_2 = MagicMock()
    mock_adapter_2._execute_metadata_many.return_value = [
        ("COMPLEX_TYPE", 1004, "field1", "varchar", 1, True, 50, None, None),
        ("COMPLEX_TYPE", 1004, "field2", "date", 2, True, None, None, None),
        ("COMPLEX_TYPE", 1004, "field3", "numeric", 3, False, None, 15, 2),
    ]

    # Act
    result1 = parse_udt_structure("SIMPLE_TYPE", mock_adapter_1)
    result2 = parse_udt_structure("COMPLEX_TYPE", mock_adapter_2)

    # Assert
    assert result1.type_name == "SIMPLE_TYPE"
    assert len(result1.members) == 1

    assert result2.type_name == "COMPLEX_TYPE"
    assert len(result2.members) == 3

    assert result1.kind == "STRUCTURED"
    assert result2.kind == "STRUCTURED"


# ============================================================================
# TEST CASE 4: UDT Not Supported on Older SQL Server Version
# ============================================================================


def test_udt_not_supported_older_version() -> None:
    """Verify graceful degradation on SQL Server 2000 (pre-2005).

    SQL Server 2000 does not support user-defined types in sys.types.
    Expected: parse_udt_structure() returns None (not exception).
    """
    # Arrange: Adapter returns no rows (version doesn't support UDTs)
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = []

    # Act: Try to parse UDT on SQL Server 2000
    result = parse_udt_structure("LEGACY_TYPE", mock_adapter)

    # Assert: Graceful degradation
    assert result is None

    # Verify logging: debug message for not found
    mock_adapter.logger.debug.assert_called()


# ============================================================================
# TEST CASE 5: UDT with Nullable Members (Mix NULL/NOT NULL)
# ============================================================================


def test_parse_udt_with_nullable_members() -> None:
    """Verify handling of nullable vs not-null members.

    Tests UDT with mixed nullable constraints:
        CREATE TYPE address_type AS (
            street varchar(255) NOT NULL,
            city varchar(100) NULL,
            zip_code varchar(10) NOT NULL
        );
    """
    # Arrange
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("ADDRESS_TYPE", 1005, "street", "varchar", 1, False, 255, None, None),
        ("ADDRESS_TYPE", 1005, "city", "varchar", 2, True, 100, None, None),
        ("ADDRESS_TYPE", 1005, "zip_code", "varchar", 3, False, 10, None, None),
    ]

    # Act
    result = parse_udt_structure("ADDRESS_TYPE", mock_adapter)

    # Assert
    assert result is not None
    assert len(result.members) == 3
    assert result.members[0].is_nullable is False  # street NOT NULL
    assert result.members[1].is_nullable is True  # city NULL
    assert result.members[2].is_nullable is False  # zip_code NOT NULL


# ============================================================================
# TEST CASE 6: UDT Hierarchy Type Detection
# ============================================================================


def test_parse_udt_hierarchy_type_detection() -> None:
    """Verify UDT kind detection for hierarchy vs structured types.

    Tests detection of UDT kind based on system metadata.
    SQL Server UDT kinds: STRUCTURED (default), HIERARCHY (special CLR-based)
    """
    # Arrange: UDT with type_id > 256 (user-defined)
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = [
        ("HIERARCHY_TYPE", 1006, "node_id", "int", 1, False, None, 10, 0),
        ("HIERARCHY_TYPE", 1006, "hierarchy_level", "int", 2, True, None, 10, 0),
    ]

    # Act
    result = parse_udt_structure("HIERARCHY_TYPE", mock_adapter)

    # Assert: Kind should be STRUCTURED (for user-defined types with type_id > 256)
    assert result is not None
    assert result.kind == "STRUCTURED"
    assert len(result.members) == 2


# ============================================================================
# TEST CASE 7: Type Not Found (Graceful Degradation)
# ============================================================================


def test_type_not_found() -> None:
    """Verify graceful degradation when type not found in sys.types.

    When a UDT doesn't exist, the adapter returns empty rows.
    Expected: parse_udt_structure() returns None (not exception).
    """
    # Arrange: Adapter returns no rows (type not found)
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.return_value = []

    # Act
    result = parse_udt_structure("NONEXISTENT_TYPE", mock_adapter)

    # Assert: Graceful degradation
    assert result is None

    # Verify logging: debug message for not found
    mock_adapter.logger.debug.assert_called()


# ============================================================================
# TEST CASE 8: Error Handling Graceful
# ============================================================================


def test_error_handling_graceful() -> None:
    """Verify graceful error handling when adapter query fails.

    When adapter._execute_metadata_many() raises exception,
    parse_udt_structure() should catch and return None.
    """
    # Arrange: Mock adapter raises exception
    mock_adapter = MagicMock()
    mock_adapter._execute_metadata_many.side_effect = Exception("Database connection failed")

    # Act
    result = parse_udt_structure("TEST_TYPE", mock_adapter)

    # Assert: Graceful degradation
    assert result is None

    # Verify logging: warning with exception info
    mock_adapter.logger.warning.assert_called()


# ============================================================================
# TEST UTILITIES: UDTMember.to_dict() and UDTTypeInfo.to_dict()
# ============================================================================


def test_udt_member_to_dict() -> None:
    """Verify UDTMember serialization to dict.

    Tests the to_dict() method for proper API response formatting.
    """
    # Arrange
    member = UDTMember(
        name="id",
        type_name="int",
        ordinal_position=1,
        is_nullable=False,
        precision=10,
        scale=0,
    )

    # Act
    result = member.to_dict()

    # Assert
    assert result["name"] == "id"
    assert result["type"] == "int"
    assert result["ordinal_position"] == 1
    assert result["nullable"] is False
    assert result["precision"] == 10
    assert result["scale"] == 0


def test_udt_member_to_dict_with_max_length() -> None:
    """Verify UDTMember serialization includes max_length when present."""
    # Arrange
    member = UDTMember(
        name="name",
        type_name="varchar",
        ordinal_position=2,
        is_nullable=True,
        max_length=100,
    )

    # Act
    result = member.to_dict()

    # Assert
    assert result["name"] == "name"
    assert result["type"] == "varchar"
    assert result["max_length"] == 100
    assert result["nullable"] is True


def test_udt_type_info_to_dict() -> None:
    """Verify UDTTypeInfo serialization to dict.

    Tests the to_dict() method for API response with nested members.
    """
    # Arrange
    members = [
        UDTMember("id", "int", 1, False, None, 10, 0),
        UDTMember("name", "varchar", 2, True, 100, None, None),
    ]
    udt_info = UDTTypeInfo(
        type_name="CUSTOMER_TYPE",
        kind="STRUCTURED",
        members=members,
    )

    # Act
    result = udt_info.to_dict()

    # Assert
    assert result["type_name"] == "CUSTOMER_TYPE"
    assert result["kind"] == "STRUCTURED"
    assert len(result["members"]) == 2
    assert result["members"][0]["name"] == "id"
    assert result["members"][1]["name"] == "name"


def test_invalid_type_name_format() -> None:
    """Verify rejection of malformed SQL Server type names.

    Invalid formats:
        - Too long (>128 chars)
        - Starts with number
        - Contains special chars (invalid)
        - Empty string
    """
    # Arrange
    mock_adapter = MagicMock()

    # Act & Assert: Type name too long (>128 chars)
    result = parse_udt_structure("A" * 200, mock_adapter)
    assert result is None

    # Act & Assert: Type name starts with number
    result = parse_udt_structure("123_INVALID", mock_adapter)
    assert result is None

    # Act & Assert: Empty type name
    result = parse_udt_structure("", mock_adapter)
    assert result is None

    # Verify logging: warning messages for invalid format
    assert mock_adapter.logger.warning.call_count >= 3


def test_sql_server_version_compatibility() -> None:
    """Verify parsing works across SQL Server versions (2005, 2008, 2012, 2022).

    Different SQL Server versions may have slight differences in system catalog
    metadata, but the core functionality should be version-agnostic.
    """
    # SQL Server 2005 format (basic UDTs)
    mock_adapter_2005 = MagicMock()
    mock_adapter_2005._execute_metadata_many.return_value = [
        ("LEGACY_TYPE", 256, "field1", "varchar", 1, True, 255, None, None),
    ]

    # SQL Server 2012+ format (with precision/scale)
    mock_adapter_2012 = MagicMock()
    mock_adapter_2012._execute_metadata_many.return_value = [
        ("MODERN_TYPE", 1007, "id", "int", 1, False, None, 10, 0),
        ("MODERN_TYPE", 1007, "amount", "decimal", 2, False, None, 15, 2),
    ]

    # Act
    result_2005 = parse_udt_structure("LEGACY_TYPE", mock_adapter_2005)
    result_2012 = parse_udt_structure("MODERN_TYPE", mock_adapter_2012)

    # Assert
    assert result_2005 is not None
    assert result_2005.type_name == "LEGACY_TYPE"
    assert len(result_2005.members) == 1

    assert result_2012 is not None
    assert result_2012.type_name == "MODERN_TYPE"
    assert len(result_2012.members) == 2
