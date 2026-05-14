# Excepciones

Jerarquía unificada de excepciones de `util_bbdd`. Todas heredan de `DatabaseException`.

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
└── DocumentationError
    ├── DocumentationConfigError
    └── DocumentationRenderError
```

!!! tip "Capturar errores genéricamente"
    Para capturar cualquier error de `util_bbdd`, usa `except DatabaseException`.
    Para errores específicos, captura la subclase correspondiente antes.

---

::: util_bbdd._core.exceptions
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"
        - "!^test"
