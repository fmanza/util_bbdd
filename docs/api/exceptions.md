# Excepciones

Jerarquía unificada de excepciones de `util_bbdd`. Todas heredan de `DatabaseException`.

Se importan desde el módulo público `util_bbdd.exceptions` (v0.43.0); la raíz `util_bbdd` exporta solo
`DatabaseException`. Ver [Migración a la API 1.0](../guides/api_1_0_migration.md).

```python
from util_bbdd.exceptions import DatabaseException, QueryNotFoundError
```

```
DatabaseException
├── ConnectionError
│   ├── PoolConnectionError
│   └── PoolTimeoutError
├── QueryError
│   ├── QueryTimeoutError
│   ├── QueryExecutionError
│   ├── QueryNotFoundError
│   ├── QueryValidationError
│   └── QueryParameterError
├── MetadataError
│   ├── MetadataFetchError
│   ├── MetadataNormalizationError
│   └── DDLBuildError
├── ValidationError
│   ├── InvalidDatabaseType
│   ├── InvalidConnectionConfig
│   └── InvalidQueryParameters
├── DriverError
│   ├── DriverNotFoundError
│   └── DriverConfigurationError
├── DatabaseOperationError
│   ├── ParallelLoadError           (v3.0.0; .result = ParallelLoadResult)
│   └── IndexRebuildError           (v3.3.0; .results, .duplicates, .recovery_ddl desde 4.0.0)
├── DatabaseConfigurationError
├── ComparerError
│   ├── SchemaDiffValidationError
│   └── MetadataIntrospectionError
├── DocumentationError
│   ├── DocumentationConfigError    (también ValueError)
│   └── DocumentationRenderError
├── DumpError
│   ├── DumpConstraintError
│   └── DumpReportError
└── AuditError                      (desde v0.18.0; antes heredaba de Exception)
    ├── AuditConfigError            (también ValueError)
    ├── AuditFileError
    ├── AuditDataError
    │   └── AuditExportError        (también OSError)
    └── AuditValidationError
```

!!! note "Auditoría de bulk (v0.18.0)"
    `AuditError` y sus subclases se importan de `util_bbdd.exceptions` (también `AuditError` de `util_bbdd.bulk`); desde
    1.0.0 ya no de la raíz `util_bbdd`. Como heredan de `DatabaseException`, un `except DatabaseException` alrededor de operaciones bulk
    captura también los errores de auditoría (solo se lanzan al configurar o leer el CSV y, con `AuditOptions(strict=True)`, al
    no poder escribirlo).

    Desde v0.29.0 los lanza el módulo común [`util_bbdd.audit`](audit.md); la jerarquía y los imports no
    cambian. Con `AuditOptions(strict=True)`, un fallo de un `AuditOptions.sink` llega como `OSError` o `AuditError`; cualquier otra excepción del destino se envuelve en `AuditError`.

!!! note "Carga paralela desde BulkCrud (v3.0.0)"
    `ParallelLoadError` la lanza `BulkCrud.bulk_*_from_df` con `parallel=ParallelOptions(...)` cuando falla alguna
    partición. Las demás particiones **quedan confirmadas**: `exc.result` (un `ParallelLoadResult`) dice cuántas filas
    se cargaron y qué particiones fallaron. `ParallelBulkLoader` no la lanza: devuelve los errores en `partition_errors`.

!!! note "Reconstrucción de índices únicos (v3.3.0)"
    `IndexRebuildError` la lanzan `BulkCrud.maintenance_scope(disable_indexes="all")` y
    `ParallelBulkLoader.load()` con `ParallelOptions(disable_indexes="all")` cuando un índice único o una PK no se
    puede reconstruir al terminar la carga, casi siempre por claves duplicadas. Se lanza después de restaurar todo lo
    demás: `exc.results` tiene un `IndexActionResult` por índice y `exc.duplicates`, hasta 5 claves repetidas por índice
    (vacío en SQL Server dentro de `bulk_session`, donde el propio servidor deshace la transacción al fallar).
    `exc.recovery_ddl` (desde 4.0.0) tiene, por índice (único o no) o FK que se borró para la carga y no se pudo
    recrear (PostgreSQL, MariaDB/MySQL InnoDB e índices únicos sin constraint de Oracle), el DDL para recrearlo a mano.
    Los índices únicos de expresión de PostgreSQL (`lower(email)`) cuentan igual que el resto.

!!! tip "Capturar errores genéricamente"
    Para capturar cualquier error de `util_bbdd`, usa `except DatabaseException`.
    Para errores específicos, captura la subclase correspondiente antes.

---

::: util_bbdd.exceptions
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"
        - "!^test"
