# Referencia Técnica — Índice de Módulos

Índice de clases públicas, módulos y convenciones de la API de `util_bbdd`.
Para documentación técnica detallada de cada módulo, navega por las subsecciones de este apartado.

## Importaciones canónicas (API 3.x)

La raíz `util_bbdd` exporta los 13 puntos de entrada y sus resultados; el resto se importa desde su submódulo público.
Ver [Migración a la API 1.0](../guides/api_1_0_migration.md).

```python
# Raíz: puntos de entrada y sus resultados
from util_bbdd import (
    SyncDatabaseManager, AsyncDatabaseManager,
    BulkCrud, ParallelBulkLoader,
    DumpOrchestrator, DumpConfig, DumpResult,
    MigrationPlanner, MigrationPlan,
    SchemaComparator, SchemaDiff,
    DatabaseDocumentation,
    DatabaseException,
)

# Submódulos públicos
from util_bbdd.exceptions import QueryNotFoundError, PoolTimeoutError
from util_bbdd.audit import JsonLinesAuditSink
from util_bbdd.bulk.audit import AuditManager
from util_bbdd.comparar import SchemaDiffReporter
from util_bbdd.connection import build_conn_params
from util_bbdd.analysis import GraphvizRelationshipGraphExt
```

## Índice de clases públicas

### Managers

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `SyncDatabaseManager` | `util_bbdd` | Manager síncrono multi-motor | [managers_sync](managers_sync.md) |
| `AsyncDatabaseManager` | `util_bbdd` | Manager asíncrono multi-motor | [managers_async](managers_async.md) |

**Métodos comunes** (sync / async equivalente):

| Método | Descripción |
|---|---|
| `get_tables()` | Lista de tablas del esquema |
| `get_columns(tabla)` | Columnas de una tabla |
| `get_primary_keys(tabla)` | Claves primarias |
| `get_foreign_keys(tabla)` | Claves foráneas |
| `get_ddl(tabla)` | DDL de una tabla |
| `execute_custom_many(sql, params?)` | Query libre → lista de filas (tuplas) |
| `execute_custom_result(sql, params?)` | Query libre → `CustomQueryResult` con columnas y filas (desde 5.0.0) |
| `execute_custom_one(sql, params?)` | Query libre → una fila (tupla) o `None` |
| `get_schema_metadata()` | Catálogo completo por lotes → `SchemaSnapshot` (ADR-003) |
| `init()` / `get_connection()` / `release_connection(conn)` | Ciclo de vida (mismos nombres en sync y async) |
| `get_sqlalchemy_engine()` | Engine SQLAlchemy para operaciones bulk |
| `close()` | Cierra la conexión y libera recursos |

### Bulk Operations

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `BulkCrud` | `util_bbdd` (también `util_bbdd.bulk`) | INSERT/UPDATE/DELETE masivo desde DataFrame | [bulk_crud](bulk_crud.md) |
| `ParallelBulkLoader` | `util_bbdd` (también `util_bbdd.bulk`) | Carga paralela por particiones de PK | [bulk_parallel](bulk_parallel.md) |
| `AuditManager` | `util_bbdd.bulk.audit` | Auditoría de operaciones bulk en CSV | [bulk_audit](bulk_audit.md) |

### Schema Comparison

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `SchemaComparator` | `util_bbdd` | Comparación de esquemas → `SchemaDiff` | [schema_comparator](schema_comparator.md) |
| `SchemaDiffReporter` | `util_bbdd.comparar` | Generación de reportes en múltiples formatos | [schema_comparator](schema_comparator.md) |

### Migration

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `MigrationPlanner` | `util_bbdd` (también `util_bbdd.migrate`) | Migración DDL entre motores | [migrate_oracle_mariadb](migrate_oracle_mariadb.md) |

### Dump

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `DumpOrchestrator` | `util_bbdd` (también `util_bbdd.dump`) | Volcado de datos entre esquemas | [dump](dump.md) |
| `DumpConfig` | `util_bbdd` (también `util_bbdd.dump`) | Configuración del volcado | [dump](dump.md) |

### Documentation & Analysis

| Clase | Módulo | Descripción | Doc técnica |
|---|---|---|---|
| `DatabaseDocumentation` | `util_bbdd` (también `util_bbdd.doc`) | Generación de documentación BD | [database_documentation](database_documentation.md) |
| `GraphvizRelationshipGraphExt` | `util_bbdd.analysis` | Grafos de relaciones con Graphviz | [analysis](analysis.md) |

### Excepciones

Todas se importan desde `util_bbdd.exceptions`; `DatabaseException` también desde la raíz.

| Excepción | Cuándo se lanza | Doc técnica |
|---|---|---|
| `DatabaseException` | Base de todas las excepciones de `util_bbdd` | [exceptions](exceptions.md) |
| `ConnectionError` | Error al conectar al servidor | [exceptions](exceptions.md) |
| `PoolTimeoutError` | Timeout esperando conexión disponible del pool | [exceptions](exceptions.md) |
| `QueryTimeoutError` | Query superó el timeout configurado | [exceptions](exceptions.md) |
| `QueryNotFoundError` | Query nombrada no registrada | [exceptions](exceptions.md) |
| `InvalidDatabaseType` | Tipo de motor no reconocido | [exceptions](exceptions.md) |
| `DriverError` | Driver Python del motor no instalado | [exceptions](exceptions.md) |

## Verificación de importaciones

```python
import util_bbdd
from util_bbdd import *  # noqa: F403 — solo los 13 símbolos de util_bbdd.__all__
from util_bbdd.comparar import SchemaDiffReporter
from util_bbdd.exceptions import QueryNotFoundError

print(len(util_bbdd.__all__), "símbolos en la raíz")  # → 13 símbolos en la raíz
```

## Autodoc (mkdocstrings)

Los módulos siguientes tienen documentación generada automáticamente desde los docstrings del código:

- [Managers](managers.md)
- [Comparador de Esquemas](comparator.md)
- [Diff Reporters](reporters.md)
- [Bulk Operations](bulk.md)
- [Excepciones](exceptions.md)
