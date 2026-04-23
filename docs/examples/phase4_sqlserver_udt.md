# Phase 4: SQL Server User-Defined Type (UDT) Introspection

## Overview

**Feature:** Programmatic discovery and parsing of SQL Server user-defined structured types.

**Introduced:** v0.8.0 (Phase 4a.2)
**Module:** `util_bbdd.metadata.sqlserver.types_advanced`
**Supported Versions:** SQL Server 2005 through 2022

---

## Use Cases

1. **Type-Safe ORM Generation**
   Extract UDT member structure to auto-generate entity classes

2. **API Schema Documentation**
   Generate OpenAPI schemas from SQL Server UDT definitions

3. **Database-to-Code Mapping**
   Create TypeScript/C# interfaces that mirror SQL types

4. **Data Validation**
   Programmatically build validators based on UDT member constraints

5. **Schema Change Tracking**
   Monitor UDT member additions/modifications across environments

---

## API Reference

### Main Function: `parse_udt_structure()`

```python
def parse_udt_structure(
    type_name: str,
    adapter: SQLServerSyncAdapter | SQLServerAsyncAdapter
) -> UDTTypeInfo | None:
    """Parse a SQL Server UDT into structured metadata.

    Args:
        type_name: Name of the UDT (e.g., 'PersonType')
        adapter: Manager adapter (from manager.adapter)

    Returns:
        UDTTypeInfo with members list, or None if type not found
    """
```

### Data Structures

#### `UDTTypeInfo`

```python
@dataclass(frozen=True)
class UDTTypeInfo:
    type_name: str                    # E.g., 'PersonType'
    schema: str                       # Schema, e.g., 'dbo'
    kind: str                         # 'STRUCTURED' | 'HIERARCHY' | 'NATIVE'
    members: list[UDTMember]          # List of member definitions
```

#### `UDTMember`

```python
@dataclass(frozen=True)
class UDTMember:
    name: str                         # Member name, e.g., 'PersonID'
    type_name: str                    # Type name, e.g., 'int'
    ordinal_position: int             # Position in UDT (1-based)
    is_nullable: bool                 # True if member allows NULL
    max_length: int | None            # For string types, -1 = MAX
    precision: int | None             # For numeric types
    scale: int | None                 # For numeric types
```

---

## Example: Basic Usage

### Prerequisites

Assume you have a SQL Server database with this UDT:

```sql
CREATE TYPE dbo.PersonType AS TABLE (
    PersonID        INT NOT NULL,
    FirstName       VARCHAR(50),
    LastName        VARCHAR(50),
    EmailAddress    VARCHAR(100),
    BirthDate       DATE
);
```

### Python Code

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.sqlserver.types_advanced import parse_udt_structure

manager = SyncDatabaseManager(
    db_type="sqlserver",
    conn_params={
        "server": "localhost",
        "database": "mydb",
        "user": "sa",
        "password": "YourPassword123!"
    }
)

# Parse the UDT
udt_info = parse_udt_structure("PersonType", adapter=manager.adapter)

if udt_info:
    print(f"UDT: {udt_info.type_name} (Schema: {udt_info.schema})")
    for member in udt_info.members:
        print(f"  {member.ordinal_position}. {member.name}: {member.type_name} "
              f"(nullable={member.is_nullable})")
        # Output:
        #   1. PersonID: int (nullable=False)
        #   2. FirstName: varchar (nullable=True)
        #   3. LastName: varchar (nullable=True)
        #   4. EmailAddress: varchar (nullable=True)
        #   5. BirthDate: date (nullable=True)

manager.close()
```

---

## Example: Generate TypeScript Interfaces

Convert SQL Server UDT to TypeScript:

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.sqlserver.types_advanced import parse_udt_structure

def sql_to_typescript_type(udt_info):
    """Generate TypeScript interface from SQL Server UDT."""
    interface_name = udt_info.type_name
    lines = [f"export interface {interface_name} {{"]

    type_mapping = {
        "int": "number",
        "bigint": "number",
        "float": "number",
        "decimal": "number",
        "varchar": "string",
        "char": "string",
        "nvarchar": "string",
        "date": "Date",
        "datetime": "Date",
        "datetime2": "Date"
    }

    for member in udt_info.members:
        ts_type = type_mapping.get(member.type_name.lower(), "any")
        optional = "?" if member.is_nullable else ""
        lines.append(f"  {member.name}{optional}: {ts_type};")

    lines.append("}")
    return "\n".join(lines)

manager = SyncDatabaseManager(...)
udt_info = parse_udt_structure("PersonType", adapter=manager.adapter)

if udt_info:
    typescript_code = sql_to_typescript_type(udt_info)
    print(typescript_code)

    # Output:
    # export interface PersonType {
    #   PersonID: number;
    #   FirstName?: string;
    #   LastName?: string;
    #   EmailAddress?: string;
    #   BirthDate?: Date;
    # }

manager.close()
```

---

## Example: Async Usage

```python
import asyncio
from util_bbdd import AsyncDatabaseManager
from util_bbdd.metadata.sqlserver.types_advanced import parse_udt_structure

async def main():
    manager = AsyncDatabaseManager(
        db_type="sqlserver",
        conn_params={...}
    )
    await manager.init()

    # Note: parse_udt_structure works with both sync and async adapters
    udt_info = parse_udt_structure("PersonType", adapter=manager.adapter)

    if udt_info:
        print(f"UDT: {udt_info.type_name}")
        for member in udt_info.members:
            print(f"  {member.name}: {member.type_name}")

    await manager.close()

asyncio.run(main())
```

---

## Supported SQL Server Versions

- SQL Server 2005 (9.0.1)
- SQL Server 2008 (10.0, 10.5)
- SQL Server 2012 (11.0)
- SQL Server 2014 (12.0)
- SQL Server 2016 (13.0)
- SQL Server 2017 (14.0)
- SQL Server 2019 (15.0)
- SQL Server 2022 (16.0)

---

## Error Handling

The function returns `None` if:
- UDT does not exist
- User lacks SELECT privilege on `sys.types`/`sys.type_members`
- Type is not a structured type (e.g., built-in scalar)
- Database connection fails

**No exception is raised** — check for `None` return value:

```python
udt_info = parse_udt_structure("NONEXISTENT_TYPE", adapter=manager.adapter)
if udt_info is None:
    print("UDT not found or parsing failed.")
```

---

## See Also

- [Phase 4 Release Notes](../v0.8.0/RELEASE_v0.8.0.md#phase-4-complete-type-system-coverage)
- [Oracle OBJECT Type Introspection](./phase4_oracle_object_types.md)
- [JSON Schema Introspection](./phase4_mariadb_json_schema.md)
- [API Reference: Metadata Type Introspection](../API_REFERENCE.md#metadata-type-introspection-phase-4)
