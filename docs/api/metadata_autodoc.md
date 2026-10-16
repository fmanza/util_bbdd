# Metadatos

`util_bbdd.metadata` lee el catálogo por lotes (ADR-003): `manager.get_schema_metadata()` devuelve un `SchemaSnapshot`
con los tipos de objeto (`Kind`) pedidos. Referencia curada: [Lectura de Metadatos](metadata_manager.md).

---

## SchemaSnapshot

::: util_bbdd.metadata.model.SchemaSnapshot
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## Kind

::: util_bbdd.metadata.model.Kind
    options:
      show_source: false
      heading_level: 3

---

## Tipos del modelo

::: util_bbdd.metadata.model
    options:
      show_source: false
      heading_level: 3
      members:
        - TableMeta
        - ViewMeta
        - ColumnMeta
        - PrimaryKeyMeta
        - UniqueMeta
        - CheckMeta
        - ForeignKeyMeta
        - IndexMeta
        - IdentityMeta
        - RoutineKey
        - RoutineMeta
        - RoutineParameterMeta
        - DatabaseMeta
        - KindNotLoadedError

---

## Contratos

::: util_bbdd.metadata.contracts
    options:
      show_source: false
      heading_level: 3
      members:
        - MetadataSource
        - AsyncMetadataSource
        - SyncMetadataProvider
        - AsyncMetadataProvider
        - CatalogDialect
        - CatalogExecutor
        - AsyncCatalogExecutor
