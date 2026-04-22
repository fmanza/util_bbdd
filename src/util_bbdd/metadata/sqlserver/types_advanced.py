"""Advanced SQL Server Type System Support — Phase 4a.2.

Provides introspection for SQL Server user-defined types (UDTs):
- Parse SQL Server user-defined structured types via sys.types + sys.type_members
- Extract member-level metadata (names, types, ordinal position, nullable, precision/scale)
- Handle multiple SQL Server versions (2005 through 2022)
- Detect UDT kind (STRUCTURED vs HIERARCHY vs NATIVE)

Module Pattern:
    - Follows SQL Server v0.8.0 adapter pattern
    - Duck-typed methods for manager integration
    - Uses sys.types + sys.type_members system catalogs
    - Graceful degradation on errors (returns None, not exception)

Example:
    >>> adapter = SQLServerSyncAdapter(manager)
    >>> udt_info = parse_udt_structure("CUSTOMER_TYPE", adapter)
    >>> for member in udt_info.members:
    ...     print(f"{member.name}: {member.type_name} (nullable={member.is_nullable})")
    id: int (nullable=False)
    name: varchar (nullable=True)
"""

import logging
import re

from dataclasses import dataclass
from typing import Any

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# UDT STRUCTURES (Intermediate Representation)
# ============================================================================


@dataclass(frozen=True, slots=True)
class UDTMember:
    """Member field within a SQL Server User-Defined Type."""

    name: str
    type_name: str
    ordinal_position: int
    is_nullable: bool
    max_length: int | None = None
    precision: int | None = None
    scale: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to metadata dict for API response.

        Returns:
            dict[str, Any]: Serializable member metadata

        Example:
            >>> member = UDTMember("id", "int", 1, False, None, 10, 0)
            >>> member.to_dict()
            {'name': 'id', 'type': 'int', 'ordinal_position': 1, 'nullable': False, 'max_length': None, 'precision': 10, 'scale': 0}
        """
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.type_name,
            "ordinal_position": self.ordinal_position,
            "nullable": self.is_nullable,
        }
        if self.max_length is not None:
            result["max_length"] = self.max_length
        if self.precision is not None:
            result["precision"] = self.precision
        if self.scale is not None:
            result["scale"] = self.scale
        return result


@dataclass(frozen=True, slots=True)
class UDTTypeInfo:
    """Metadata for a SQL Server User-Defined Type.

    Attributes:
        type_name: Name of the UDT
        kind: Type kind (STRUCTURED, HIERARCHY, or NATIVE)
        members: List of UDTMember items
    """

    type_name: str
    kind: str
    members: list[UDTMember]

    def to_dict(self) -> dict[str, Any]:
        """Convert to metadata dict for API response.

        Returns:
            dict[str, Any]: Serializable UDT metadata

        Example:
            >>> info = UDTTypeInfo(
            ...     type_name="CUSTOMER_TYPE",
            ...     kind="STRUCTURED",
            ...     members=[UDTMember("id", "int", 1, False)]
            ... )
            >>> info.to_dict()
            {'type_name': 'CUSTOMER_TYPE', 'kind': 'STRUCTURED', 'members': [...]}
        """
        return {
            "type_name": self.type_name,
            "kind": self.kind,
            "members": [member.to_dict() for member in self.members],
        }


# ============================================================================
# HELPER FUNCTIONS FOR PARSING
# ============================================================================


def _build_udt_member_from_row(row: tuple | list, member_index: int) -> UDTMember:
    """Build a UDTMember from a row tuple.

    Extracts member fields from row and creates UDTMember with defaults.

    Args:
        row: Row tuple from sys.types query
        member_index: Index for fallback member name

    Returns:
        UDTMember: Parsed member with all fields populated
    """
    member_name = str(row[2]).lower() if row[2] else f"member_{member_index}"
    member_type = str(row[3]).upper() if row[3] else "VARCHAR"
    position = int(row[4]) if len(row) > 4 and row[4] else member_index + 1
    is_nullable = bool(row[5]) if len(row) > 5 else True
    max_length_val = int(row[6]) if len(row) > 6 and row[6] is not None else None
    precision_val = int(row[7]) if len(row) > 7 and row[7] is not None else None
    scale_val = int(row[8]) if len(row) > 8 and row[8] is not None else None

    return UDTMember(
        name=member_name,
        type_name=member_type,
        ordinal_position=position,
        is_nullable=is_nullable,
        max_length=max_length_val,
        precision=precision_val,
        scale=scale_val,
    )


def _parse_udt_members_from_rows(
    rows: list[Any],
    adapter: Any,
) -> tuple[int, list[UDTMember]]:
    """Parse UDT members from query result rows.

    Iterates rows, validates structure, extracts type_id, and builds members.

    Args:
        rows: List of rows from sys.types query
        adapter: Manager adapter with logger

    Returns:
        tuple: (type_id, list of UDTMember objects)
    """
    type_id: int = 0
    members: list[UDTMember] = []

    for idx, row in enumerate(rows):
        # Validate row structure
        if not isinstance(row, (tuple, list)) or len(row) < 5:
            adapter.logger.debug(f"Skipping invalid row at index {idx}: {row}")
            continue

        # Extract type_id from first row
        if not type_id and len(row) > 1:
            type_id = int(row[1]) if row[1] else 0

        # Build and append member
        member = _build_udt_member_from_row(row, len(members))
        members.append(member)

    return type_id, members


# ============================================================================
# UDT PARSING FUNCTIONS
# ============================================================================


def _validate_type_name(name: str) -> bool:
    """Validate SQL Server identifier format for type name.

    Args:
        name: Type name to validate

    Returns:
        bool: True if name is valid SQL Server identifier, False otherwise

    Notes:
        - SQL Server identifiers: max 128 chars
        - Pattern: [a-zA-Z_][a-zA-Z0-9_]*
        - Can include brackets [Type Name], but MVP validates unbracketed names
    """
    if not name or len(name) > 128:
        return False

    # SQL Server identifier pattern: starts with letter/underscore, contains alphanumeric/_
    return bool(re.match(r"^[a-zA-Z_]\w*$", name))


def _detect_udt_kind(type_id: int, adapter: Any) -> str:
    """Detect UDT kind based on type metadata.

    Args:
        type_id: Type ID from sys.types
        adapter: Manager adapter with logger

    Returns:
        str: UDT kind (STRUCTURED, HIERARCHY, or NATIVE)

    Notes:
        - User-defined types have type_id > 256
        - HIERARCHY types are special (CLR-based, SQL Server 2008+)
        - MVP implementation returns STRUCTURED for all user-defined types
    """
    try:
        # User-defined types have type_id > 256
        if type_id > 256:
            return "STRUCTURED"
        return "NATIVE"
    except Exception:
        return "NATIVE"


def parse_udt_structure(
    type_name: str,
    adapter: Any,
) -> UDTTypeInfo | None:
    """Parse SQL Server UDT structure via sys.types + sys.type_members.

    Fetches UDT definition from SQL Server system catalogs and constructs
    UDTTypeInfo with member metadata (names, types, nullability, precision/scale).

    Args:
        type_name: Name of UDT to parse (e.g., "CUSTOMER_TYPE")
        adapter: Manager adapter with logger + _execute_metadata_many() method

    Returns:
        UDTTypeInfo with parsed members, or None if type not found or error occurs

    Raises:
        None (graceful degradation: returns None instead of raising)

    Example:
        >>> adapter = MagicMock()
        >>> adapter._execute_metadata_many.return_value = [
        ...     ("CUSTOMER_TYPE", 1, "id", "int", 1, False, None, 10, 0),
        ...     ("CUSTOMER_TYPE", 1, "name", "varchar", 2, True, 100, None, None)
        ... ]
        >>> info = parse_udt_structure("CUSTOMER_TYPE", adapter)
        >>> info.type_name
        'CUSTOMER_TYPE'
        >>> len(info.members)
        2
        >>> info.members[0].name
        'id'

    Notes:
        - Validates type_name format before query (reject malformed identifiers)
        - Handles SQL Server 2005+ versions
        - Returns None if type not found (not error) for graceful degradation
        - Logs at debug level for entry, info for success, warning/error for failures
        - Validates member count: return None if no members parsed
    """
    # Validate type name format
    if not _validate_type_name(type_name):
        adapter.logger.warning(f"Invalid type name format: {type_name}")
        return None

    adapter.logger.debug(f"Parsing SQL Server UDT: {type_name}")

    try:
        # Execute metadata query to fetch type members from sys.types + sys.type_members
        params: dict[str, Any] = {"type_name": type_name}
        rows = adapter._execute_metadata_many(
            query_name="fetch_udt_members",
            params=params,
            error_message=f"Failed to fetch UDT members for {type_name}",
        )

        # Graceful degradation: no rows found
        if not rows:
            adapter.logger.debug(f"UDT {type_name} not found in sys.types")
            return None

        # Parse members from rows
        type_id, members = _parse_udt_members_from_rows(rows, adapter)

        # Validate members were found
        if not members:
            adapter.logger.warning(f"No members found for UDT {type_name}")
            return None

        # Detect UDT kind and construct result
        kind = _detect_udt_kind(type_id, adapter)
        result = UDTTypeInfo(
            type_name=type_name,
            kind=kind,
            members=members,
        )

        adapter.logger.info(f"Parsed SQL Server UDT {type_name} ({kind}) with {len(members)} members")
        return result

    except Exception as e:
        adapter.logger.warning(f"Failed to parse SQL Server UDT {type_name}: {e}")
        return None
