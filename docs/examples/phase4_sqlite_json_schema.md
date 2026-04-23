# Phase 4: SQLite JSON Column Schema Introspection

## Overview

**Feature:** Programmatic inference and extraction of JSON column schemas from SQLite.

**Introduced:** v0.8.0 (Phase 4a.5)
**Module:** `util_bbdd.metadata.sqlite.types_advanced`
**Supported Versions:** SQLite 3.38+ (with JSON1 extension)

---

## Use Cases

1. **Embedded Database Schema Discovery**
   Automatically discover JSON structure in SQLite applications

2. **Test Data Generation**
   Generate realistic test data based on sampled JSON schemas

3. **API Documentation**
   Export SQLite JSON column structure as OpenAPI schemas

4. **Type-Safe Serialization**
   Generate Python dataclasses from JSON column samples

5. **Database Migration Planning**
   Understand unstructured data before schema normalization

---

## API Reference

### Main Function: `query_json_column_schema()`

```python
def query_json_column_schema(
    schema: str,
    table: str,
    column: str,
    adapter: SQLiteSyncAdapter | SQLiteAsyncAdapter,
    sample_size: int = 100
) -> dict[str, Any] | None:
    """Query and infer JSON column schema from SQLite.

    Strategy:
    1. Sample up to sample_size rows from column
    2. Infer structure from JSON samples
    3. Return schema_hint dict or None if no data available

    Args:
        schema: Database name (SQLite: "main" for main database)
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
    "required": ["field_name", ...]  # Fields present in all samples
}
```

---

## Example: Basic Usage

### Prerequisites

Assume you have a SQLite database with this table:

```sql
CREATE TABLE documents (
    doc_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP
);

INSERT INTO documents (title, metadata) VALUES
('Document 1', JSON_OBJECT('author', 'Alice', 'version', 1, 'tags', JSON_ARRAY('draft'))),
('Document 2', JSON_OBJECT('author', 'Bob', 'version', 2, 'tags', JSON_ARRAY('final', 'published'))),
('Document 3', JSON_OBJECT('author', 'Charlie', 'version', 1, 'tags', JSON_ARRAY('review')));
```

### Python Code

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.sqlite.types_advanced import query_json_column_schema

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={
        "database": "/path/to/mydb.sqlite3"
    }
)

# Query JSON column schema
schema = query_json_column_schema(
    schema="main",
    table="documents",
    column="metadata",
    adapter=manager.adapter,
    sample_size=100
)

if schema:
    print(f"Root Type: {schema['type']}")
    print(f"Properties: {list(schema['properties'].keys())}")
    print(f"Required: {schema['required']}")

    # Output:
    # Root Type: object
    # Properties: ['author', 'version', 'tags']
    # Required: ['author', 'version', 'tags']

manager.close()
```

---

## Example: Export to Python Type Hints

Generate Python type hints from inferred schema:

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.sqlite.types_advanced import query_json_column_schema
from typing import Optional

def schema_to_type_hint(schema, field_name="data"):
    """Generate Python type hint from JSON schema."""
    type_mapping = {
        "string": "str",
        "number": "float",
        "integer": "int",
        "boolean": "bool",
        "array": "list",
        "object": "dict"
    }

    hint_parts = []
    for prop_name, prop_def in schema.get("properties", {}).items():
        prop_type = type_mapping.get(prop_def.get("type"), "Any")
        hint_parts.append(f"  {prop_name}: {prop_type}")

    return f"{field_name}: dict[str, Any] = {{\n" + ",\n".join(hint_parts) + "\n}"

manager = SyncDatabaseManager(...)
schema = query_json_column_schema("main", "documents", "metadata", adapter=manager.adapter)

if schema:
    type_hint = schema_to_type_hint(schema, "metadata")
    print(type_hint)

    # Output:
    # metadata: dict[str, Any] = {
    #   author: str,
    #   version: int,
    #   tags: list
    # }

manager.close()
```

---

## Example: Query Multiple JSON Columns

Discover schemas for all JSON columns in a table:

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.sqlite.types_advanced import query_json_column_schema

manager = SyncDatabaseManager(db_type="sqlite", conn_params={...})

# Assume table has multiple JSON columns
json_columns = ["metadata", "attributes", "tags_data"]

schemas = {}
for col_name in json_columns:
    schema = query_json_column_schema("main", "documents", col_name, adapter=manager.adapter)
    if schema:
        schemas[col_name] = schema
        print(f"✅ {col_name}: {list(schema['properties'].keys())}")
    else:
        print(f"⚠️  {col_name}: Could not infer schema")

manager.close()
```

---

## Example: Async Usage

```python
import asyncio
from util_bbdd import AsyncDatabaseManager
from util_bbdd.metadata.sqlite.types_advanced import query_json_column_schema

async def main():
    manager = AsyncDatabaseManager(
        db_type="sqlite",
        conn_params={"database": "/path/to/mydb.sqlite3"}
    )
    await manager.init()

    # Note: query_json_column_schema works with both sync and async adapters
    schema = query_json_column_schema(
        schema="main",
        table="documents",
        column="metadata",
        adapter=manager.adapter,
        sample_size=100
    )

    if schema:
        print(f"JSON Schema: {schema}")

    await manager.close()

asyncio.run(main())
```

---

## Supported SQLite Versions

- SQLite 3.38.0+ (JSON1 extension required)
- SQLite 3.39, 3.40, 3.41, 3.42, 3.43, 3.44 (latest)

**Note:** JSON1 extension must be compiled into SQLite. Check with:

```python
import sqlite3
conn = sqlite3.connect(":memory:")
cursor = conn.cursor()
cursor.execute("SELECT json_array(1, 2, 3)")
result = cursor.fetchone()
print(result)  # If JSON1 works, prints: ([1,2,3],)
```

---

## Error Handling

The function returns `None` if:
- Column does not exist
- Column is empty (no rows)
- Column is not JSON type or contains non-JSON data
- JSON1 extension not available
- User lacks SELECT privilege
- Database connection fails

**No exception is raised** — check for `None` return value:

```python
schema = query_json_column_schema("main", "documents", "metadata", adapter=manager.adapter)
if schema is None:
    print("Schema could not be inferred.")
```

---

## See Also

- [Phase 4 Release Notes](../v0.8.0/RELEASE_v0.8.0.md#phase-4-complete-type-system-coverage)
- [MariaDB JSON Schema Introspection](./phase4_mariadb_json_schema.md)
- [Redshift JSON Schema Introspection](./phase4_redshift_json_schema.md)
- [API Reference: Metadata Type Introspection](../API_REFERENCE.md#metadata-type-introspection-phase-4)
