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
│   │   ├── PoolExhaustedError
│   │   └── (otras subclases de pool)
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
│   └── DatabaseConfigurationError
├── ComparerError
│   ├── SchemaDiffValidationError
│   ├── MetadataIntrospectionError
│   └── DiffReportGenerationError
├── DocumentationError
│   ├── DocumentationConfigError
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
    `AuditError` y sus subclases se importan igual que antes (`util_bbdd.bulk`, `util_bbdd.bulk.audit`) y también desde
    `util_bbdd`. Como ahora heredan de `DatabaseException`, un `except DatabaseException` alrededor de operaciones bulk
    captura también los errores de auditoría (solo se lanzan al configurar o leer el CSV y, con `audit_strict=True`, al
    no poder escribirlo).

    Desde la sesión 2026-10-02c los lanza el módulo común [`util_bbdd.audit`](audit.md); la jerarquía y los imports no
    cambian. Con `audit_strict=True`, un fallo de un `audit_sink` llega como `OSError` o `AuditError`; cualquier otra excepción del destino se envuelve en `AuditError`.

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
