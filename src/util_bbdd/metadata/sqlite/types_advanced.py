"""Advanced SQLite Type System Support — Phase 4b.2.

Provides introspection for JSON schemas in SQLite:
- JSON schema inference from column sampling (primary mechanism)
- SQLite is typeless: no built-in schema like PostgreSQL/Oracle
- JSON support: SQLite 3.38+ (JSONB-like storage)
- Strategy: Sample column values → infer JSON schema structure

Module Pattern:
    - Minimal implementation (MVP sampling-based approach)
    - Reuses shared json_schema module for inference
    - Always graceful: None return instead of error
    - Logs all type resolution attempts for debugging

Example:
    >>> adapter = SqliteSyncAdapter(manager)
    >>> schema_hint = query_json_column_schema("main", "events", "data", adapter)
    >>> if schema_hint:
    ...     print(f"Type: {schema_hint['type']}")
    ...     print(f"Properties: {list(schema_hint['properties'].keys())}")
    Type: object
    Properties: ['id', 'status', 'timestamp']
"""

import logging

from typing import Any

from util_bbdd.metadata.adapters.shared.json_schema import (
    infer_json_schema_from_sample,
    normalize_json_schema,
)

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# JSON SCHEMA INTROSPECTION (Phase 4b.2 - SQLite Typeless Database)
# ============================================================================


def query_json_column_schema(
    schema: str,
    table: str,
    column: str,
    adapter: Any,
    sample_size: int = 100,
) -> dict[str, Any] | None:
    """Query JSON column schema for SQLite.

    Strategy (SQLite is typeless):
    SQLite has no built-in schema information like PostgreSQL or Oracle.
    Instead, we use sampling to infer JSON structure from actual values.

    1. Query first N rows from column (sampling)
    2. Filter NULL values
    3. Infer JSON schema from sample
    4. Return schema_hint dict or None if no schema available

    Args:
        schema: Database name (SQLite: typically 'main' or 'temp')
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
                "source": "sampling_inference",
                "depth": int
            }
        or None if schema cannot be determined

    Example:
        >>> schema_hint = query_json_column_schema("main", "events", "payload", adapter)
        >>> if schema_hint:
        ...     print(f"Type: {schema_hint['type']}")
        ...     print(f"Sample count: {schema_hint['sample_count']}")
        Type: object
        Sample count: 50

    Notes:
        - SQLite is typeless: no pg_type or information_schema equivalent
        - Sampling is the primary (and only) mechanism for schema inference
        - Large tables (> 1M rows): sampling still uses LIMIT, should be fast
        - NULL columns: returns None gracefully
        - JSON columns must contain valid JSON (strings auto-parsed)
        - Mixed type arrays: schema will show "mixed" element type
        - No CHECK constraints (SQLite doesn't support them)
    """
    logger.debug(f"Querying SQLite JSON schema for {schema}.{table}.{column}")

    try:
        # Step 1: Sample column values from table
        params: dict[str, Any] = {
            "schema": schema,
            "table": table,
            "column": column,
            "limit": sample_size,
        }

        rows = adapter._execute_metadata_many(
            query_name="sample_column_values",
            params=params,
            error_message=f"Failed to sample column {schema}.{table}.{column}",
        )

        if not rows:
            logger.debug(f"SQLite: no data found for {schema}.{table}.{column}")
            return None

        # Step 2: Extract and filter JSON values from sample
        sample_values: list[str | dict[str, Any] | list[Any]] = []
        for row in rows:
            if row and row[0] is not None:
                value = row[0]
                # Handle both string JSON and already-parsed JSON
                if isinstance(value, (str, dict, list)):
                    sample_values.append(value)

        if not sample_values:
            logger.debug(f"SQLite: no valid JSON values found for {schema}.{table}.{column}")
            return None

        # Step 3: Infer schema from JSON values
        schema_dict = infer_json_schema_from_sample(sample_values, sample_size=len(sample_values))
        if schema_dict:
            # Only accept structured types (object, array) as valid JSON schemas
            # Also reject empty schemas (sample_count == 0 means no valid JSON found)
            if schema_dict.get("type") not in ("object", "array") or schema_dict.get("sample_count", 0) == 0:
                logger.debug(
                    f"SQLite: inferred type is not structured JSON or no valid data: {schema_dict.get('type')}"
                )
                return None

            # Add metadata about inference source
            schema_dict["source"] = "sampling_inference"
            logger.info(f"Inferred JSON schema for {schema}.{table}.{column} from {len(sample_values)} samples")
            return normalize_json_schema(schema_dict)

        return None

    except Exception as e:
        # Graceful error handling: never raise, always return None
        logger.warning(f"Failed to query SQLite JSON schema for {schema}.{table}.{column}: {e}")
        return None
