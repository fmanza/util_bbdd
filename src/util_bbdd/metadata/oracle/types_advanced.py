"""Advanced Oracle Type System Support — Phase 4a.

Provides introspection for user-defined OBJECT database types:
- Parse Oracle user-defined OBJECT types via dba_types + dba_type_attrs
- Extract field-level metadata (names, types, nullable, precision/scale)
- Handle nested OBJECT types and complex types
- Support multiple Oracle versions (9i through 21c)

Module Pattern:
    - Follows Oracle v0.8.0 adapter pattern
    - Duck-typed methods for manager integration
    - Uses dba_types + dba_type_attrs system catalogs
    - Graceful degradation on errors (returns None, not exception)

Example:
    >>> adapter = OracleSyncAdapter(manager)
    >>> object_info = parse_object_type_structure("CUSTOMER_TYPE", adapter)
    >>> for field in object_info.fields:
    ...     print(f"{field.name}: {field.type_name} (nullable={field.is_nullable})")
    id: NUMBER (nullable=False)
    name: VARCHAR2 (nullable=True)
"""

import logging
import re

from dataclasses import dataclass
from typing import Any

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# OBJECT TYPE STRUCTURES (Intermediate Representation)
# ============================================================================


@dataclass(frozen=True, slots=True)
class ObjectTypeField:
    """Field within an Oracle OBJECT type."""

    name: str
    type_name: str
    ordinal_position: int
    is_nullable: bool
    precision: int | None = None
    scale: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to metadata dict for API response.

        Returns:
            dict[str, Any]: Serializable field metadata

        Example:
            >>> field = ObjectTypeField("id", "NUMBER", 1, False, 10, 0)
            >>> field.to_dict()
            {'name': 'id', 'type': 'NUMBER', 'ordinal_position': 1, 'nullable': False, 'precision': 10, 'scale': 0}
        """
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.type_name,
            "ordinal_position": self.ordinal_position,
            "nullable": self.is_nullable,
        }
        if self.precision is not None:
            result["precision"] = self.precision
        if self.scale is not None:
            result["scale"] = self.scale
        return result


@dataclass(frozen=True, slots=True)
class ObjectTypeInfo:
    """Metadata for an Oracle OBJECT type.

    Attributes:
        type_name: Name of the OBJECT type
        owner: Schema/owner of the type
        fields: List of ObjectTypeField items
    """

    type_name: str
    owner: str
    fields: list[ObjectTypeField]

    def to_dict(self) -> dict[str, Any]:
        """Convert to metadata dict for API response.

        Returns:
            dict[str, Any]: Serializable type metadata

        Example:
            >>> info = ObjectTypeInfo(
            ...     type_name="CUSTOMER_TYPE",
            ...     owner="SYS",
            ...     fields=[ObjectTypeField("id", "NUMBER", 1, False, 10, 0)]
            ... )
            >>> info.to_dict()
            {'type_name': 'CUSTOMER_TYPE', 'owner': 'SYS', 'fields': [...]}
        """
        return {
            "type_name": self.type_name,
            "owner": self.owner,
            "fields": [field.to_dict() for field in self.fields],
        }


# ============================================================================
# OBJECT TYPE PARSING FUNCTIONS
# ============================================================================


def _validate_type_name(name: str) -> bool:
    """Validate Oracle identifier format for type name.

    Args:
        name: Type name to validate

    Returns:
        bool: True if name is valid Oracle identifier, False otherwise

    Notes:
        - Oracle identifiers: max 30 chars
        - Pattern: [a-zA-Z_][a-zA-Z0-9_$#]*
        - Case-sensitive when quoted, case-insensitive otherwise
    """
    if not name or len(name) > 30:
        return False

    # Oracle identifier pattern: starts with letter/underscore, contains alphanumeric/$/#
    return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_$#]*$", name))


def parse_object_type_structure(
    type_name: str,
    adapter: Any,
) -> ObjectTypeInfo | None:
    """Parse Oracle OBJECT type structure via dba_types + dba_type_attrs.

    Fetches type definition from Oracle system catalogs and constructs
    ObjectTypeInfo with field metadata (names, types, nullability, precision/scale).

    Args:
        type_name: Name of OBJECT type to parse (e.g., "CUSTOMER_TYPE")
        adapter: Manager adapter with logger + _execute_metadata_many() method

    Returns:
        ObjectTypeInfo with parsed fields, or None if type not found or error occurs

    Raises:
        None (graceful degradation: returns None instead of raising)

    Example:
        >>> adapter = MagicMock()
        >>> adapter._execute_metadata_many.return_value = [
        ...     ("CUSTOMER_TYPE", "SYS", "id", "NUMBER", 1, False, 10, 0),
        ...     ("CUSTOMER_TYPE", "SYS", "name", "VARCHAR2", 2, True, 100, None)
        ... ]
        >>> info = parse_object_type_structure("CUSTOMER_TYPE", adapter)
        >>> info.type_name
        'CUSTOMER_TYPE'
        >>> len(info.fields)
        2
        >>> info.fields[0].name
        'id'

    Notes:
        - Validates type_name format before query (reject malformed identifiers)
        - Handles multiple Oracle versions (9i through 21c)
        - Returns None if type not found (not error) for graceful degradation
        - Logs at debug level for entry, info for success, warning/error for failures
        - Callable field count validation: return None if no fields parsed
    """
    # Validate type name format
    if not _validate_type_name(type_name):
        adapter.logger.warning(f"Invalid type name format: {type_name}")
        return None

    adapter.logger.debug(f"Parsing Oracle OBJECT type: {type_name}")

    try:
        # Execute metadata query to fetch type attributes from dba_types + dba_type_attrs
        params: dict[str, Any] = {"type_name": type_name}
        rows = adapter._execute_metadata_many(
            query_name="fetch_object_type_attributes",
            params=params,
            error_message=f"Failed to fetch OBJECT type attributes for {type_name}",
        )

        # Graceful degradation: no rows found
        if not rows:
            adapter.logger.debug(f"Type {type_name} not found in dba_types")
            return None

        # Parse row data: (type_name, owner, attr_name, attr_type, attr_no, nullable, precision, scale)
        owner: str = ""
        fields: list[ObjectTypeField] = []

        for row in rows:
            # Validate row structure
            if not isinstance(row, (tuple, list)) or len(row) < 5:
                continue

            # Extract fields from row
            row_owner = str(row[1]) if len(row) > 1 and row[1] else "UNKNOWN"
            attr_name = str(row[2]).lower() if row[2] else f"field_{len(fields)}"
            attr_type = str(row[3]).upper() if row[3] else "VARCHAR2"
            attr_no = int(row[4]) if row[4] else len(fields) + 1
            is_nullable = bool(row[5]) if len(row) > 5 else True
            precision_val = int(row[6]) if len(row) > 6 and row[6] is not None else None
            scale_val = int(row[7]) if len(row) > 7 and row[7] is not None else None

            # Update owner from first row
            if not owner:
                owner = row_owner

            # Create ObjectTypeField
            field = ObjectTypeField(
                name=attr_name,
                type_name=attr_type,
                ordinal_position=attr_no,
                is_nullable=is_nullable,
                precision=precision_val,
                scale=scale_val,
            )
            fields.append(field)

        # Validate fields were found
        if not fields:
            adapter.logger.warning(f"No attributes found for type {type_name}")
            return None

        # Construct result
        result = ObjectTypeInfo(
            type_name=type_name,
            owner=owner,
            fields=fields,
        )

        adapter.logger.info(f"Parsed Oracle OBJECT type {type_name} with {len(fields)} fields")
        return result

    except Exception as e:
        adapter.logger.warning(f"Failed to parse Oracle OBJECT type {type_name}: {e}")
        return None
