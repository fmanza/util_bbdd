"""JSON Schema extraction and inference utilities — Phase 2.

Provides utilities for:
1. Extracting JSON schema from CHECK constraints
2. Inferring JSON schema from sample column values
3. Normalizing and merging inferred schemas

Module Pattern:
    - Shared module for all database adapters (PostgreSQL, MySQL)
    - Type-safe IR for schemas
    - No database-specific logic (that lives in adapter modules)

Example:
    >>> from util_bbdd.metadata.adapters.shared.json_schema import (
    ...     extract_json_schema_from_check_constraint,
    ...     infer_json_schema_from_sample,
    ... )

    >>> check_clause = "JSON_SCHEMA_VALID('{\"type\": \"object\"}', column)"
    >>> schema = extract_json_schema_from_check_constraint(check_clause)
    >>> print(schema)
    {'type': 'object'}

    >>> sample_rows = ['{"id": 1, "name": "Alice"}', '{"id": 2, "name": "Bob"}']
    >>> inferred = infer_json_schema_from_sample(sample_rows)
    >>> print(inferred['properties'].keys())
    dict_keys(['id', 'name'])
"""

import json
import logging
import re

from typing import Any

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# JSON SCHEMA EXTRACTION (from CHECK constraints)
# ============================================================================


def extract_json_schema_from_check_constraint(
    check_clause: str,
) -> dict[str, Any] | None:
    """Extract JSON schema from CHECK constraint clause.

    Looks for patterns like:
        - JSON_SCHEMA_VALID('{"type": "object", ...}', column)
        - CHECK_JSON('{"type": "object", ...}')

    Args:
        check_clause: Raw CHECK constraint clause from information_schema

    Returns:
        Parsed JSON schema dict, or None if no schema found/parseable

    Example:
        >>> clause = '''JSON_SCHEMA_VALID('{"type": "object", "properties": {
        ...     "id": {"type": "integer"}, "name": {"type": "string"}}}', payload)'''
        >>> schema = extract_json_schema_from_check_constraint(clause)
        >>> schema['properties']['id']['type']
        'integer'
    """
    if not check_clause or not isinstance(check_clause, str):
        return None

    # Pattern 1: JSON_SCHEMA_VALID('schema', column) or JSON_SCHEMA_VALID("schema", column)
    pattern_1 = r"JSON_SCHEMA_VALID\s*\(\s*'([^']+)'[^\)]*\)"
    match = re.search(pattern_1, check_clause)
    if match:
        schema_str = match.group(1)
        try:
            return json.loads(schema_str)  # type: ignore[no-any-return]
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse JSON schema from CHECK constraint: {e}")
            return None

    # Pattern 2: JSON_SCHEMA_VALID("schema", column)
    pattern_2 = r'JSON_SCHEMA_VALID\s*\(\s*"([^"]+)"[^\)]*\)'
    match = re.search(pattern_2, check_clause)
    if match:
        schema_str = match.group(1)
        try:
            return json.loads(schema_str)  # type: ignore[no-any-return]
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse JSON schema from CHECK constraint: {e}")
            return None

    return None


# ============================================================================
# JSON SCHEMA INFERENCE (from sample data)
# ============================================================================


def infer_json_schema_from_sample(
    rows: list[str | dict[str, Any] | list[Any]],
    sample_size: int = 100,
    max_depth: int = 2,
) -> dict[str, Any]:
    """Infer JSON schema from sample column values.

    Analyzes sample rows to determine:
    - Key presence frequency (for "required" keys)
    - Type distribution per key (type, examples)
    - Value constraints (e.g., enum values)

    Algorithm:
    1. Parse each row as JSON
    2. Track key presence (frequency > 80% → required)
    3. Infer type for each key (number, string, boolean, object, array, null)
    4. Track examples per type
    5. Detect enums (low cardinality)

    Args:
        rows: Sample of column values (strings or parsed objects)
        sample_size: Max rows to analyze (default 100)
        max_depth: Max nesting depth for nested object inference (default 2)

    Returns:
        dict with schema structure:
            {
                "type": "object" | "array" | "string" | "number" | "mixed",
                "properties": {
                    "key1": {"type": "string", "examples": [...]},
                    ...
                },
                "required": ["key1", ...],
                "sample_count": int,
                "depth": int
            }

    Example:
        >>> samples = [
        ...     '{"id": 1, "name": "Alice"}',
        ...     '{"id": 2, "name": "Bob"}',
        ...     '{"id": 3, "name": "Charlie"}'
        ... ]
        >>> schema = infer_json_schema_from_sample(samples)
        >>> schema['properties']['id']['type']
        'number'
        >>> 'id' in schema['required']
        True
    """
    if not rows:
        return {
            "type": "object",
            "properties": {},
            "required": [],
            "sample_count": 0,
            "depth": 0,
        }

    # Limit to sample_size rows
    rows_to_analyze = rows[:sample_size]

    # Parse all rows
    parsed_rows: list[Any] = []
    for row in rows_to_analyze:
        if isinstance(row, str):
            try:
                parsed_rows.append(json.loads(row))
            except json.JSONDecodeError:
                logger.debug("Skipping unparseable JSON row")
                continue
        else:
            parsed_rows.append(row)

    if not parsed_rows:
        return {
            "type": "object",
            "properties": {},
            "required": [],
            "sample_count": 0,
            "depth": 0,
        }

    # Infer top-level type
    top_level_type = _infer_value_type(parsed_rows[0])

    if top_level_type == "object":
        return _infer_object_schema(
            parsed_rows,
            max_depth=max_depth,
            current_depth=0,
        )
    elif top_level_type == "array":
        return _infer_array_schema(parsed_rows, max_depth=max_depth)
    else:
        # Scalar type
        return {
            "type": top_level_type,
            "examples": [r for r in parsed_rows[:3] if r is not None],
            "sample_count": len(parsed_rows),
            "depth": 0,
        }


def _infer_object_schema(
    rows: list[dict[str, Any]],
    max_depth: int = 2,
    current_depth: int = 0,
) -> dict[str, Any]:
    """Infer schema for object-type rows."""
    properties: dict[str, Any] = {}
    key_counts: dict[str, int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        for key, value in row.items():
            key_counts[key] = key_counts.get(key, 0) + 1

            # Infer type for this key
            if key not in properties:
                properties[key] = {}

            value_type = _infer_value_type(value)

            # Build type info
            if "types" not in properties[key]:
                properties[key]["types"] = set()
            properties[key]["types"].add(value_type)

            # Collect examples (for enum detection)
            if "examples" not in properties[key]:
                properties[key]["examples"] = []
            if value not in properties[key]["examples"] and len(properties[key]["examples"]) < 5:
                properties[key]["examples"].append(value)

    # Normalize properties and detect required keys
    required_keys: list[str] = []
    for key, key_count in key_counts.items():
        presence = key_count / len(rows)

        # Determine primary type
        types = properties[key]["types"]
        if len(types) == 1:
            primary_type = next(iter(types))
        else:
            primary_type = "mixed"

        # Build property schema
        prop_schema: dict[str, Any] = {"type": primary_type}

        # Add examples
        examples = properties[key].get("examples", [])
        if examples:
            prop_schema["examples"] = examples

        # Detect enums (low cardinality strings)
        if primary_type == "string" and 2 <= len(set(examples)) <= 10:
            prop_schema["enum"] = list(set(examples))

        # Mark as required if present in > 80% of rows
        if presence > 0.8:
            required_keys.append(key)

        properties[key] = prop_schema

    return {
        "type": "object",
        "properties": properties,
        "required": required_keys,
        "sample_count": len(rows),
        "depth": current_depth,
    }


def _infer_array_schema(
    rows: list[list[Any]],
    max_depth: int = 2,
) -> dict[str, Any]:
    """Infer schema for array-type rows."""
    element_types: set[str] = set()
    all_elements: list[Any] = []

    for row in rows:
        if not isinstance(row, list):
            continue

        for element in row:
            if element is not None:
                element_types.add(_infer_value_type(element))
                all_elements.append(element)

    if not element_types:
        element_type = "mixed"
    elif len(element_types) == 1:
        element_type = next(iter(element_types))
    else:
        element_type = "mixed"

    return {
        "type": "array",
        "element_type": element_type,
        "examples": all_elements[:3],
        "sample_count": len(rows),
        "depth": 0,
    }


def _infer_value_type(value: Any) -> str:
    """Infer JSON type of a single value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "number"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "mixed"


# ============================================================================
# SCHEMA NORMALIZATION & MERGING
# ============================================================================


def normalize_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize schema to standard form.

    Ensures:
    - "type" field is present
    - "properties" is dict (for objects)
    - "required" is list
    - No dangling "types" field

    Args:
        schema: Raw inferred schema

    Returns:
        Normalized schema dict
    """
    if not isinstance(schema, dict):
        return {"type": "mixed"}

    # Copy to avoid mutation
    normalized = schema.copy()

    # Ensure type
    if "type" not in normalized:
        normalized["type"] = "object"

    # Normalize properties
    if "properties" in normalized:
        props = normalized["properties"]
        if isinstance(props, dict):
            # Convert any "types" to "type"
            for _key, prop_schema in props.items():
                if isinstance(prop_schema, dict):
                    if "types" in prop_schema:
                        types = prop_schema.pop("types")
                        if "type" not in prop_schema:
                            if len(types) == 1:
                                prop_schema["type"] = next(iter(types))
                            else:
                                prop_schema["type"] = "mixed"

    # Ensure required is list
    if "required" in normalized:
        if not isinstance(normalized["required"], list):
            normalized["required"] = list(normalized["required"])
    else:
        normalized["required"] = []

    return normalized


def merge_inferred_schemas(
    schemas: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge multiple inferred schemas into consensus.

    Strategy:
    - Common keys across all schemas → required
    - Union of keys → properties
    - Common type → use it; otherwise "mixed"

    Args:
        schemas: List of inferred schema dicts

    Returns:
        Merged consensus schema
    """
    if not schemas:
        return {"type": "object", "properties": {}, "required": []}

    if len(schemas) == 1:
        return normalize_json_schema(schemas[0])

    # Collect all keys and their type distributions
    all_keys: dict[str, list[str]] = {}  # key → list of types
    total_schemas = len(schemas)

    for schema in schemas:
        if schema.get("type") == "object" and "properties" in schema:
            for key, prop_schema in schema["properties"].items():
                if key not in all_keys:
                    all_keys[key] = []
                prop_type = prop_schema.get("type", "mixed")
                all_keys[key].append(prop_type)

    # Build merged properties
    merged_properties: dict[str, dict[str, str]] = {}
    merged_required: list[str] = []

    for key, type_list in all_keys.items():
        # Determine consensus type
        unique_types = set(type_list)
        if len(unique_types) == 1:
            consensus_type = next(iter(unique_types))
        else:
            consensus_type = "mixed"

        merged_properties[key] = {"type": consensus_type}

        # Key is required if present in all schemas
        if len(type_list) == total_schemas:
            merged_required.append(key)

    return {
        "type": "object",
        "properties": merged_properties,
        "required": merged_required,
        "merged_from": total_schemas,
    }
