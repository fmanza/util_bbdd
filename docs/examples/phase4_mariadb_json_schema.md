# Phase 4: MariaDB JSON Column Schema Introspection

## Overview

**Feature:** Programmatic inference and extraction of JSON column schemas from MariaDB.

**Introduced:** v0.8.0 (Phase 4a.3)
**Module:** `util_bbdd.metadata.mariadb.types_advanced`
**Supported Versions:** MariaDB 10.2+ (with strong JSON support)

---

## Use Cases

1. **API Schema Generation**
   Extract JSON column structure to auto-generate OpenAPI/GraphQL schemas

2. **Data Validation**
   Build runtime validators based on inferred JSON structure

3. **Type-Safe Code Generation**
   Generate Python dataclasses/TypeScript interfaces from JSON samples

4. **Data Documentation**
   Discover and document unstructured data models automatically

5. **ETL Pipeline Mapping**
   Understand JSON transformations without manual inspection

---

## API Reference

### Main Function: `query_json_column_schema()`

```python
def query_json_column_schema(
    schema: str,
    table: str,
    column: str,
    adapter: MariaDBSyncAdapter | MariaDBAsyncAdapter,
    sample_size: int = 100
) -> dict[str, Any] | None:
    """Query and infer JSON column schema from MariaDB.

    Strategy:
    1. Query CHECK constraints (if defined with JSON schema hints)
    2. Sample up to sample_size rows and infer structure
    3. Return schema_hint dict or None if no data available

    Args:
        schema: Database name (MariaDB: same as database name)
        table: Table name
        column: JSON column name
        adapter: Manager adapter (from manager.adapter)
        sample_size: Max rows to sample (default: 100)

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
    "required": ["field_name", ...]  # Required fields (always present in samples)
}
```

---

## Example: Basic Usage

### Prerequisites

Assume you have a MariaDB table:

```sql
CREATE TABLE events (
    event_id INT PRIMARY KEY AUTO_INCREMENT,
    event_type VARCHAR(50),
    payload JSON,
    created_at TIMESTAMP
);

INSERT INTO events (event_type, payload) VALUES
('user_login', JSON_OBJECT('user_id', 123, 'ip_address', '192.168.1.1')),
('user_purchase', JSON_OBJECT('user_id', 456, 'amount', 99.99, 'items', 2)),
('user_logout', JSON_OBJECT('user_id', 123, 'session_duration', 3600));
```

### Python Code

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.mariadb.types_advanced import query_json_column_schema

manager = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={
        "host": "localhost",
        "user": "root",
        "password": "password",
        "database": "mydb"
    }
)

# Query JSON column schema
schema = query_json_column_schema(
    schema="mydb",
    table="events",
    column="payload",
    adapter=manager.adapter,
    sample_size=100
)

if schema:
    print(f"Root Type: {schema['type']}")
    print(f"Properties: {list(schema['properties'].keys())}")
    print(f"Required: {schema['required']}")

    # Output:
    # Root Type: object
    # Properties: ['user_id', 'ip_address', 'amount', 'items', 'session_duration']
    # Required: ['user_id']

manager.close()
```

---

## Example: Generate Python Dataclass

Convert inferred JSON schema to Python dataclass:

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.mariadb.types_advanced import query_json_column_schema
from typing import Optional, Any
from dataclasses import dataclass

def generate_dataclass_from_schema(schema, class_name):
    """Generate Python dataclass code from JSON schema."""
    lines = ["@dataclass"]
    lines.append(f"class {class_name}:")

    type_mapping = {
        "string": "str",
        "number": "float",
        "integer": "int",
        "boolean": "bool",
        "array": "list[Any]",
        "object": "dict[str, Any]"
    }

    required_fields = set(schema.get("required", []))

    for prop_name, prop_def in schema.get("properties", {}).items():
        prop_type = type_mapping.get(prop_def.get("type", "object"), "Any")

        if prop_name not in required_fields:
            prop_type = f"Optional[{prop_type}] = None"

        lines.append(f"    {prop_name}: {prop_type}")

    return "\n".join(lines)

manager = SyncDatabaseManager(...)
schema = query_json_column_schema("mydb", "events", "payload", adapter=manager.adapter)

if schema:
    dataclass_code = generate_dataclass_from_schema(schema, "EventPayload")
    print(dataclass_code)

    # Output:
    # @dataclass
    # class EventPayload:
    #     user_id: int
    #     ip_address: Optional[str] = None
    #     amount: Optional[float] = None
    #     items: Optional[list[Any]] = None
    #     session_duration: Optional[int] = None

manager.close()
```

---

## Example: Validate JSON Against Schema

Use inferred schema to validate incoming JSON:

```python
import json
from jsonschema import validate, ValidationError

schema = query_json_column_schema("mydb", "events", "payload", adapter=manager.adapter)

# Incoming payload
incoming_json = {
    "user_id": 789,
    "ip_address": "10.0.0.1"
}

try:
    validate(instance=incoming_json, schema=schema)
    print("✅ Valid JSON against schema")
except ValidationError as e:
    print(f"❌ Validation failed: {e.message}")
```

---

## Example: Async Usage

```python
import asyncio
from util_bbdd import AsyncDatabaseManager
from util_bbdd.metadata.mariadb.types_advanced import query_json_column_schema

async def main():
    manager = AsyncDatabaseManager(
        db_type="mariadb",
        conn_params={...}
    )
    await manager.init()

    # Note: query_json_column_schema works with both sync and async adapters
    schema = query_json_column_schema(
        schema="mydb",
        table="events",
        column="payload",
        adapter=manager.adapter,
        sample_size=100
    )

    if schema:
        print(f"JSON Schema: {schema}")

    await manager.close()

asyncio.run(main())
```

---

## Supported MariaDB Versions

- MariaDB 10.2 (first JSON-supporting release)
- MariaDB 10.3, 10.4, 10.5
- MariaDB 10.6 (LTS)
- MariaDB 11.0, 11.1, 11.2, 11.3, 11.4

---

## Error Handling

The function returns `None` if:
- Column does not exist
- Column is empty (no rows with JSON data)
- Column is not JSON type
- User lacks SELECT privilege
- Database connection fails

**No exception is raised** — check for `None` return value:

```python
schema = query_json_column_schema("mydb", "events", "payload", adapter=manager.adapter)
if schema is None:
    print("Schema could not be inferred.")
```

---

## See Also

- [Phase 4 Release Notes](../v0.8.0/RELEASE_v0.8.0.md#phase-4-complete-type-system-coverage)
- [SQLite JSON Schema Introspection](./phase4_sqlite_json_schema.md)
- [Redshift JSON Schema Introspection](./phase4_redshift_json_schema.md)
- [API Reference: Metadata Type Introspection](../API_REFERENCE.md#metadata-type-introspection-phase-4)
