"""Advanced Snowflake Type System Support — Phase 3.

Provides introspection for semi-structured database types:
- OBJECT<k1: T1, k2: T2, ...> parsing
- ARRAY<T> parsing
- Nested OBJECT and ARRAY types
- Snowflake type normalization

Module Pattern:
    - Follows Snowflake v0.7.0 adapter pattern
    - Duck-typed methods for manager integration
    - Recursive parsing for nested types
    - Graceful error handling (returns None on parse failure)

Example:
    >>> schema_str = "OBJECT<customer_id: INTEGER, name: VARCHAR, tags: ARRAY<VARCHAR>>"
    >>> schema = parse_snowflake_object_syntax(schema_str)
    >>> schema['properties']['customer_id']['type']
    'integer'
    >>> schema['properties']['tags']['element_type']['type']
    'string'
"""

import logging
import re

from typing import Any

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# SNOWFLAKE TYPE PARSING FUNCTIONS
# ============================================================================


def parse_snowflake_object_syntax(type_str: str) -> dict[str, Any] | None:
    """Parse Snowflake OBJECT type syntax.

    Parses type strings like:
        OBJECT<customer_id: INTEGER, name: VARCHAR>
        OBJECT<id: INTEGER, data: OBJECT<nested_id: INTEGER>>
        OBJECT<id: INTEGER, tags: ARRAY<VARCHAR>>

    Args:
        type_str: Snowflake type string (e.g., from INFORMATION_SCHEMA)

    Returns:
        dict with schema structure:
            {
                "type": "object",
                "properties": {
                    "key1": {"type": "integer"},
                    "key2": {"type": "array", "element_type": {"type": "string"}},
                    ...
                }
            }
        or None if parsing fails

    Example:
        >>> schema = parse_snowflake_object_syntax("OBJECT<id: INTEGER, name: VARCHAR>")
        >>> schema['type']
        'object'
        >>> list(schema['properties'].keys())
        ['id', 'name']
        >>> schema['properties']['id']['type']
        'integer'

    Notes:
        - Case-insensitive parsing (Snowflake types are uppercase)
        - Supports nested OBJECT and ARRAY types
        - Handles complex nested patterns: OBJECT<...ARRAY<OBJECT<...>>>
        - Returns None on parse failure (graceful degradation)
    """
    if not type_str or not isinstance(type_str, str):
        return None

    type_str = type_str.strip()

    # Check if it's OBJECT<...> syntax
    if not type_str.upper().startswith("OBJECT<"):
        return None

    # Extract content between outer < and >
    try:
        content = _extract_content_between_brackets(type_str, 6)  # Position of "OBJECT<"
        if not content:
            return None

        # Parse properties
        properties = _parse_object_properties(content)
        if not properties:
            logger.warning(f"Failed to parse OBJECT properties from: {type_str}")
            return None

        return {
            "type": "object",
            "properties": properties,
        }
    except Exception as e:
        logger.debug(f"Failed to parse OBJECT syntax: {e}")
        return None


def parse_snowflake_array_syntax(type_str: str) -> dict[str, Any] | None:
    """Parse Snowflake ARRAY type syntax.

    Parses type strings like:
        ARRAY<INTEGER>
        ARRAY<VARCHAR>
        ARRAY<OBJECT<id: INTEGER, name: VARCHAR>>
        ARRAY<ARRAY<VARCHAR>>

    Args:
        type_str: Snowflake type string

    Returns:
        dict with schema structure:
            {
                "type": "array",
                "element_type": {
                    "type": "object|array|string|integer|..."
                    ...
                }
            }
        or None if parsing fails

    Example:
        >>> schema = parse_snowflake_array_syntax("ARRAY<VARCHAR>")
        >>> schema['type']
        'array'
        >>> schema['element_type']['type']
        'string'

        >>> schema2 = parse_snowflake_array_syntax("ARRAY<OBJECT<id: INTEGER>>")
        >>> schema2['element_type']['type']
        'object'
    """
    if not type_str or not isinstance(type_str, str):
        return None

    type_str = type_str.strip()

    # Check if it's ARRAY<...> syntax
    if not type_str.upper().startswith("ARRAY<"):
        return None

    try:
        # Extract content between < and >
        content = _extract_content_between_brackets(type_str, 5)  # Position of "ARRAY<"
        if not content:
            return None

        # Parse element type (recursively handle nested OBJECT/ARRAY)
        element_type = _parse_snowflake_type(content.strip())
        if not element_type:
            logger.warning(f"Failed to parse ARRAY element type from: {type_str}")
            return None

        return {
            "type": "array",
            "element_type": element_type,
        }
    except Exception as e:
        logger.debug(f"Failed to parse ARRAY syntax: {e}")
        return None


# ============================================================================
# HELPER FUNCTIONS FOR PARSING
# ============================================================================


def _extract_content_between_brackets(s: str, start_pos: int) -> str:
    """Extract content between < and > starting at start_pos.

    Args:
        s: String to extract from
        start_pos: Position where < is (or before it)

    Returns:
        Content between < and > (excluding the brackets)
        Empty string if extraction fails

    Example:
        >>> s = "OBJECT<id: INTEGER, name: VARCHAR>"
        >>> _extract_content_between_brackets(s, 5)
        'id: INTEGER, name: VARCHAR'
    """
    if start_pos >= len(s):
        return ""

    # Find the opening bracket starting from start_pos
    bracket_pos = s.find("<", start_pos)
    if bracket_pos < 0:
        return ""

    # Find matching closing bracket (handle nesting)
    depth = 0
    for i in range(bracket_pos, len(s)):
        if s[i] == "<":
            depth += 1
        elif s[i] == ">":
            depth -= 1
            if depth == 0:
                return s[bracket_pos + 1 : i]

    return ""


def _parse_object_properties(content: str) -> dict[str, dict[str, Any]] | None:
    """Parse properties from OBJECT<...> content.

    Splits "key1: Type1, key2: Type2" into properties.
    Handles nested types with commas inside them.

    Args:
        content: Content between OBJECT< and >

    Returns:
        dict mapping property names to type schemas
    """
    if not content:
        return None

    properties: dict[str, dict[str, Any]] = {}

    # Split by commas, but respect nested angle brackets
    parts = _split_by_comma_respecting_brackets(content)
    if not parts:
        return None

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Parse "key: Type" format
        match = re.match(r"(\w+)\s*:\s*(.+)", part, re.IGNORECASE)
        if not match:
            logger.debug(f"Failed to parse property format: {part}")
            continue

        key = match.group(1).lower()
        type_str = match.group(2).strip()

        # Recursively parse type
        type_schema = _parse_snowflake_type(type_str)
        if type_schema:
            properties[key] = type_schema

    return properties if properties else None


def _parse_snowflake_type(type_str: str) -> dict[str, Any] | None:
    """Recursively parse a Snowflake type.

    Handles:
    - OBJECT<...>
    - ARRAY<...>
    - Primitive types (INTEGER, VARCHAR, etc.)

    Args:
        type_str: Type string to parse

    Returns:
        dict with type schema or None if parsing fails
    """
    if not type_str:
        return None

    type_str = type_str.strip().upper()

    # Try OBJECT
    if type_str.startswith("OBJECT<"):
        result = parse_snowflake_object_syntax(type_str)
        if result:
            return result

    # Try ARRAY
    if type_str.startswith("ARRAY<"):
        result = parse_snowflake_array_syntax(type_str)
        if result:
            return result

    # Primitive type
    normalized = _normalize_snowflake_type(type_str)
    if normalized:
        return {"type": normalized}

    logger.debug(f"Unknown Snowflake type: {type_str}")
    return {"type": "mixed"}  # Fallback


def _split_by_comma_respecting_brackets(s: str) -> list[str]:
    """Split string by commas, respecting nested < > brackets.

    Example:
        "a: INTEGER, b: ARRAY<VARCHAR>, c: OBJECT<x: INT, y: INT>"
        →
        ["a: INTEGER", "b: ARRAY<VARCHAR>", "c: OBJECT<x: INT, y: INT>"]

    Args:
        s: String to split

    Returns:
        List of parts split by commas (respecting bracket nesting)
    """
    parts: list[str] = []
    current = ""
    depth = 0

    for char in s:
        if char == "<":
            depth += 1
            current += char
        elif char == ">":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char

    if current:
        parts.append(current)

    return parts


def _normalize_snowflake_type(type_str: str) -> str | None:
    """Normalize Snowflake type name to generic type.

    Args:
        type_str: Snowflake type (uppercase)

    Returns:
        Generic type name or None if unknown
    """
    type_str = type_str.strip().upper()

    # Remove precision/scale info: DECIMAL(10,2) → DECIMAL
    type_str = re.sub(r"\(\d+.*\)", "", type_str).strip()

    # Map Snowflake types to generic types
    type_map = {
        "BYTE": "binary",
        "BINARY": "binary",
        "VARBINARY": "binary",
        # Integers
        "TINYINT": "integer",
        "SMALLINT": "integer",
        "INT": "integer",
        "INTEGER": "integer",
        "BIGINT": "integer",
        "HUGEINT": "integer",
        # Floating point
        "FLOAT": "float",
        "FLOAT4": "float",
        "FLOAT8": "float",
        "DOUBLE": "float",
        "DOUBLE PRECISION": "float",
        "REAL": "float",
        # Decimal
        "DECIMAL": "decimal",
        "DEC": "decimal",
        "NUMERIC": "decimal",
        # String
        "CHAR": "string",
        "CHARACTER": "string",
        "VARCHAR": "string",
        "NCHAR": "string",
        "NVARCHAR": "string",
        "STRING": "string",
        "TEXT": "string",
        # Date/Time
        "DATE": "date",
        "TIME": "time",
        "TIME WITH TIME ZONE": "time",
        "TIMESTAMP": "timestamp",
        "TIMESTAMP_NTZ": "timestamp",
        "TIMESTAMP WITHOUT TIME ZONE": "timestamp",
        "TIMESTAMP_LTZ": "timestamp",
        "TIMESTAMP WITH TIME ZONE": "timestamp",
        "TIMESTAMP_TZ": "timestamp",
        # Boolean
        "BOOLEAN": "boolean",
        "BOOL": "boolean",
        # Semi-structured
        "JSON": "json",
        "VARIANT": "json",
        # Geometry
        "GEOMETRY": "geometry",
        # Special
        "OBJECT": "object",
        "ARRAY": "array",
    }

    return type_map.get(type_str)


# ============================================================================
# MANAGER INTERFACE METHODS (to be called by Snowflake adapter)
# ============================================================================


def query_snowflake_column_schema(
    schema: str,
    table: str,
    column: str,
    adapter: Any,
) -> dict[str, Any] | None:
    """Query Snowflake column schema for OBJECT/ARRAY types.

    Extracts schema from Snowflake type definition stored in INFORMATION_SCHEMA.

    Args:
        schema: Database schema name
        table: Table name
        column: Column name
        adapter: Manager adapter with _execute_metadata_many

    Returns:
        dict with schema structure:
            {
                "type": "object|array|...",
                "properties": {...},
                "element_type": {...},
                "source": "type_definition"
            }
        or None if type is not OBJECT/ARRAY or parsing fails

    Example:
        >>> schema_hint = query_snowflake_column_schema(
        ...     "raw_data", "events", "event_payload", adapter
        ... )
        >>> if schema_hint:
        ...     print(f"Type: {schema_hint['type']}")
        Type: object
    """
    adapter.logger.debug(f"Querying Snowflake schema for {schema}.{table}.{column}")

    try:
        # Query INFORMATION_SCHEMA.COLUMNS for column data type
        params: dict[str, Any] = {
            "schema": schema,
            "table": table,
            "column": column,
        }

        rows = adapter._execute_metadata_many(
            "query_column_type",
            params=params,
            error_message=f"Failed to query column type for {schema}.{table}.{column}",
        )

        if not rows or not rows[0]:
            adapter.logger.debug(f"No type information found for {schema}.{table}.{column}")
            return None

        type_str = str(rows[0][0]) if rows[0][0] else ""

        if not type_str:
            return None

        # Parse type string
        schema_dict: dict[str, Any] | None = None
        if type_str.upper().startswith("OBJECT<"):
            schema_dict = parse_snowflake_object_syntax(type_str)
        elif type_str.upper().startswith("ARRAY<"):
            schema_dict = parse_snowflake_array_syntax(type_str)
        else:
            # Not an OBJECT/ARRAY type
            return None

        if schema_dict:
            schema_dict["source"] = "type_definition"
            adapter.logger.info(f"Parsed Snowflake {schema_dict['type']} type for {schema}.{table}.{column}")
            return schema_dict

    except Exception as e:
        adapter.logger.warning(f"Failed to parse Snowflake column schema: {e}")

    return None
