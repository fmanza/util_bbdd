# PostgreSQL Driver — Quick Reference Guide

## Import & Usage

### Basic Setup

```python
from util_bbdd import SyncDatabaseManager, AsyncDatabaseManager

# Connect to PostgreSQL
manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
        "database": "mydb"
    }
)
```

### Fetch Metadata (Sync)

```python
# Tables & columns
tables = manager.get_tables(schema="public")
columns = manager.get_columns(schema="public", tabla="users")

# Constraints
pks = manager.get_primary_keys(schema="public", tabla="users")
fks = manager.get_foreign_keys(schema="public", tabla="orders")
indexes = manager.get_indexes(schema="public", tabla="users")

# Routines (functions/procedures)
functions = manager.get_routines(schema="public")
params = manager.get_routine_parameters(
    tabla="calculate_total",
    routine_type="FUNCTION"
)
```

### Fetch Metadata (Async)

```python
import asyncio

async def introspect():
    async_manager = AsyncDatabaseManager(
        db_type="postgresql",
        conn_params={...}
    )

    tables = await async_manager.get_tables(schema="public")
    columns = await async_manager.get_columns(schema="public", tabla="users")

    await async_manager.close()

asyncio.run(introspect())
```

### Generate Documentation

```python
from util_bbdd import generate_document

# Generate Word documentation (all drivers, same API)
document = manager.generate_document(
    output_format="docx",
    output_file="database_docs.docx",
    include_diagrams=True
)

# Generate Markdown
markdown = manager.generate_document(
    output_format="markdown",
    output_file="schema.md"
)

# HTML with Mermaid diagrams
html = manager.generate_document(
    output_format="html",
    output_file="schema.html",
    include_diagrams=True
)
```

## Registry Access (Advanced)

### Get PostgreSQL Adapter Directly

```python
from util_bbdd.metadata.adapters import get_global_adapter_registry
from util_bbdd.metadata.postgresql import PostgreSQLSyncAdapter

# Resolve adapter
registry = get_global_adapter_registry()
adapter_class = registry.get_source_adapter_sync("postgresql")
adapter = adapter_class(manager)  # Inject manager

# Use adapter directly
tables = adapter.fetch_tables_sync("public")
```

### Check Registered Drivers

```python
registry = get_global_adapter_registry()

# List all registered drivers
drivers = registry.list_registered_drivers()
print(drivers)  # {'mariadb', 'postgresql', ...}

# Check if PostgreSQL is registered
if registry.is_driver_registered("postgresql"):
    print("✅ PostgreSQL driver available")
```

## Type Mapping Reference

| PostgreSQL Type | Normalized Type | Example |
|-----------------|-----------------|---------|
| `integer`, `int4`, `int8` | `INT` | `id` column |
| `numeric`, `decimal` | `NUMERIC` | Price with precision |
| `real`, `double precision` | `FLOAT` | Coordinates |
| `character varying`, `varchar` | `VARCHAR` | Names, emails |
| `character`, `char` | `CHAR` | Codes |
| `text` | `TEXT` | Descriptions |
| `boolean`, `bool` | `BOOLEAN` | Flags |
| `timestamp`, `timestamp with time zone` | `TIMESTAMP` | Created dates |
| `date` | `DATE` | Birth dates |
| `time` | `TIME` | Clock times |
| `bytea` | `BLOB` | Binary data |
| `uuid` | `UUID` | Unique IDs |
| `json`, `jsonb` | `JSON` | Structured data |
| `integer[]`, `text[]` | `ARRAY` | Bulk data |

## Performance Tips

### Optimize for Large Schemas (500+ tables)

```python
# Batch introspection with caching
# (manager handles caching automatically)

# Recommended: Fetch once, reuse
schema_metadata = manager.get_all_schema_metadata(schema="public")
# Internally caches table/column/constraint info

# Avoid: Multiple calls for same data
tables1 = manager.get_tables(schema="public")  # ❌ Re-queries
tables2 = manager.get_tables(schema="public")  # ❌ Re-queries again
```

### Parallel Async Introspection

```python
import asyncio

async def parallel_introspect():
    manager = AsyncDatabaseManager(db_type="postgresql", conn_params={...})

    # Fetch multiple schemas in parallel
    results = await asyncio.gather(
        manager.get_tables(schema="public"),
        manager.get_tables(schema="staging"),
        manager.get_tables(schema="archive"),
    )

    await manager.close()
    return results
```

## Common Queries

### Find Tables by Pattern

```python
tables = manager.get_tables(schema="public")
user_tables = [t for t in tables if "user" in t[0].lower()]
```

### Get Composite FK Information

```python
fks = manager.get_foreign_keys(schema="public", tabla="orders")
# Returns: (constraint_name, column, ref_schema, ref_table, ref_column, ...)

for fk in fks:
    constraint, col, ref_schema, ref_table, ref_col = fk[:5]
    print(f"{constraint}: {col} → {ref_table}.{ref_col}")
```

### List All Routines in Schema

```python
routines = manager.get_routines(schema="public")
# Returns: (routine_name, routine_type, routine_owner, ...)

functions = [r for r in routines if r[1] == "FUNCTION"]
procedures = [r for r in routines if r[1] == "PROCEDURE"]

print(f"Functions: {len(functions)}")
print(f"Procedures: {len(procedures)}")
```

## Troubleshooting

### Permission Denied on Schema

```
DatabaseOperationError: Insufficient privileges to introspect public...
```

**Solution:** Grant privileges to role:
```sql
GRANT USAGE ON SCHEMA public TO your_role;
GRANT SELECT ON information_schema.* TO your_role;
```

### "Schema Not Found"

```
ValueError: Schema 'myschema' not found or inaccessible
```

**Solution:** Check schema exists:
```sql
SELECT schema_name FROM information_schema.schemata
WHERE schema_name = 'myschema';
```

### Type Mapping Shows "UNKNOWN"

```python
# This indicates a PostgreSQL type not in the standard mapping
# Check actual type:
columns = manager.get_columns(schema="public", tabla="mytable")
for col in columns:
    print(col)  # See raw PostgreSQL type name
```

**Report:** File issue with PostgreSQL type + version info

## Integration with MariaDB

### Side-by-Side Support

```python
# Document BOTH databases
pg_manager = SyncDatabaseManager(db_type="postgresql", conn_params={...})
mariadb_manager = SyncDatabaseManager(db_type="mariadb", conn_params={...})

# Same API, different backends
pg_schema = pg_manager.get_schema_metadata()
mdb_schema = mariadb_manager.get_schema_metadata()

# Compare schemas
if pg_schema == mdb_schema:
    print("✅ Schemas match across engines")
```

### Migration Path

```python
# Step 1: Extract from MariaDB
source = SyncDatabaseManager(db_type="mariadb", conn_params=mdb_params)
tables = source.get_all_schema_metadata()

# Step 2: Generate PostgreSQL DDL
# (util_bbdd generates DDL for any database represented in metadata)
pg_ddl = manager.generate_ddl_for_tables(tables, target_dialect="postgresql")

# Step 3: Validate against target PostgreSQL
target = SyncDatabaseManager(db_type="postgresql", conn_params=pg_params)
target_tables = target.get_all_schema_metadata()

print(f"MariaDB tables: {len(tables)}")
print(f"PostgreSQL tables: {len(target_tables)}")
```

---

**For more examples, see:**
- [PostgreSQL Adapter Tests](../../../tests/unit/test_postgresql_adapter_tables.py)
- [Phase 3C.1 Completion Report](./PHASE_3C1_COMPLETION_REPORT.md)
- [Main Documentation](../../README.md)
