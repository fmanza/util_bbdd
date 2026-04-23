# API Reference — Índice de Clases Públicas

Referencia rápida de las clases y métodos públicos de util_bbdd.

## Tabla de Contenidos

- [Managers (Entrada Principal)](#managers-entrada-principal)
- [Bulk Operations](#bulk-operations)
- [Analysis & Graphs](#analysis--graphs)
- [Schema Comparison](#schema-comparison)
- [Exceptions](#exceptions)
- [Type Hints](#type-hints)

---

## Managers (Entrada Principal)

### SyncDatabaseManager

**Ubicación:** `src/util_bbdd/managers/sync_database_manager.py`

Manager sincrónico para operaciones de BD.

| Método | Parámetros | Retorna | Descripción |
|--------|-----------|---------|-------------|
| `__init__()` | `db_type: str`, `conn_params: dict`, `use_pool: bool = False` | - | Inicializar manager sincrónico |
| `get_connection()` | - | `Connection` | Obtener conexión cruda del pool |
| `get_tables()` | `schema: str \| None = None` | `Rows` | Listar tablas (retorna lista de tuplas) |
| `get_columns()` | `table_name: str`, `schema: str \| None = None` | `Rows` | Listar columnas de tabla con tipos |
| `get_views()` | `schema: str \| None = None` | `Rows` | Listar vistas |
| `get_table_primary_keys()` | `table_name: str` | `Rows` | Obtener claves primarias |
| `get_table_foreign_keys()` | `table_name: str` | `Rows` | Obtener claves foráneas |
| `execute_custom_many()` | `query: str`, `params: dict \| None = None` | `Rows` | Ejecutar query, retorna múltiples filas |
| `execute_custom_one()` | `query: str`, `params: dict \| None = None` | `RowOrNone` | Ejecutar query, retorna 1 fila o None |
| `close()` | - | - | Cerrar conexión y pool |

**Ejemplo:**

```python
from util_bbdd import SyncDatabaseManager

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

# Obtener metadatos
tables = manager.get_tables()
columns = manager.get_columns("users")

# Ejecutar queries
result = manager.execute_custom_many(
    "SELECT * FROM users WHERE age > :age",
    {"age": 18}
)

for row in result:
    print(row)

manager.close()
```

---

### AsyncDatabaseManager

**Ubicación:** `src/util_bbdd/managers/async_database_manager.py`

Manager asincrónico para operaciones concurrentes de BD.

| Método | Parámetros | Retorna | Descripción |
|--------|-----------|---------|-------------|
| `__init__()` | `db_type: str`, `conn_params: dict`, `use_pool: bool = True`, `pool_size: int = 10` | - | Inicializar manager async |
| `init()` | - | `Coroutine[None]` | Inicializar pool y conexiones **REQUERIDO antes de usar** |
| `get_tables()` | `schema: str \| None = None` | `Coroutine[Rows]` | Listar tablas (async) |
| `get_columns()` | `table_name: str`, `schema: str \| None = None` | `Coroutine[Rows]` | Listar columnas (async) |
| `get_views()` | `schema: str \| None = None` | `Coroutine[Rows]` | Listar vistas (async) |
| `execute_custom_many()` | `query: str`, `params: dict \| None = None` | `Coroutine[Rows]` | Query async, múltiples filas |
| `execute_custom_one()` | `query: str`, `params: dict \| None = None` | `Coroutine[RowOrNone]` | Query async, 1 fila |
| `close()` | - | `Coroutine[None]` | Cerrar pool y conexiones |

**Ejemplo:**

```python
import asyncio
from util_bbdd import AsyncDatabaseManager

async def main():
    manager = AsyncDatabaseManager(
        db_type="postgresql",
        conn_params={...},
        pool_size=20
    )

    await manager.init()  # ← REQUERIDO

    # Queries concurrentes en paralelo
    results = await asyncio.gather(
        manager.get_tables(),
        manager.execute_custom_many("SELECT * FROM users"),
        manager.execute_custom_many("SELECT COUNT(*) FROM orders"),
    )

    await manager.close()

asyncio.run(main())
```

---

## Bulk Operations

### BulkCrud — Operaciones Masivas

**Ubicación:** `src/util_bbdd/bulk/crud.py`

Realiza inserciones, actualizaciones y eliminaciones masivas desde DataFrames de pandas con auditoría opcional.

**Factory Function:**

```python
from util_bbdd.bulk import bulk_crud
bulk = bulk_crud(engine, chunk_size=5000, audit_csv_path=None)
```

| Método | Parámetros | Descripción |
|--------|-----------|-------------|
| `bulk_insert_from_df()` | `df: DataFrame`, `tabla_destino: str`, `generar_sql: bool = True`, `path_sql: Path \| None = None` | Insertar lote desde DataFrame con auditoría |
| `bulk_update_from_df()` | `df: DataFrame`, `tabla_destino: str`, `generar_sql: bool = True`, `path_sql: Path \| None = None` | Actualizar lote según PK |
| `bulk_delete_from_df()` | `df: DataFrame`, `tabla_destino: str` | Eliminar lote según IDs |

**Ejemplo:**

```python
import pandas as pd
from util_bbdd import SyncDatabaseManager
from util_bbdd.bulk import bulk_crud
from pathlib import Path

manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={"host": "localhost", "user": "postgres", ...}
)

# Crear instancia de bulk operations (factory)
bulk = bulk_crud(
    engine=manager.engine,
    chunk_size=5000,
    audit_csv_path=Path("audit.csv")  # Opcional
)

# Cargar datos
df = pd.read_csv("users.csv")

# Insertar masivamente
bulk.bulk_insert_from_df(
    df=df,
    tabla_destino="users",
    generar_sql=True,
    path_sql=Path("insert_queries.sql")
)

print("✅ Insertados:", len(df), "registros")
```

---

### AuditManager

**Ubicación:** `src/util_bbdd/bulk/audit_manager.py`

Registrar cambios (auditoría) de operaciones masivas.

| Método | Parámetros | Retorna | Descripción |
|--------|-----------|---------|-------------|
| `__init__()` | `output_path: str`, `include_old_values: bool = False` | - | Inicializar auditoría |
| `log_insert()` | `table: str`, `record: dict`, `timestamp: datetime` | - | Registrar inserción |
| `log_update()` | `table: str`, `old: dict`, `new: dict`, `timestamp: datetime` | - | Registrar actualización |
| `log_delete()` | `table: str`, `record: dict`, `timestamp: datetime` | - | Registrar eliminación |
| `export_to_csv()` | `filepath: str` | - | Exportar auditoría a CSV |

---

## Analysis & Graphs

### GraphvizRelationshipGraphExt

**Ubicación:** `src/util_bbdd/analysis/graphviz_ext.py`

Generar grafos visuales de relaciones entre tablas.

| Método | Parámetros | Retorna | Descripción |
|--------|-----------|---------|-------------|
| `__init__()` | `manager: SyncDatabaseManager`, `title: str`, `max_depth: int = 2`, `hide_column_types: bool = False` | - | Inicializar generador de grafos |
| `render()` | `filename: str`, `format: str = "svg"` | `str` | Renderizar y guardar grafo (svg, png, pdf, etc.) |

**Formatos soportados:**
- `"svg"` — Vector escalable (recomendado para web)
- `"png"` — Raster (para documentos Word/PDF)
- `"pdf"` — Vector comprimido
- `"plain"` — Texto ASCII

**Ejemplo:**

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.analysis import GraphvizRelationshipGraphExt

manager = SyncDatabaseManager(...)

graph = GraphvizRelationshipGraphExt(
    manager=manager,
    title="E-Commerce Database",
    max_depth=2,
    hide_column_types=True
)

# Exportar a SVG
graph.render("schema_diagram", format="svg")
# Exportar a PNG
graph.render("schema_diagram", format="png")
```

---

## Schema Comparison

### SchemaComparator

**Ubicación:** `src/util_bbdd/comparar/comparator.py`

Comparar esquemas entre dos BDs y detectar cambios.

| Método | Parámetros | Retorna | Descripción |
|--------|-----------|---------|-------------|
| `compare()` | `source: Inspector`, `target: Inspector`, `include_tables: bool = True`, `include_indices: bool = True` | `SchemaDiff` | Comparar dos esquemas |

**Retorna objeto `SchemaDiff`:**
- `source_label: str` — Etiqueta del esquema origen
- `target_label: str` — Etiqueta del esquema destino
- `summary: str` — Resumen de cambios
- `table_diffs: list[TableDiff]` — Diferencias por tabla

**Ejemplo:**

```python
from sqlalchemy import create_engine, inspect
from util_bbdd.comparar import SchemaComparator

# Crear engines
source_engine = create_engine("sqlite:///old_db.db")
target_engine = create_engine("sqlite:///new_db.db")

# Inspectors
source_inspector = inspect(source_engine)
target_inspector = inspect(target_engine)

# Comparar
comparator = SchemaComparator()
diff = comparator.compare(source_inspector, target_inspector)

# Analizar diferencias
for table_diff in diff.table_diffs:
    if table_diff.status != "unmodified":
        print(f"Tabla '{table_diff.table_name}': {table_diff.status}")
        for col_diff in table_diff.column_diffs:
            print(f"  - {col_diff.column_name}: {col_diff.attribute}")
```

---

## Exceptions

### Jerarquía de Excepciones

```
DatabaseException (base)
├── ConnectionError
├── QueryTimeoutError
├── ValidationError
├── PoolExhaustedError
├── SchemaNotFoundError
└── TableNotFoundError
```

**Ubicación:** `src/util_bbdd/_core/exceptions.py`

### Uso Recomendado

```python
from util_bbdd._core.exceptions import (
    DatabaseException,
    ConnectionError as DbConnectionError,
    QueryTimeoutError,
    ValidationError,
    PoolExhaustedError,
)

try:
    manager = SyncDatabaseManager(...)
    result = manager.execute_custom_many("SELECT...")
except DbConnectionError as e:
    print(f"Error de conexión: {e}")
except QueryTimeoutError as e:
    print(f"Query timeout: {e}")
except ValidationError as e:
    print(f"Errorer de validación: {e}")
except DatabaseException as e:
    print(f"Error general de BD: {e}")
```

---

## Type Hints

### Tipos Comunes

```python
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import Connection

# Alias de tipos en util_bbdd
Rows = List[Tuple[Any, ...]]  # Múltiples filas como tuplas
RowOrNone = Optional[Tuple[Any, ...]]  # Una fila o None
```

### Ejemplo de Type Hints

```python
from typing import List, Dict, Any
from util_bbdd import SyncDatabaseManager
from util_bbdd.results import Rows, RowOrNone

def get_active_users(manager: SyncDatabaseManager) -> Rows:
    """Retorna lista de tuplas."""
    return manager.execute_custom_many(
        "SELECT * FROM users WHERE active = 1"
    )

def find_user_by_id(manager: SyncDatabaseManager, user_id: int) -> RowOrNone:
    """Retorna tupla o None."""
    return manager.execute_custom_one(
        "SELECT * FROM users WHERE id = :id",
        {"id": user_id}
    )

def insert_users_bulk(
    manager: SyncDatabaseManager,
    users: List[Dict[str, Any]]
) -> None:
    """Inserta usuarios en lote desde lista de diccionarios."""
    import pandas as pd
    from util_bbdd.bulk import bulk_crud
    from pathlib import Path

    df = pd.DataFrame(users)
    bulk = bulk_crud(engine=manager.engine, chunk_size=5000)
    bulk.bulk_insert_from_df(
        df=df,
        tabla_destino="users",
        generar_sql=True,
        path_sql=Path("insert_users.sql")
    )
```

---

## Motores Soportados

| Motor | Sync | Async | Estado |
|-------|------|-------|--------|
| SQLite | ✅ | ✅ | Soporte completo |
| PostgreSQL | ✅ | ✅ | Soporte completo |
| MySQL/MariaDB | ✅ | ✅ | Soporte completo |
| Oracle | ✅ | ✅ | Soporte completo |
| SQL Server | ✅ | ✅ | Soporte completo |
| HSQLDB | ✅ | ❌ | Solo sync |

---

## Recursos Adicionales

- [Ejemplos de Código](examples/) — Casos de uso completos
- [Guía de Async](ASYNC_GUIDE.md) — Programación asincrónica detallada
- [Manejo de Excepciones](examples/exception_handling.py) — Patrones de error handling
- [Bulk Operations](examples/bulk_insert_csv.py) — CRUD masivo desde CSV
- [Schema Comparison](examples/schema_comparison.py) — Detectar cambios entre BDs

---

## Búsqueda Rápida por Tarea

### Quiero obtener metadatos

```python
manager.get_tables()
manager.get_columns(table_name)
manager.get_table_primary_keys(table_name)
manager.get_table_foreign_keys(table_name)
```

### Quiero ejecutar una query

```python
# Una fila
row = manager.execute_custom_one("SELECT ...", params)

# Múltiples filas
rows = manager.execute_custom_many("SELECT ...", params)
```

### Quiero insertar múltiples registros

```python
import pandas as pd
from util_bbdd.bulk import bulk_crud
from pathlib import Path

df = pd.DataFrame(records)
bulk = bulk_crud(engine=manager.engine, chunk_size=5000)
bulk.bulk_insert_from_df(
    df=df,
    tabla_destino="users",
    generar_sql=True,
    path_sql=Path("insert.sql")
)
```

### Quiero ejecutar queries en paralelo (async)

```python
import asyncio

async def main():
    manager = AsyncDatabaseManager(...)
    await manager.init()

    results = await asyncio.gather(
        manager.execute_custom_many("SELECT..."),
        manager.execute_custom_many("SELECT..."),
    )

    await manager.close()

asyncio.run(main())
```

### Quiero comparar esquemas

```python
from sqlalchemy import inspect
from util_bbdd.comparar import SchemaComparator

diff = SchemaComparator().compare(
    inspect(source_engine),
    inspect(target_engine)
)

for table_diff in diff.table_diffs:
    print(f"{table_diff.table_name}: {table_diff.status}")
```

### Quiero generar un grafo de relaciones

```python
from util_bbdd.analysis import GraphvizRelationshipGraphExt

graph = GraphvizRelationshipGraphExt(manager, title="My DB")
graph.render("schema_graph", format="svg")
```

---

## Metadata Type Introspection (Phase 4)

**v0.8.0+ Feature:** Advanced introspection for user-defined types and JSON schemas across all supported databases.

### Overview

Phase 4 enables programmatic discovery and parsing of:
- **Oracle:** OBJECT types (user-defined composite types)
- **SQL Server:** User-Defined Types (UDTs) with structured members
- **MariaDB:** JSON column schema inference
- **SQLite:** JSON column schema inference
- **Redshift:** JSON column schema inference

### Oracle: Object Type Introspection

**Module:** `util_bbdd.metadata.oracle.types_advanced`

**Main Functions:**

| Function | Args | Returns | Description |
|----------|------|---------|-------------|
| `parse_object_type_structure(type_name, adapter)` | `type_name: str`, `adapter: OracleSyncAdapter \| OracleAsyncAdapter` | `ObjectTypeInfo \| None` | Parse Oracle OBJECT type into structured metadata |
| `get_object_type_fields(type_name, adapter)` | `type_name: str`, `adapter: OracleSyncAdapter \| OracleAsyncAdapter` | `list[ObjectTypeField] \| None` | List fields of an OBJECT type |

**Data Classes:**

- `ObjectTypeField`: Field name, type, ordinal, nullable flag, precision/scale
- `ObjectTypeInfo`: Type name, owner (schema), list of fields

**Example:**

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.oracle.types_advanced import parse_object_type_structure

manager = SyncDatabaseManager(
    db_type="oracle",
    conn_params={"dsn": "ORCL", "user": "scott", "password": "tiger"}
)

# Parse OBJECT type
type_info = parse_object_type_structure("CUSTOMER_TYPE", adapter=manager.adapter)

if type_info:
    print(f"Type: {type_info.type_name} (Owner: {type_info.owner})")
    for field in type_info.fields:
        print(f"  {field.name}: {field.type_name} (nullable={field.is_nullable})")

manager.close()
```

---

### SQL Server: User-Defined Type Introspection

**Module:** `util_bbdd.metadata.sqlserver.types_advanced`

**Main Functions:**

| Function | Args | Returns | Description |
|----------|------|---------|-------------|
| `parse_udt_structure(type_name, adapter)` | `type_name: str`, `adapter: SQLServerSyncAdapter \| SQLServerAsyncAdapter` | `UDTTypeInfo \| None` | Parse SQL Server UDT into structured metadata |
| `get_udt_members(type_name, adapter)` | `type_name: str`, `adapter: SQLServerSyncAdapter \| SQLServerAsyncAdapter` | `list[UDTMember] \| None` | List members of a UDT |

**Data Classes:**

- `UDTMember`: Member name, type, ordinal, nullable, max_length, precision/scale
- `UDTTypeInfo`: Type name, schema, kind (STRUCTURED/HIERARCHY/NATIVE), members list

**Example:**

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.sqlserver.types_advanced import parse_udt_structure

manager = SyncDatabaseManager(
    db_type="sqlserver",
    conn_params={"server": "localhost", "database": "mydb", "user": "sa", "password": "pwd"}
)

# Parse UDT
udt_info = parse_udt_structure("PersonType", adapter=manager.adapter)

if udt_info:
    print(f"UDT: {udt_info.type_name} (Schema: {udt_info.schema}, Kind: {udt_info.kind})")
    for member in udt_info.members:
        print(f"  {member.name}: {member.type_name} (nullable={member.is_nullable})")

manager.close()
```

---

### MariaDB/SQLite/Redshift: JSON Schema Introspection

**Modules:**
- `util_bbdd.metadata.mariadb.types_advanced`
- `util_bbdd.metadata.sqlite.types_advanced`
- `util_bbdd.metadata.redshift.types_advanced`

**Main Functions:**

| Function | Args | Returns | Description |
|----------|------|---------|-------------|
| `query_json_column_schema(schema, table, column, adapter, sample_size)` | Schema, table, column, adapter, sample rows | `dict \| None` | Infer JSON schema from column sampling |

**Returns Schema Dict:**

```python
{
    "type": "object",  # "object", "array", "string", "mixed"
    "properties": {
        "user_id": {"type": "integer"},
        "name": {"type": "string"},
        "tags": {"type": "array"}
    },
    "required": ["user_id", "name"]
}
```

**Example (MariaDB):**

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.mariadb.types_advanced import query_json_column_schema

manager = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={"host": "localhost", "user": "root", "password": "pwd", "database": "mydb"}
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
    print(f"JSON Schema for events.payload:")
    print(f"  Type: {schema['type']}")
    print(f"  Properties: {list(schema['properties'].keys())}")
    print(f"  Required: {schema['required']}")

manager.close()
```

**Compatibility Matrix (Phase 4):**

| Database | Sync | Async | Module | API |
|----------|------|-------|--------|-----|
| **Oracle 9i+** | ✅ | ✅ | `metadata.oracle.types_advanced` | `parse_object_type_structure()` |
| **SQL Server 2005+** | ✅ | ✅ | `metadata.sqlserver.types_advanced` | `parse_udt_structure()` |
| **MariaDB 10.2+** | ✅ | ✅ | `metadata.mariadb.types_advanced` | `query_json_column_schema()` |
| **SQLite 3.38+** | ✅ | ✅ | `metadata.sqlite.types_advanced` | `query_json_column_schema()` |
| **Redshift (latest)** | ✅ | ✅ | `metadata.redshift.types_advanced` | `query_json_column_schema()` |

---

## Connection Pool Finalization Safety (v0.8.0)

**Issue Fixed:** `PythonFinalizationError` at interpreter shutdown when using connection pools with threading.

**Solution:** Automatic detection of interpreter finalization phase using `sys.is_finalizing()` prevents thread creation during cleanup.

**Impact:** No code changes required — pool automatically handles shutdown safety.

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#pythonfinalizationerror-at-shutdown) for details.
```
