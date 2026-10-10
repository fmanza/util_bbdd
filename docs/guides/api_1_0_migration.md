# Migración a la API 1.0 (v0.43.0)

## 1. Objetivo

Adaptar el código que usa `util_bbdd` ≤ 0.42 a la superficie pública 1.0. En **0.43.0** todo lo anterior sigue
funcionando y emite `DeprecationWarning`; en **1.0.0** se retiran los alias. Esta guía dice qué cambiar.

## 2. Qué cambia

- La raíz `util_bbdd` exporta solo los **puntos de entrada y sus resultados** (13 símbolos).
- Las excepciones tienen un módulo público propio: **`util_bbdd.exceptions`** (la jerarquía completa).
- El resto de nombres que exportaba la raíz se importan desde su **submódulo público**.
- Los dos managers comparten los nombres del ciclo de vida: `init()` y `release_connection()`.
- `import util_bbdd` ya no carga pandas, openpyxl, python-docx ni jinja2: los puntos de entrada que los usan se cargan
  la primera vez que se accede a ellos (medido en v0.43.0: ~1,1 s → ~0,3 s).

### Raíz `util_bbdd` (1.0)

| Grupo | Símbolos |
|---|---|
| Conexión y consultas | `SyncDatabaseManager`, `AsyncDatabaseManager` |
| Carga masiva | `BulkCrud`, `ParallelBulkLoader` |
| Volcado | `DumpOrchestrator`, `DumpConfig`, `DumpResult` |
| Migración DDL | `MigrationPlanner`, `MigrationPlan` |
| Comparación | `SchemaComparator`, `SchemaDiff` |
| Documentación | `DatabaseDocumentation` |
| Error base | `DatabaseException` |

### Submódulos públicos estables

| Submódulo | Contenido |
|---|---|
| `util_bbdd.exceptions` | Jerarquía completa de excepciones (todas heredan de `DatabaseException`) |
| `util_bbdd.audit` | `AuditEvent`, `AuditSink` y destinos (`JsonLinesAuditSink`, `MemoryAuditSink`, `NullAuditSink`) |
| `util_bbdd.metadata` | `SchemaSnapshot`, `Kind`, contratos `SyncMetadataProvider`/`AsyncMetadataProvider` |
| `util_bbdd.connection` | `build_conn_params`, `ConnectionFactory`, `EngineReadinessAdvisor`, `AdvisoryFinding` |
| `util_bbdd.factory` | `ConnectionFactory`, `PoolFactory` |
| `util_bbdd.async_utils` | `maybe_await` |
| `util_bbdd.analysis` | Grafos de relaciones |
| `util_bbdd.bulk`, `.dump`, `.migrate`, `.comparar`, `.doc` | Tipos auxiliares de cada punto de entrada |

## 3. Pasos

### Paso 1 — Ver qué usa tu código

Ejecuta tus tests con los avisos de obsolescencia como errores; cada fallo dice la ruta nueva:

```bash
python -W error::DeprecationWarning -m pytest
```

El mensaje tiene esta forma:

```text
DeprecationWarning: 'util_bbdd.QueryNotFoundError' está obsoleto y se retirará en util_bbdd 1.0.0;
usa 'from util_bbdd.exceptions import QueryNotFoundError'.
```

### Paso 2 — Cambiar los imports

Antes (≤ 0.42):

```python
from util_bbdd import (
    SyncDatabaseManager,
    DatabaseException,
    QueryNotFoundError,
    JsonLinesAuditSink,
    build_conn_params,
)
```

Después (0.43+):

```python
from util_bbdd import DatabaseException, SyncDatabaseManager
from util_bbdd.audit import JsonLinesAuditSink
from util_bbdd.connection import build_conn_params
from util_bbdd.exceptions import QueryNotFoundError
```

Tabla completa de nombres que salen de la raíz:

| Nombre | Importar desde |
|---|---|
| `ConnectionError`, `PoolConnectionError`, `PoolExhaustedError`, `PoolTimeoutError`, `DriverError`, `ValidationError`, `InvalidDatabaseType`, `DatabaseOperationError`, `DatabaseConfigurationError` | `util_bbdd.exceptions` |
| `QueryError`, `QueryNotFoundError`, `QueryValidationError`, `QueryParameterError`, `QueryTimeoutError`, `QueryExecutionError` | `util_bbdd.exceptions` |
| `ComparerError`, `SchemaDiffValidationError`, `MetadataIntrospectionError`, `DiffReportGenerationError` | `util_bbdd.exceptions` |
| `DumpError`, `DumpConstraintError`, `DumpReportError` | `util_bbdd.exceptions` |
| `AuditError`, `AuditConfigError`, `AuditFileError`, `AuditDataError`, `AuditExportError`, `AuditValidationError` | `util_bbdd.exceptions` |
| `DocumentationError`, `DocumentationConfigError`, `DocumentationRenderError` | `util_bbdd.exceptions` |
| `AuditEvent`, `AuditSink`, `JsonLinesAuditSink`, `MemoryAuditSink`, `NullAuditSink` | `util_bbdd.audit` |
| `SyncMetadataProvider`, `AsyncMetadataProvider` | `util_bbdd.metadata` |
| `build_conn_params`, `EngineReadinessAdvisor`, `AdvisoryFinding` | `util_bbdd.connection` |
| `ConnectionFactory`, `PoolFactory` | `util_bbdd.factory` |
| `maybe_await` | `util_bbdd.async_utils` |
| `TableDumpResult` | `util_bbdd.dump` |
| `MigrationWarning` | `util_bbdd.migrate` |

Las clases son **las mismas**: `except util_bbdd.QueryError` y `except util_bbdd.exceptions.QueryError` capturan lo
mismo, así que puedes migrar los imports fichero a fichero.

### Paso 3 — Managers

| Antes | Después |
|---|---|
| `sync_manager.close_connection(conn)` | `sync_manager.release_connection(conn)` |
| — | `sync_manager.init()` (devuelve el manager; no hace I/O porque el sync conecta en el constructor) |
| `AsyncDatabaseManager.is_db_type_supported` / `validate_db_type_static` no existían | ahora existen, igual que en el sync |

Así el mismo código de arranque vale para los dos:

```python
manager = SyncDatabaseManager("sqlite", {"database": ":memory:"}).init()
conn = manager.get_connection()
try:
    ...
finally:
    manager.release_connection(conn)
    manager.close()
```

Diferencia que se mantiene a propósito: en `AsyncDatabaseManager`, `get_query_info()`, `get_available_queries()` y
`get_database_info()` son corrutinas.

## 4. Verificación

- `python -W error::DeprecationWarning -m pytest` pasa sin avisos de `util_bbdd`.
- `from util_bbdd import *` solo trae los 13 símbolos de la raíz: si usabas `*`, importa explícitamente el resto
  (este caso **no** avisa, porque `*` solo mira `__all__`).

## 5. Errores frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `NameError: name 'QueryError' is not defined` tras `from util_bbdd import *` | `*` ya no trae excepciones | `from util_bbdd.exceptions import QueryError` |
| Un `ImportError` de un driver o de python-docx aparece al acceder a `util_bbdd.DatabaseDocumentation` y no al importar `util_bbdd` | Carga perezosa de los puntos de entrada | Instala la dependencia; el error es el mismo, solo cambia el momento |
| `DeprecationWarning` sobre `close_connection()` | Nombre unificado con el manager async | Usa `release_connection()` |

## 6. Calendario

| Versión | Estado |
|---|---|
| 0.43.0 | Superficie nueva + alias con `DeprecationWarning` |
| 0.43–0.x | Los alias se mantienen |
| 1.0.0 | Se retiran los alias de la raíz y `SyncDatabaseManager.close_connection()` |
