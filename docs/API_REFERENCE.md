# Referencia Rápida de API

## 1. Requisitos Previos

- `util_bbdd` instalado
- Para operaciones bulk: `pandas` instalado
- Para análisis de grafos: extra `analysis` instalado (`pip install "util-bbdd[analysis]"`)
- Para documentación BD: extra `doc` instalado (`pip install "util-bbdd[doc]"`)

## 2. Índice de Referencia

### Managers (Punto de entrada principal)

| Clase | Módulo | Descripción |
|---|---|---|
| `SyncDatabaseManager` | `util_bbdd` | Manager síncrono multi-motor |
| `AsyncDatabaseManager` | `util_bbdd` | Manager asíncrono multi-motor |

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

| Clase | Módulo | Descripción |
|---|---|---|
| `BulkCrud` | `util_bbdd.bulk` | INSERT/UPDATE/DELETE masivo desde DataFrame |
| `ParallelBulkLoader` | `util_bbdd.bulk` | Carga paralela por particiones de PK |
| `AuditManager` | `util_bbdd.bulk.audit` | Auditoría de operaciones bulk en CSV |

### Schema Comparison

| Clase | Módulo | Descripción |
|---|---|---|
| `SchemaComparator` | `util_bbdd` | Comparación de esquemas → `SchemaDiff` |
| `SchemaDiffReporter` | `util_bbdd` | Generación de reportes en múltiples formatos |

### Migration

| Clase | Módulo | Descripción |
|---|---|---|
| `MigrationPlanner` | `util_bbdd.migrate` | Migración DDL entre motores |

### Dump

| Clase | Módulo | Descripción |
|---|---|---|
| `DumpOrchestrator` | `util_bbdd.dump` | Volcado de datos entre esquemas |
| `DumpConfig` | `util_bbdd.dump` | Configuración del volcado |

### Documentation & Analysis

| Clase | Módulo | Descripción |
|---|---|---|
| `DatabaseDocumentation` | `util_bbdd.doc` | Generación de documentación BD (Word/Excel/HTML) |
| `GraphvizRelationshipGraphExt` | `util_bbdd.analysis` | Grafos de relaciones con Graphviz |

### Exceptions

| Excepción | Cuándo se lanza |
|---|---|
| `DatabaseException` | Base de todas las excepciones de `util_bbdd` |
| `ConnectionError` | Error al conectar al servidor |
| `PoolExhaustedError` | Pool de conexiones agotado |
| `QueryTimeoutError` | Query superó el timeout configurado |
| `QueryNotFoundError` | Query nombrada no registrada |
| `InvalidDatabaseType` | Tipo de motor no reconocido |
| `DriverError` | Driver Python del motor no instalado |

## 3. Verificación

```python
# Verificar que las importaciones principales funcionan
from util_bbdd import (
    SyncDatabaseManager, AsyncDatabaseManager,
    SchemaComparator, SchemaDiffReporter,
)
from util_bbdd.bulk import BulkCrud, ParallelBulkLoader
from util_bbdd.migrate import MigrationPlanner
from util_bbdd.dump import DumpOrchestrator, DumpConfig

print("Todas las importaciones OK")
```

## 4. Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `ImportError: cannot import name 'SchemaComparator'` | `util_bbdd` no instalado o versión antigua | `pip install --upgrade util_bbdd` |
| `ImportError: cannot import name 'GraphvizRelationshipGraphExt'` | Extra `analysis` no instalado | `pip install "util-bbdd[analysis]"` |
| `ImportError: cannot import name 'DatabaseDocumentation'` | Extra `doc` no instalado | `pip install "util-bbdd[doc]"` |
