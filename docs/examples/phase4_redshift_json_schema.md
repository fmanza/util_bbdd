# Phase 4: Redshift JSON Column Schema Introspection

## Overview

**Feature:** Programmatic inference and extraction of JSON column schemas from AWS Redshift.

**Introduced:** v0.8.0 (Phase 4a.4)
**Module:** `util_bbdd.metadata.redshift.types_advanced`
**Supported Versions:** Redshift 1.0+ (works with both SUPER and VARCHAR JSON columns)

---

## Use Cases

1. **Data Lake Schema Discovery**
   Automatically discover JSON structure in raw data dumps

2. **ETL Data Contracts**
   Generate data contracts from sampled event streams

3. **Anomaly Detection**
   Monitor schema changes in high-volume streaming data

4. **API Schema Extraction**
   Generate GraphQL/REST schemas from Redshift SUPER columns

5. **Data Governance**
   Document unstructured data models in your data warehouse

---

## API Reference

### Main Function: `query_json_column_schema()`

```python
def query_json_column_schema(
    schema: str,
    table: str,
    column: str,
    adapter: RedshiftSyncAdapter | RedshiftAsyncAdapter,
    sample_size: int = 100
) -> dict[str, Any] | None:
    """Query and infer JSON column schema from Redshift.

    Strategy:
    1. Sample up to sample_size rows from column
    2. Infer structure from JSON samples (works with SUPER or VARCHAR)
    3. Return schema_hint dict or None if no data available

    Args:
        schema: Schema name (Redshift: typically "public" or custom)
        table: Table name
        column: JSON column name (SUPER or VARCHAR with JSON)
        adapter: Manager adapter (from manager.adapter)
        sample_size: Max rows to sample (default: 100, recommend 1000+ for data lakes)

    Returns:
        Dict with schema structure or None if column is empty/not JSON
    """
```

---

## Returned Schema Structure

```python
{
    "type": "object",              # Root type: "object", "array", "string", or "mixed"
    "properties": {
        "field_name": {
            "type": "string"       # Field type: "string", "number", "integer", "boolean", "array", "object"
        },
        # ... more fields
    },
    "required": ["field_name", ...]  # Fields present in all samples
}
```

---

## Example: Basic Usage

### Prerequisites

Assume you have a Redshift cluster with this table:

```sql
CREATE TABLE events (
    event_id BIGINT,
    event_time TIMESTAMP,
    event_data SUPER  -- or VARCHAR(MAX) containing JSON
);

INSERT INTO events VALUES
(1, '2024-01-01 10:00:00', JSON_PARSE('{"user_id": 123, "action": "login", "ip": "192.168.1.1"}')),
(2, '2024-01-01 10:05:00', JSON_PARSE('{"user_id": 456, "action": "purchase", "amount": 99.99}')),
(3, '2024-01-01 10:10:00', JSON_PARSE('{"user_id": 123, "action": "logout", "session_duration": 600}'));
```

### Python Code

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.redshift.types_advanced import query_json_column_schema

manager = SyncDatabaseManager(
    db_type="redshift",
    conn_params={
        "host": "my-redshift-cluster.xxxx.us-east-1.redshift.amazonaws.com",
        "port": 5439,
        "database": "analytics",
        "user": "admin",
        "password": "YourPassword123!"
    }
)

# Query JSON column schema
schema = query_json_column_schema(
    schema="public",
    table="events",
    column="event_data",
    adapter=manager.adapter,
    sample_size=1000  # Larger sample for data lake analysis
)

if schema:
    print(f"Root Type: {schema['type']}")
    print(f"Properties: {list(schema['properties'].keys())}")
    print(f"Required: {schema['required']}")

    # Output:
    # Root Type: object
    # Properties: ['user_id', 'action', 'ip', 'amount', 'session_duration']
    # Required: ['user_id', 'action']

manager.close()
```

---

## Example: Generate Data Contract (dbt/Great Expectations)

Convert inferred schema to data validation format:

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.redshift.types_advanced import query_json_column_schema

def schema_to_dbt_columns(schema, column_name):
    """Generate dbt columns.yml from JSON schema."""
    yaml_lines = [f"- name: {column_name}"]
    yaml_lines.append("  description: 'Inferred from JSON sampling'")
    yaml_lines.append("  columns:")

    for prop_name, prop_def in schema.get("properties", {}).items():
        prop_type = prop_def.get("type", "object")
        required = "required" if prop_name in schema.get("required", []) else "optional"

        yaml_lines.append(f"    - name: {prop_name}")
        yaml_lines.append(f"      data_type: {prop_type}")
        yaml_lines.append(f"      description: '{required}'")

    return "\n".join(yaml_lines)

manager = SyncDatabaseManager(...)
schema = query_json_column_schema("public", "events", "event_data", adapter=manager.adapter, sample_size=1000)

if schema:
    dbt_yaml = schema_to_dbt_columns(schema, "event_data")
    print(dbt_yaml)

    # Output:
    # - name: event_data
    #   description: 'Inferred from JSON sampling'
    #   columns:
    #     - name: user_id
    #       data_type: integer
    #       description: 'required'
    #     - name: action
    #       data_type: string
    #       description: 'required'

manager.close()
```

---

## Example: Monitor Schema Drift

Track schema changes over time:

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.redshift.types_advanced import query_json_column_schema

manager = SyncDatabaseManager(...)

# Baseline schema (from 1 week ago)
baseline_schema = {
    "properties": {
        "user_id": {"type": "integer"},
        "action": {"type": "string"},
        "ip": {"type": "string"}
    }
}

# Current schema
current_schema = query_json_column_schema(
    "public", "events", "event_data",
    adapter=manager.adapter,
    sample_size=1000
)

# Detect schema drift
baseline_props = set(baseline_schema["properties"].keys())
current_props = set(current_schema["properties"].keys())

new_fields = current_props - baseline_props
removed_fields = baseline_props - current_props
common_fields = baseline_props & current_props

if new_fields:
    print(f"⚠️  New fields detected: {new_fields}")

if removed_fields:
    print(f"🔴 Fields removed: {removed_fields}")

if not new_fields and not removed_fields:
    print("✅ Schema stable (no drift detected)")

manager.close()
```

---

## Example: Async Usage

```python
import asyncio
from util_bbdd import AsyncDatabaseManager
from util_bbdd.metadata.redshift.types_advanced import query_json_column_schema

async def main():
    manager = AsyncDatabaseManager(
        db_type="redshift",
        conn_params={...}
    )
    await manager.init()

    # Note: query_json_column_schema works with both sync and async adapters
    schema = query_json_column_schema(
        schema="public",
        table="events",
        column="event_data",
        adapter=manager.adapter,
        sample_size=1000
    )

    if schema:
        print(f"JSON Schema: {schema}")

    await manager.close()

asyncio.run(main())
```

---

## Supported Redshift Versions

- Redshift 1.0+
- Works with both SUPER data type and VARCHAR(MAX) containing JSON
- Compatible with Redshift Spectrum (external tables)

---

## Performance Notes

- **sample_size parameter:** For data lakes with billions of rows, use larger sample sizes (1000+) for accurate schema inference
- **Execution time:** Sampling scales linearly with sample_size; typical query: 1-5 seconds for 1000 rows
- **Network overhead:** Results are returned as dict, minimal network transfer

---

## Error Handling

The function returns `None` if:
- Column does not exist
- Column is empty (no rows with JSON data)
- Column is not JSON-compatible (SUPER or VARCHAR)
- User lacks SELECT privilege
- Redshift connection fails
- Query timeout (large tables with complex JSON)

**No exception is raised** — check for `None` return value:

```python
schema = query_json_column_schema("public", "events", "event_data", adapter=manager.adapter)
if schema is None:
    print("Schema could not be inferred.")
```

---

## See Also

- [Phase 4 Release Notes](../v0.8.0/RELEASE_v0.8.0.md)
- [MariaDB JSON Schema Introspection](./phase4_mariadb_json_schema.md)
- [SQLite JSON Schema Introspection](./phase4_sqlite_json_schema.md)
- [API Reference: Metadata Type Introspection](../API_REFERENCE.md#metadata-type-introspection-phase-4)
