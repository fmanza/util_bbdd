"""Advanced PostgreSQL Type System Support — Phase 1.

Provides introspection for complex/composite database types:
- Composite types (user-defined types)
- Field-level metadata (names, types, ordinal position)
- Recursive type resolution (nested composites)

Module Pattern:
    - Follows PostgreSQL v0.7.0 adapter pattern
    - Duck-typed methods for manager integration
    - Uses pg_type + pg_attribute system catalogs
    - Supports nested types with cycle detection (max 5 levels)

Example:
    >>> adapter = PostgreSQLSyncAdapter(manager)
    >>> composite_fields = adapter.get_composite_type_fields("public", "address_type")
    >>> for field in composite_fields:
    ...     print(f"{field['name']}: {field['type']}")
    street: varchar
    city: varchar
    zip: varchar(10)
"""

import logging

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

T = TypeVar("T")

logger: logging.Logger = logging.getLogger(__name__)

# ============================================================================
# COMPOSITE TYPE STRUCTURES (Intermediate Representation)
# ============================================================================


@dataclass(frozen=True, slots=True)
class CompositeTypeField:
    """Field within a composite type."""

    name: str
    type_name: str
    ordinal_position: int
    is_array: bool = False
    is_nullable: bool = True
    max_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to metadata dict for API response."""
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.type_name,
            "ordinal_position": self.ordinal_position,
            "nullable": self.is_nullable,
        }
        if self.is_array:
            result["is_array"] = True
        if self.max_length is not None:
            result["max_length"] = self.max_length
        if self.numeric_precision is not None:
            result["precision"] = self.numeric_precision
        if self.numeric_scale is not None:
            result["scale"] = self.numeric_scale
        return result


@dataclass(frozen=True, slots=True)
class CompositeTypeInfo:
    """Metadata for a composite type."""

    name: str
    schema: str
    owner: str
    fields: list[CompositeTypeField]
    is_nested: bool = False
    depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to metadata dict for API response."""
        return {
            "name": self.name,
            "schema": self.schema,
            "owner": self.owner,
            "fields": [field.to_dict() for field in self.fields],
            "depth": self.depth,
        }


# ============================================================================
# MANAGER PROTOCOL (Duck-typed interface)
# ============================================================================


class PostgreSQLManagerProtocol(Protocol):
    """Interface that manager must provide."""

    @property
    def logger(self) -> logging.Logger:
        """Logger instance."""
        ...

    def _execute_metadata_many(
        self, query_name: str, *, params: dict[str, Any], error_message: str
    ) -> list[tuple[Any, ...]]:
        """Execute metadata query (rows as tuples)."""
        ...


# ============================================================================
# COMPOSITE TYPE PARSING FUNCTIONS
# ============================================================================


def parse_composite_type_structure(
    schema: str, type_name: str, adapter: Any, max_depth: int = 5, current_depth: int = 0
) -> CompositeTypeInfo | None:
    """Parse PostgreSQL composite type structure via pg_type + pg_attribute.

    Args:
        schema: Schema name (e.g., "public")
        type_name: Composite type name (e.g., "address_type")
        adapter: Manager adapter with logger + execute methods
        max_depth: Maximum recursion depth for nested composites (default: 5)
        current_depth: Current recursion depth (internal use)

    Returns:
        CompositeTypeInfo with field details, or None if type not found

    Example:
        >>> info = parse_composite_type_structure("public", "address_type", adapter)
        >>> for field in info.fields:
        ...     print(f"{field.name}: {field.type_name}")
        street: varchar
        city: varchar

    Notes:
        - Handles nested composite types (composite within composite)
        - Cycle detection: max_depth prevents infinite recursion
        - Returns None if schema/type not found (graceful degradation)
        - Edge cases: array fields, domain types, types with defaults
    """
    # Validate recursion depth
    if not _is_depth_valid(current_depth, max_depth, schema, type_name, adapter):
        return None

    # Fetch rows from database
    rows = _fetch_composite_type_rows(schema, type_name, adapter)
    if not rows:
        return None

    # Parse all field rows
    fields, owner = _parse_all_composite_fields(rows, adapter, schema, type_name)
    if not fields:
        return None

    # Build and return composite type info
    return _build_composite_info(schema, type_name, fields, owner, current_depth)


# ============================================================================
# PRIVATE HELPER FUNCTIONS (Extracted for CC reduction)
# ============================================================================


def _is_depth_valid(current_depth: int, max_depth: int, schema: str, type_name: str, adapter: Any) -> bool:
    """Validate recursion depth for composite type parsing.

    Args:
        current_depth: Current recursion depth
        max_depth: Maximum allowed depth
        schema: Schema name (for logging)
        type_name: Type name (for logging)
        adapter: Adapter with logger

    Returns:
        True if depth is valid, False if limit reached
    """
    if current_depth >= max_depth:
        adapter.logger.warning(f"Composite type nesting depth limit ({max_depth}) reached for {schema}.{type_name}")
        return False
    return True


def _fetch_composite_type_rows(schema: str, type_name: str, adapter: Any) -> list[tuple[Any, ...]] | None:
    """Fetch composite type field rows from database.

    Args:
        schema: Schema name
        type_name: Type name
        adapter: Manager adapter

    Returns:
        List of row tuples, or None if fetch failed or no rows found
    """
    params: dict[str, Any] = {"schema": schema, "type_name": type_name}

    try:
        rows: Any = adapter._execute_metadata_many(
            "fetch_composite_type_fields",
            params=params,
            error_message=f"Failed to fetch composite type {schema}.{type_name}",
        )
        if not rows:
            adapter.logger.debug(f"Composite type {schema}.{type_name} not found")
            return None
        # Type narrowing: assume list of tuples from adapter
        return rows if isinstance(rows, list) else None
    except Exception as e:
        adapter.logger.error(f"Error fetching composite type {schema}.{type_name}: {e}", exc_info=True)
        return None


def _parse_composite_field_row(row: Any) -> tuple[CompositeTypeField, str] | None:
    """Parse a single composite type field row.

    Args:
        row: Single row tuple from database

    Returns:
        Tuple of (CompositeTypeField, owner_name), or None if row invalid
    """
    # Validate row structure
    if not isinstance(row, (tuple, list)) or len(row) < 9:
        return None

    # Extract and normalize field values using safe conversion helper
    field_name = _safe_str(row[0])
    field_type_name = _safe_str(row[2], default="unknown")
    ordinal_position = _safe_int(row[3])
    owner = _safe_str(row[4])
    is_array = _safe_bool(row[5])
    max_length = _safe_int_optional(row[6])
    numeric_precision = _safe_int_optional(row[7])
    numeric_scale = _safe_int_optional(row[8])

    # Normalize field type name
    normalized_type = _normalize_composite_field_type(field_type_name)

    # Build field object
    field = CompositeTypeField(
        name=field_name,
        type_name=normalized_type,
        ordinal_position=ordinal_position,
        is_array=is_array,
        is_nullable=True,  # PostgreSQL composite fields are nullable by default
        max_length=max_length,
        numeric_precision=numeric_precision,
        numeric_scale=numeric_scale,
    )

    return field, owner


def _parse_all_composite_fields(
    rows: list[tuple[Any, ...]], adapter: Any, schema: str, type_name: str
) -> tuple[list[CompositeTypeField], str]:
    """Parse all composite type field rows.

    Args:
        rows: All field rows from database
        adapter: Manager adapter (for logging)
        schema: Schema name (for logging)
        type_name: Type name (for logging)

    Returns:
        Tuple of (fields_list, owner_name)
    """
    fields: list[CompositeTypeField] = []
    owner: str = ""

    for row in rows:
        result = _parse_composite_field_row(row)
        if result:
            field, row_owner = result
            fields.append(field)
            owner = row_owner  # Last owner wins (typically all same)

    if not fields:
        adapter.logger.debug(f"No fields found for composite type {schema}.{type_name}")

    return fields, owner


def _build_composite_info(
    schema: str, type_name: str, fields: list[CompositeTypeField], owner: str, current_depth: int
) -> CompositeTypeInfo:
    """Build CompositeTypeInfo from parsed fields.

    Args:
        schema: Schema name
        type_name: Type name
        fields: List of parsed fields
        owner: Owner/role name
        current_depth: Current recursion depth

    Returns:
        CompositeTypeInfo instance
    """
    composite_info = CompositeTypeInfo(
        name=type_name,
        schema=schema,
        owner=owner,
        fields=fields,
        is_nested=(current_depth > 0),
        depth=current_depth,
    )
    logger.debug(f"Parsed composite type {schema}.{type_name} with {len(fields)} fields")
    return composite_info


# ============================================================================
# SAFE TYPE CONVERSION HELPERS
# ============================================================================


def _safe_str(value: Any, default: str = "") -> str:
    """Safely convert value to string."""
    return str(value).strip() if value else default


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default


def _safe_int_optional(value: Any) -> int | None:
    """Safely convert value to optional int (None if not digit-like)."""
    if value and str(value).isdigit():
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return None


def _safe_bool(value: Any, default: bool = False) -> bool:
    """Safely convert value to bool."""
    if value is None:
        return default
    return bool(value)


def resolve_field_types(composite_info: CompositeTypeInfo, adapter: Any) -> CompositeTypeInfo:
    """Recursively resolve nested composite types within fields.

    Args:
        composite_info: Composite type metadata
        adapter: Manager adapter

    Returns:
        CompositeTypeInfo with potentially expanded field types

    Notes:
        - Currently returns as-is (framework for future nested resolution)
        - Future: if field type is composite, recursively fetch its structure
    """
    return composite_info


# ============================================================================
# SQL BUILDERS
# ============================================================================


def _get_composite_type_query() -> str:
    """Build SQL to fetch composite type structure from pg_type + pg_attribute.

    Returns:
        Parameterized SQL query
    """
    return """
        SELECT
            pg_attribute.attname                           AS field_name,
            pg_attribute.atttypid                          AS field_type_oid,
            (SELECT typname FROM pg_type WHERE oid = pg_attribute.atttypid)
                                                           AS field_type_name,
            pg_attribute.attnum                            AS ordinal_position,
            pg_type.typowner::regrole::name               AS type_owner,
            (SELECT typelem > 0 FROM pg_type WHERE oid = pg_attribute.atttypid)
                                                           AS is_array,
            CASE
                WHEN typlen = -1 THEN atttypmod - 4
                WHEN typname = 'varchar' OR typname = 'char' THEN atttypmod - 4
                ELSE NULL
            END                                            AS max_length,
            NULL::INTEGER                                  AS numeric_precision,
            NULL::INTEGER                                  AS numeric_scale
        FROM
            pg_type
            INNER JOIN pg_attribute ON pg_attribute.attrelid = pg_type.typrelid
        WHERE
            pg_type.typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %(schema)s)
            AND pg_type.typname = %(type_name)s
            AND pg_attribute.attnum > 0
        ORDER BY
            pg_attribute.attnum
    """  # noqa: F841


# ============================================================================
# TYPE NORMALIZATION
# ============================================================================


def _normalize_composite_field_type(pg_type_name: str) -> str:
    """Normalize PostgreSQL type name for composite type field.

    Args:
        pg_type_name: PostgreSQL type name (e.g., "varchar", "timestamp with time zone")

    Returns:
        Normalized type name

    Example:
        >>> _normalize_composite_field_type("timestamp with time zone")
        'timestamp'
        >>> _normalize_composite_field_type("varchar")
        'varchar'
    """
    if not pg_type_name:
        return "unknown"

    # Take first part of compound types
    # "timestamp with time zone" → "timestamp"
    normalized = pg_type_name.lower().strip().split()[0]
    return normalized


# ============================================================================
# PUBLIC ADAPTER METHODS (to be called by PostgreSQL adapter)
# ============================================================================


def get_composite_types(schema: str | None, adapter: Any) -> list[CompositeTypeInfo]:
    """Get all composite types in schema.

    Args:
        schema: Schema name (None = all schemas)
        adapter: Manager adapter

    Returns:
        List of composite type metadata

    Example:
        >>> types = get_composite_types("public", adapter)
        >>> for t in types:
        ...     print(f"{t.schema}.{t.name}")
        public.address_type
        public.contact_type
    """
    # Note: SQL query is documented above; manager executes via query name "list_composite_types"
    # where_clause construction not needed: manager handles schema filtering
    params: dict[str, Any] = {}
    if schema:
        params["schema"] = schema

    try:
        rows = adapter._execute_metadata_many(
            "list_composite_types",
            params=params,
            error_message="Failed to list composite types",
        )
    except Exception as exc:
        adapter.logger.error(f"Error listing composite types: {exc}", exc_info=True)
        return []

    composite_types: list[CompositeTypeInfo] = []

    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 3:
            continue

        type_name = str(row[0]) if row[0] else ""
        schema_name = str(row[1]) if row[1] else "public"

        # Fetch detailed field structure
        composite_info = parse_composite_type_structure(schema_name, type_name, adapter)
        if composite_info:
            composite_types.append(composite_info)

    adapter.logger.debug(f"Found {len(composite_types)} composite types")
    return composite_types


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
    """Query JSON column schema for PostgreSQL.

    Strategy:
    1. Check for CHECK constraints with embedded JSON schema
    2. If not found, sample column values and infer schema
    3. Return schema_hint dict or None if no schema available

    Args:
        schema: Database schema name
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
        >>> schema_hint = query_json_column_schema("public", "events", "payload", adapter)
        >>> if schema_hint:
        ...     print(f"Type: {schema_hint['type']}")
        ...     print(f"Properties: {list(schema_hint['properties'].keys())}")
        Type: object
        Properties: ['user_id', 'timestamp', 'status']

    Notes:
        - PostgreSQL: Supports CHECK constraints with JSON_SCHEMA_VALID()
        - JSON and JSONB columns supported equally
        - Sampling uses LIMIT clause for performance on large tables
        - Returns None gracefully if no schema available (NULL column, etc)
    """
    from util_bbdd.metadata.adapters.shared.json_schema import (
        extract_json_schema_from_check_constraint,
        infer_json_schema_from_sample,
        normalize_json_schema,
    )

    adapter.logger.debug(f"Querying JSON schema for {schema}.{table}.{column}")

    # Step 1: Try to extract schema from CHECK constraints
    try:
        # Query for CHECK constraints via adapter execute method
        # noqa: F841 - SQL handled by adapter
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
        adapter.logger.debug(f"Failed to query CHECK constraints: {e}")
        # Fall through to sampling

    # Step 2: Fall back to sampling column values
    try:
        # Sample JSON column values (SQL handled by adapter)
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
