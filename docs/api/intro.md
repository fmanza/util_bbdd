# Referencia Técnica — Índice de Módulos

Índice de clases públicas, módulos y convenciones de la API de `util_bbdd`.
Para documentación técnica detallada de cada módulo, navega por las subsecciones de este apartado.

## Importaciones canónicas

```python
# Managers (punto de entrada principal)
from util_bbdd import SyncDatabaseManager, AsyncDatabaseManager

# Bulk operations
from util_bbdd.bulk import BulkCrud, ParallelBulkLoader
from util_bbdd.bulk.audit import AuditManager

# Schema comparison
from util_bbdd import SchemaComparator, SchemaDiffReporter

# Migration
from util_bbdd.migrate import MigrationPlanner

# Dump
from util_bbdd.dump import DumpOrchestrator, DumpConfig

# Documentation & analysis
from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.analysis import GraphvizRelationshipGraphExt
```

## Índice de clases públicas

### Managers

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `SyncDatabaseManager` | `util_bbdd` | Manager síncrono multi-motor | [managers-sync](managers-sync.md) |
| `AsyncDatabaseManager` | `util_bbdd` | Manager asíncrono multi-motor | [managers-async](managers-async.md) |

**Métodos comunes** (sync / async equivalente):

| Método | Descripción |
|---|---|
| `get_tables()` | Lista de tablas del esquema |
| `get_columns(tabla)` | Columnas de una tabla |
| `get_primary_keys(tabla)` | Claves primarias |
| `get_foreign_keys(tabla)` | Claves foráneas |
| `get_ddl(tabla)` | DDL de una tabla |
| `execute_custom_many(sql, params?)` | Query libre → múltiples filas |
| `execute_custom_one(sql, params?)` | Query libre → una fila o `None` |
| `get_sqlalchemy_engine()` | Engine SQLAlchemy para operaciones bulk |
| `close()` | Cierra la conexión y libera recursos |

### Bulk Operations

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `BulkCrud` | `util_bbdd.bulk` | INSERT/UPDATE/DELETE masivo desde DataFrame | [bulk-crud](bulk-crud.md) |
| `ParallelBulkLoader` | `util_bbdd.bulk` | Carga paralela por particiones de PK | [bulk-parallel](bulk-parallel.md) |
| `AuditManager` | `util_bbdd.bulk.audit` | Auditoría de operaciones bulk en CSV | [bulk-audit](bulk-audit.md) |

### Schema Comparison

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `SchemaComparator` | `util_bbdd` | Comparación de esquemas → `SchemaDiff` | [schema-comparator](schema-comparator.md) |
| `SchemaDiffReporter` | `util_bbdd` | Generación de reportes en múltiples formatos | [schema-comparator](schema-comparator.md) |

### Migration

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `MigrationPlanner` | `util_bbdd.migrate` | Migración DDL entre motores | [migrate-oracle-mariadb](migrate-oracle-mariadb.md) |

### Dump

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `DumpOrchestrator` | `util_bbdd.dump` | Volcado de datos entre esquemas | [dump](dump.md) |
| `DumpConfig` | `util_bbdd.dump` | Configuración del volcado | [dump](dump.md) |

### Documentation & Analysis

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `DatabaseDocumentation` | `util_bbdd.doc` | Generación de documentación BD | [database-documentation](database-documentation.md) |
| `GraphvizRelationshipGraphExt` | `util_bbdd.analysis` | Grafos de relaciones con Graphviz | [analysis](analysis.md) |

### Excepciones

| Excepción | Cuándo se lanza | Doc técnica |
|---|---|---|
| `DatabaseException` | Base de todas las excepciones de `util_bbdd` | [exceptions](exceptions.md) |
| `ConnectionError` | Error al conectar al servidor | [exceptions](exceptions.md) |
| `PoolExhaustedError` | Pool de conexiones agotado | [exceptions](exceptions.md) |
| `QueryTimeoutError` | Query superó el timeout configurado | [exceptions](exceptions.md) |
| `QueryNotFoundError` | Query nombrada no registrada | [exceptions](exceptions.md) |
| `InvalidDatabaseType` | Tipo de motor no reconocido | [exceptions](exceptions.md) |
| `DriverError` | Driver Python del motor no instalado | [exceptions](exceptions.md) |

## Verificación de importaciones

```python
from util_bbdd import (
    SyncDatabaseManager, AsyncDatabaseManager,
    SchemaComparator, SchemaDiffReporter,
)
from util_bbdd.bulk import BulkCrud, ParallelBulkLoader
from util_bbdd.migrate import MigrationPlanner
from util_bbdd.dump import DumpOrchestrator, DumpConfig

print("Todas las importaciones OK")
```

## Autodoc (mkdocstrings)

Los módulos siguientes tienen documentación generada automáticamente desde los docstrings del código:

- [Managers](managers.md)
- [Comparador de Esquemas](comparator.md)
- [Diff Reporters](reporters.md)
- [Bulk Operations](bulk.md)
- [Excepciones](exceptions.md)
