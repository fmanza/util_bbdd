"""Advanced MySQL Type System Support — Phase 2.

Provides introspection for JSON schemas in MySQL:
- JSON schema extraction from CHECK constraints (limited MySQL support)
- Sampling-based JSON schema inference (primary mechanism)
- ENUM/SET value extraction (bonus)

Module Pattern:
    - Follows MySQL v0.7.0 adapter pattern
    - Duck-typed methods for manager integration
    - JSON schema inference via sampling (MySQL has limited CHECK support)
    - Type-safe IR compatible with shared json_schema module

Example:
    >>> adapter = MySQLSyncAdapter(manager)
    >>> schema_hint = query_json_column_schema("test_db", "events", "payload", adapter)
    >>> print(schema_hint['properties'].keys())
    dict_keys(['user_id', 'timestamp', 'status'])
"""

import logging

from typing import Any

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# JSON SCHEMA INTROSPECTION (Phase 2)
# ============================================================================


def query_json_column_schema(
    schema: str,
    table: str,
    column: str,
    adapter: Any,
    sample_size: int = 100,
) -> dict[str, Any] | None:
    """Query JSON column schema for MySQL.

    Strategy (MySQL has limited CHECK support):
    1. Try to query CHECK constraints (may not be available)
    2. Fall back to sampling column values and inferring schema
    3. Return schema_hint dict or None if no schema available

    Args:
        schema: Database schema name (MySQL: same as database name)
        table: Table name
        column: Column name
        adapter: Manager adapter with _execute_metadata_many
        sample_size: Max rows to sample for schema inference (default: 100)

    Returns:
        dict with schema structure:
            {
                "type": "object" | "array" | "string" | "mixed",
                "properties": {...},
                "required": [...],
                "sample_count": int,
                "source": "constraint" | "sampling"
            }
        or None if schema cannot be determined

    Example:
        >>> schema_hint = query_json_column_schema("events_db", "api_logs", "response", adapter)
        >>> if schema_hint:
        ...     print(f"Type: {schema_hint['type']}")
        ...     print(f"Sample count: {schema_hint['sample_count']}")
        Type: object
        Sample count: 100

    Notes:
        - MySQL has very limited CHECK constraint support in most versions
        - Sampling is the primary mechanism for MySQL
        - Large tables (> 1M rows): sampling still uses LIMIT, should be fast
        - NULL columns: returns None gracefully
        - Mixed type arrays: schema will show "mixed" element type
    """
    from util_bbdd.metadata.adapters.shared.json_schema import (
        extract_json_schema_from_check_constraint,
        infer_json_schema_from_sample,
        normalize_json_schema,
    )

    adapter.logger.debug(f"Querying JSON schema for {schema}.{table}.{column}")

    # Step 1: Try to extract schema from CHECK constraints (may not exist in MySQL)
    try:
        # Query for CHECK constraints (MySQL has limited support)
        params_check = {"schema": schema, "table": table}

        rows = adapter._execute_metadata_many(
            "query_check_constraints",
            params=params_check,
            error_message=f"Failed to query CHECK constraints for {schema}.{table}",
        )

        for row in rows:
            if row and row[0]:
                check_clause = str(row[0])
                schema_dict = extract_json_schema_from_check_constraint(check_clause)
                if schema_dict:
                    adapter.logger.info(f"JSON schema extracted from CHECK constraint for {schema}.{table}.{column}")
                    result = normalize_json_schema(schema_dict)
                    result["source"] = "constraint"
                    return result
    except Exception as e:
        adapter.logger.debug(f"Failed to query CHECK constraints (expected for MySQL): {e}")
        # Fall through to sampling (expected for MySQL)

    # Step 2: Fall back to sampling column values (primary mechanism for MySQL)
    try:
        params_sample: dict[str, Any] = {
            "schema": schema,
            "table": table,
            "column": column,
            "limit": sample_size,
        }

        rows = adapter._execute_metadata_many(
            "sample_json_column",
            params=params_sample,
            error_message=f"Failed to sample {schema}.{table}.{column}",
        )

        if not rows:
            adapter.logger.debug(f"No JSON values found in {schema}.{table}.{column}")
            return None

        sample_values = [str(row[0]) if row and row[0] else None for row in rows]
        sample_values_filtered: list[str | dict[str, Any] | list[Any]] = [v for v in sample_values if v]
        if sample_values_filtered:
            schema_dict = infer_json_schema_from_sample(sample_values_filtered, sample_size=len(sample_values_filtered))
            adapter.logger.info(f"JSON schema inferred from {len(sample_values)} samples for {schema}.{table}.{column}")
            result = normalize_json_schema(schema_dict)
            result["source"] = "sampling"
            return result
    except Exception as e:
        adapter.logger.warning(f"Failed to sample JSON column {schema}.{table}.{column}: {e}")

    return None


# ============================================================================
# ENUM/SET VALUE EXTRACTION (Bonus — Phase 2 Enhancement)
# ============================================================================


def parse_enum_values(type_str: str) -> list[str]:
    """Extract ENUM values from MySQL column type definition.

    Args:
        type_str: Column type string from information_schema
                 Format: "enum('value1','value2','value3')"

    Returns:
        List of enum values (empty list if parsing fails)

    Example:
        >>> parse_enum_values("enum('active','inactive','pending')")
        ['active', 'inactive', 'pending']
    """
    if not type_str or "enum(" not in type_str.lower():
        return []

    try:
        # Extract values between parentheses
        start = type_str.find("(")
        end = type_str.rfind(")")
        if start < 0 or end < 0:
            return []

        values_str = type_str[start + 1 : end]

        # Parse quoted values
        values = []
        current_value = ""
        in_quotes = False
        escape_next = False

        for char in values_str:
            if escape_next:
                current_value += char
                escape_next = False
                continue

            if char == "\\" and in_quotes:
                escape_next = True
                continue

            if char in ("'", '"'):
                if in_quotes:
                    values.append(current_value)
                    current_value = ""
                    in_quotes = False
                else:
                    in_quotes = True
                continue

            if in_quotes:
                current_value += char

        return values
    except Exception as e:
        logger.debug(f"Failed to parse ENUM values: {e}")
        return []


def parse_set_values(type_str: str) -> list[str]:
    """Extract SET values from MySQL column type definition.

    Args:
        type_str: Column type string from information_schema
                 Format: "set('value1','value2','value3')"

    Returns:
        List of set values (empty list if parsing fails)

    Example:
        >>> parse_set_values("set('read','write','delete')")
        ['read', 'write', 'delete']
    """
    # SET parsing is identical to ENUM
    return parse_enum_values(type_str.replace("set(", "enum(", 1))
