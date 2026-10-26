# Migración a la API 1.0

## 1. Objetivo

Adaptar el código que usa `util_bbdd` ≤ 0.42 a la superficie pública 1.0. En **1.0.0** los nombres antiguos de la raíz
y `SyncDatabaseManager.close_connection()` ya no existen: `from util_bbdd import QueryNotFoundError` da `ImportError`.
Esta guía dice desde dónde se importa cada nombre. (0.43–0.44 los mantenían con `DeprecationWarning`.)

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
| `util_bbdd.progress` | `ProgressEvent`, `ProgressCallback`, `CancellationToken`, `ProgressReporter` (desde 4.1.0) |
| `util_bbdd.metadata` | `SchemaSnapshot`, `Kind`, contratos `SyncMetadataProvider`/`AsyncMetadataProvider` |
| `util_bbdd.connection` | `build_conn_params`, `ConnectionFactory`, `EngineReadinessAdvisor`, `AdvisoryFinding` |
| `util_bbdd.factory` | `ConnectionFactory`, `PoolFactory` |
| `util_bbdd.async_utils` | `maybe_await` |
| `util_bbdd.analysis` | Grafos de relaciones |
| `util_bbdd.bulk`, `.dump`, `.migrate`, `.comparar`, `.doc` | Tipos auxiliares de cada punto de entrada |

## 3. Pasos

### Paso 1 — Ver qué usa tu código

Busca los imports desde la raíz y compáralos con la tabla del paso 2:

```bash
grep -rnE "from util_bbdd import|util_bbdd\.[A-Z]" --include=*.py .
```

Si migras desde 0.43 o 0.44, otra opción es ejecutar tus tests con esa versión y los avisos como errores
(`python -W error::DeprecationWarning -m pytest`): cada aviso nombra el import nuevo. Con 1.0.0 el fallo es un
`ImportError: cannot import name '…' from 'util_bbdd'`.

### Paso 2 — Cambiar los imports

Antes (0.x):

```python
from util_bbdd import (
    SyncDatabaseManager,
    DatabaseException,
    QueryNotFoundError,
    JsonLinesAuditSink,
    build_conn_params,
)
```

Después (1.0):

```python
from util_bbdd import DatabaseException, SyncDatabaseManager
from util_bbdd.audit import JsonLinesAuditSink
from util_bbdd.connection import build_conn_params
from util_bbdd.exceptions import QueryNotFoundError
```

Tabla completa de nombres que salen de la raíz:

| Nombre | Importar desde |
|---|---|
| `ConnectionError`, `PoolConnectionError`, `PoolTimeoutError`, `DriverError`, `ValidationError`, `InvalidDatabaseType`, `DatabaseOperationError`, `DatabaseConfigurationError` | `util_bbdd.exceptions` |
| `QueryError`, `QueryNotFoundError`, `QueryValidationError`, `QueryParameterError`, `QueryTimeoutError`, `QueryExecutionError` | `util_bbdd.exceptions` |
| `ComparerError`, `SchemaDiffValidationError`, `MetadataIntrospectionError` | `util_bbdd.exceptions` |
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

Las clases son **las mismas** que en 0.x; solo cambia desde dónde se importan. Desde 0.44.0 las trazas y los pickles
muestran `util_bbdd.exceptions.QueryError` en vez de `util_bbdd._core.exceptions.QueryError` (los pickles antiguos se
siguen cargando).

### Paso 3 — Managers

| Antes | Después |
|---|---|
| `sync_manager.close_connection(conn)` (retirado en 1.0.0) | `sync_manager.release_connection(conn)` |
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

- Tu suite pasa con util_bbdd 1.0.0 sin `ImportError` ni `AttributeError` sobre `util_bbdd`.
- `from util_bbdd import *` solo trae los 13 símbolos de la raíz: si usabas `*`, importa explícitamente el resto
  (el fallo aparece como `NameError` en el primer uso, no en el import).

## 5. Errores frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `NameError: name 'QueryError' is not defined` tras `from util_bbdd import *` | `*` ya no trae excepciones | `from util_bbdd.exceptions import QueryError` |
| Un `ImportError` de un driver o de python-docx aparece al acceder a `util_bbdd.DatabaseDocumentation` y no al importar `util_bbdd` | Carga perezosa de los puntos de entrada | Instala la dependencia; el error es el mismo, solo cambia el momento |
| `ImportError: cannot import name 'QueryError' from 'util_bbdd'` | El nombre salió de la raíz en 1.0.0 | Importa desde su submódulo (tabla del paso 2) |
| `AttributeError: 'SyncDatabaseManager' object has no attribute 'close_connection'` | Nombre unificado con el manager async | Usa `release_connection()` |

## 6. Cambios en v2.0.0

Dos excepciones documentadas como "reservadas" desde v1.1.1 se retiran completamente en v2.0.0:

| Excepción | Cambio | Alternativa |
|---|---|---|
| `PoolExhaustedError` | Removida | Usa `PoolTimeoutError` (mismo árbol: `ConnectionError → PoolConnectionError → PoolTimeoutError`) |
| `DiffReportGenerationError` | Removida | Usa `ComparerError` (clase padre de errores del comparador) |

Código para migrar:

```python
# 1.0.x
try:
    comparar.compare(...)
except DiffReportGenerationError as e:
    handle_report_error(e)

# 2.0.0+
try:
    comparar.compare(...)
except ComparerError as e:  # o captura la excepción original del reporter
    handle_report_error(e)
```

## 7. Calendario

| Versión | Estado |
|---|---|
| 0.43.0 | Superficie nueva + alias con `DeprecationWarning` |
| 0.44.0 | Las excepciones se presentan como `util_bbdd.exceptions` (trazas, logs, pickle) |
| 1.0.0 | Alias de la raíz y `SyncDatabaseManager.close_connection()` retirados; API pública estable bajo SemVer |
| 2.0.0 | `PoolExhaustedError` y `DiffReportGenerationError` retiradas (eran reservadas desde 1.1.1) |
