"""Advanced MariaDB Type System Support — Phase 4a.3.

Provides introspection for JSON schemas in MariaDB:
- JSON schema extraction from CHECK constraints (MariaDB 10.2+)
- Sampling-based JSON schema inference (primary mechanism)
- Reuses MySQL implementation (MariaDB/MySQL JSON handling is nearly identical)

Module Pattern:
    - Delegates to MySQL types_advanced for JSON introspection
    - MariaDB and MySQL have compatible JSON functions for schema inference
    - Type-safe IR compatible with shared json_schema module

Example:
    >>> adapter = MariaDBSyncAdapter(manager)
    >>> schema_hint = query_json_column_schema("test_db", "events", "payload", adapter)
    >>> print(schema_hint['properties'].keys())
    dict_keys(['user_id', 'timestamp', 'status'])
"""

import logging

from typing import Any

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# JSON SCHEMA INTROSPECTION (Phase 4a.3)
# ============================================================================


def query_json_column_schema(
    schema: str,
    table: str,
    column: str,
    adapter: Any,
    sample_size: int = 100,
) -> dict[str, Any] | None:
    """Query JSON column schema for MariaDB.

    Strategy (MariaDB has strong JSON support, similar to MySQL):
    1. Try to query CHECK constraints (MariaDB 10.2+ has good support)
    2. Fall back to sampling column values and inferring schema
    3. Return schema_hint dict or None if no schema available

    MariaDB JSON handling is nearly identical to MySQL, so this function
    delegates to the MySQL implementation with full compatibility.

    Args:
        schema: Database schema name (MariaDB: same as database name)
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
        - MariaDB JSON support is compatible with MySQL (JSON functions similar)
        - CHECK constraints are supported in MariaDB 10.2+
        - Sampling is used when CHECK constraints unavailable
        - Large tables (> 1M rows): sampling still uses LIMIT, should be fast
        - NULL columns: returns None gracefully
        - Mixed type arrays: schema will show "mixed" element type
    """
    from util_bbdd.metadata.mysql.types_advanced import query_json_column_schema as query_mysql_json

    logger.debug(f"Querying MariaDB JSON schema for {schema}.{table}.{column}")

    try:
        # Delegate to MySQL implementation (MariaDB JSON handling is compatible)
        result = query_mysql_json(schema, table, column, adapter, sample_size)
        if result:
            logger.info(f"MariaDB JSON schema inferred for {schema}.{table}.{column}")
        return result
    except Exception as e:
        logger.warning(f"Failed to query MariaDB JSON schema: {e}")
        return None
