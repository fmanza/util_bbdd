# Excepciones

Jerarquía unificada de excepciones de `util_bbdd`. Todas heredan de `DatabaseException`.

```
DatabaseException
├── ConnectionError
│   └── PoolExhaustedError
├── QueryError
│   ├── QueryTimeoutError
│   └── QuerySyntaxError
├── ValidationError
├── ConfigurationError
├── DriverNotAvailableError
└── ComparerError
    ├── SchemaDiffValidationError
    ├── MetadataIntrospectionError
    └── DiffReportGenerationError
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
