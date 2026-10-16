# Sistema de Queries

`util_bbdd.query` registra y resuelve queries con nombre, `util_bbdd.validators` valida sus parámetros por motor y
`util_bbdd.results` normaliza las filas devueltas. Referencia curada: [Registry y Resolver](query_system.md),
[Ejecución de Consultas](query_execution.md) y [Sistema de Validadores](validators_system.md).

---

## QueryRegistry

::: util_bbdd.query.registry.QueryRegistry
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## QueryResolver

::: util_bbdd.query.resolver.QueryResolver
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## DatabaseQueries

::: util_bbdd.query.queries.DatabaseQueries
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## Validadores

::: util_bbdd.validators.get_type_validator
    options:
      show_source: false
      heading_level: 3

::: util_bbdd.validators.base_validator.QueryParameterValidator
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## ResultNormalizer

::: util_bbdd.results.normalizer.ResultNormalizer
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"
