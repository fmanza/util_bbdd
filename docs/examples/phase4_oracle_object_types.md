# Phase 4: Oracle OBJECT Type Introspection

## Overview

**Feature:** Programmatic discovery and parsing of Oracle user-defined OBJECT types.

**Introduced:** v0.8.0 (Phase 4a)
**Module:** `util_bbdd.metadata.oracle.types_advanced`

---

## Use Cases

1. **API Documentation Generation**
   Extract OBJECT type structure to auto-generate OpenAPI/Swagger schemas

2. **Form Validation**
   Discover field types and nullability to build dynamic validators

3. **Type Synchronization**
   Compare OBJECT type definitions across development/staging/production

4. **ETL Data Mapping**
   Programmatically understand type hierarchies for data transformation

---

## API Reference

### Main Function: `parse_object_type_structure()`

```python
def parse_object_type_structure(
    type_name: str,
    adapter: OracleSyncAdapter | OracleAsyncAdapter
) -> ObjectTypeInfo | None:
    """Parse an Oracle OBJECT type into structured metadata.

    Args:
        type_name: Name of the OBJECT type (e.g., 'CUSTOMER_TYPE')
        adapter: Manager adapter (from manager.adapter)

    Returns:
        ObjectTypeInfo with fields list, or None if type not found
    """
```

### Data Structures

#### `ObjectTypeInfo`

```python
@dataclass(frozen=True)
class ObjectTypeInfo:
    type_name: str                    # E.g., 'CUSTOMER_TYPE'
    owner: str                        # Schema/owner, e.g., 'SCOTT'
    fields: list[ObjectTypeField]     # List of field definitions
```

#### `ObjectTypeField`

```python
@dataclass(frozen=True)
class ObjectTypeField:
    name: str                         # Field name, e.g., 'CUSTOMER_ID'
    type_name: str                    # Type name, e.g., 'NUMBER'
    ordinal_position: int             # Position in OBJECT (1-based)
    is_nullable: bool                 # True if field allows NULL
    precision: int | None             # For numeric types (e.g., 10)
    scale: int | None                 # For numeric types (e.g., 2)
```

---

## Example: Basic Usage

### Prerequisites

Assume you have an Oracle database with this OBJECT type:

```sql
CREATE TYPE CUSTOMER_TYPE AS OBJECT (
    customer_id     NUMBER(10),
    first_name      VARCHAR2(50),
    last_name       VARCHAR2(50),
    email           VARCHAR2(100),
    created_date    DATE
);
```

### Python Code

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.oracle.types_advanced import parse_object_type_structure

manager = SyncDatabaseManager(
    db_type="oracle",
    conn_params={
        "dsn": "ORCL",
        "user": "scott",
        "password": "tiger"
    }
)

# Parse the type
type_info = parse_object_type_structure("CUSTOMER_TYPE", adapter=manager.adapter)

if type_info:
    print(f"Type: {type_info.type_name} (Owner: {type_info.owner})")
    for field in type_info.fields:
        print(f"  {field.ordinal_position}. {field.name}: {field.type_name} "
              f"(nullable={field.is_nullable})")
        # Output:
        #   1. CUSTOMER_ID: NUMBER (nullable=False)
        #   2. FIRST_NAME: VARCHAR2 (nullable=True)
        #   3. LAST_NAME: VARCHAR2 (nullable=True)
        #   4. EMAIL: VARCHAR2 (nullable=True)
        #   5. CREATED_DATE: DATE (nullable=True)

manager.close()
```

---

## Example: Serialize to JSON

Extract OBJECT type metadata as JSON for API responses:

```python
type_info = parse_object_type_structure("CUSTOMER_TYPE", adapter=manager.adapter)

schema = {
    "type_name": type_info.type_name,
    "owner": type_info.owner,
    "fields": [field.to_dict() for field in type_info.fields]
}

import json
print(json.dumps(schema, indent=2))

# Output:
# {
#   "type_name": "CUSTOMER_TYPE",
#   "owner": "SCOTT",
#   "fields": [
#     {
#       "name": "CUSTOMER_ID",
#       "type": "NUMBER",
#       "ordinal_position": 1,
#       "nullable": false,
#       "precision": 10
#     },
#     {
#       "name": "FIRST_NAME",
#       "type": "VARCHAR2",
#       "ordinal_position": 2,
#       "nullable": true
#     },
#     ...
#   ]
# }
```

---

## Example: Async Usage

```python
import asyncio
from util_bbdd import AsyncDatabaseManager
from util_bbdd.metadata.oracle.types_advanced import parse_object_type_structure

async def main():
    manager = AsyncDatabaseManager(
        db_type="oracle",
        conn_params={...}
    )
    await manager.init()

    # Note: parse_object_type_structure works with both sync and async adapters
    type_info = parse_object_type_structure("CUSTOMER_TYPE", adapter=manager.adapter)

    if type_info:
        print(f"Type: {type_info.type_name}")
        for field in type_info.fields:
            print(f"  {field.name}: {field.type_name}")

    await manager.close()

asyncio.run(main())
```

---

## Supported Oracle Versions

- Oracle 9i (9.0.1)
- Oracle 10g (10.1, 10.2)
- Oracle 11g (11.1, 11.2)
- Oracle 12c (12.1, 12.2)
- Oracle 18c
- Oracle 19c
- Oracle 21c

---

## Error Handling

The function returns `None` if:
- Type does not exist
- Type is not an OBJECT type (e.g., SCALAR type)
- User lacks SELECT privilege on `dba_types`/`dba_type_attrs`
- Database connection fails

**No exception is raised** — check for `None` return value:

```python
type_info = parse_object_type_structure("NONEXISTENT_TYPE", adapter=manager.adapter)
if type_info is None:
    print("Type not found or parsing failed.")
```

---

## See Also

- [Phase 4 Release Notes](../v0.8.0/RELEASE_v0.8.0.md#phase-4-complete-type-system-coverage)
- [SQL Server UDT Introspection](./phase4_sqlserver_udt.md)
- [API Reference: Metadata Type Introspection](../API_REFERENCE.md#metadata-type-introspection-phase-4)
