# Gestor de Metadatos (MetadataManager)

`MetadataManager` orquesta el acceso a metadatos de base de datos coordinando fetcher, caché, DDL builder y normalizadores, evitando que los managers gestionen directamente la caché y la normalización.

## 1. Arquitectura y Diseño

```mermaid
flowchart TD
    A[MetadataManager] --> B{¿use_cache?}
    B -->|True| C[DatabaseMetadataCache]
    C -->|Hit| D[Retornar cacheado]
    C -->|Miss| E[MetadataFetcher]
    B -->|False| E
    E --> F[SyncMetadataProvider]
    F --> G[Base de datos]
    G --> F
    F --> E
    E --> C
    C --> H[Retornar resultado]
    D --> H
    A --> I[DDLBuilder]
    I --> J[DDL construido por motor]
```

## 2. Modelo de Datos / Contratos

### API pública

#### Clase `MetadataManager`

| Método | Firma simplificada | Descripción | Retorna |
|---|---|---|---|
| `MetadataManager` | `(metadata_provider, db_cache?, relationship_cache?, db_type?)` | Inicializa con proveedor de metadatos | `MetadataManager` |
| `get_tables` | `(use_cache?)` | Lista de tablas con caché opcional | `Rows` |
| `get_columns` | `(table_name, use_cache?)` | Columnas de una tabla | `Rows` |
| `get_primary_keys` | `(table_name, use_cache?)` | Claves primarias | `Rows` |
| `get_foreign_keys` | `(table_name, use_cache?)` | Claves foráneas | `Rows` |
| `get_indices` | `(table_name, use_cache?)` | Índices | `Rows` |
| `get_tables_normalized` | `(use_cache?)` | Tablas en formato normalizado | `list[NormalizedTableRow]` |
| `get_columns_normalized` | `(table_name, use_cache?)` | Columnas en formato normalizado | `list[NormalizedColumnRow]` |
| `get_ddl` | `(table_name)` | DDL de una tabla | `str` |
| `get_view_ddl` | `(view_name)` | DDL de una vista | `str` |

#### Clase `DatabaseMetadataCache`

| Método | Firma simplificada | Descripción | Retorna |
|---|---|---|---|
| `get_columns` | `(table_key)` | Columnas cacheadas | `list \| None` |
| `set_columns` | `(table_key, columns)` | Guarda columnas en caché | `None` |
| `get_primary_keys` | `(table_key)` | PKs cacheadas | `list \| None` |
| `set_primary_keys` | `(table_key, pks)` | Guarda PKs | `None` |
| `get_foreign_keys` | `(table_key)` | FKs cacheadas | `list \| None` |
| `set_foreign_keys` | `(table_key, fks)` | Guarda FKs | `None` |

### Contrato de entrada

| Parámetro | Tipo | Descripción | Restricciones |
|---|---|---|---|
| `metadata_provider` | `SyncMetadataProvider` | Objeto que implementa `get_tables()`, `get_columns()`, etc. | Normalmente una instancia de `SyncDatabaseManager` |
| `db_cache` | `DatabaseMetadataCache \| None` | Caché a reutilizar entre managers | `None` crea caché vacía nueva |
| `db_type` | `str` | Tipo de motor | Default `"mariadb"`; afecta la construcción DDL |
| `table_key` | `tuple[str, str]` | Clave de tabla para la caché | `(context, nombre_tabla)` |
| `use_cache` | `bool` | Usar caché en la consulta | Default `True` |

### Contrato de salida

- **`Rows`** — `list[tuple[Any, ...]]`; estructura dependiente del motor.
- **`NormalizedTableRow`** / **`NormalizedColumnRow`** — dataclasses con campos homogéneos entre motores.
- Métodos `get_*` de `DatabaseMetadataCache` retornan `None` en cache miss (no lanzan excepción).

### Errores y casos especiales

| Error | Cuándo ocurre |
|---|---|
| Propagado desde `metadata_provider` | Si el proveedor lanza error en BD (conexión caída, permisos) |

Si `db_cache` se comparte entre varios `MetadataManager`, los resultados de uno son visibles al otro en el mismo proceso.

## 3. Componentes y Clases

| Clase | Responsabilidad |
|---|---|
| `MetadataManager` | Coordinación entre fetcher, caché, DDL builder y normalizadores |
| `DatabaseMetadataCache` | 12 cachés independientes para metadatos puros |
| `RelationshipMetadataCache` | 4 cachés adicionales para análisis derivados de relaciones |

## 4. Dependencias y Requisitos

| Dependencia | Propósito | Requerida | Comportamiento sin ella |
|---|---|---|---|
| `SyncMetadataProvider` (protocolo interno) | Proveedor de metadatos desde BD | Sí | Sin proveedor no hay datos que cachear |
| `DDLBuilder` (interno) | Construcción del DDL por motor | Sí | `get_ddl()` no funciona |

## 5. Lectura por lotes: `CatalogSource` (ADR-003)

`MetadataManager` y los `get_*` de los managers leen el catálogo **tabla a tabla**. `CatalogSource` lee cada tipo de
objeto (`Kind`: tablas, vistas, columnas, PK, UK, CHECK, FK, índices, identidad, routines, parámetros, base de datos)
con **una consulta por schema**, guarda el resultado en una `SnapshotCache` y devuelve un `SchemaSnapshot` inmutable.
Es el camino que irán usando managers, `doc`, `analysis`, `migrate`, `dump`, `bulk` y `comparar` (centralización de
metadatos en curso); de momento lo implementan PostgreSQL (`metadata.postgresql.catalog`, solo `pg_catalog`) y Oracle 12c+ (`metadata.oracle.catalog`, `ALL_*` por owner con bind variables) SQL Server 2012+ (`metadata.sqlserver.catalog`, `sys.*`) y MariaDB 10.2+ / MySQL 8.0.16+ (`metadata.mariadb.catalog`, `information_schema` sin joins entre vistas: FK y routines con dos consultas) y SQLite 3.16+ (`metadata.sqlite.catalog`, PRAGMA como funciones tabla; solo el schema `main`, sin CHECK ni nombres de constraint, que los PRAGMA no exponen) y HSQLDB 2.x (`metadata.hsqldb.catalog`, por JDBC con `DbapiCatalogExecutor`; sin dialecto de SQLAlchemy). En Oracle, los nombres sin comillas en minúsculas se buscan en mayúsculas (`snapshot("scott")` lee `SCOTT`).

```python
from sqlalchemy import create_engine
from util_bbdd.metadata import CatalogSource, Kind

source = CatalogSource.from_engine(create_engine("postgresql+psycopg://usr:pwd@host/db"))
snapshot = source.snapshot("ventas", kinds={Kind.TABLES, Kind.COLUMNS, Kind.FOREIGN_KEYS})
for table in snapshot.tables():
    print(table.name, [c.name for c in snapshot.columns(table.name)])
print({fk.ref_table for fk in snapshot.all_foreign_keys()})
source.invalidate("ventas")  # tras cambiar el esquema con DDL propio
```

| Elemento | Descripción |
|---|---|
| `snapshot(schema=None, *, kinds=ALL_KINDS, tables=None)` | Una consulta por tipo no cacheado (dos en algunos tipos de MySQL/MariaDB); `tables=` limita la lectura a unas tablas (hasta 50; por encima, schema completo) |
| `SchemaSnapshot` | `tables()`, `views()`, `routines()`, `columns(t)`, `primary_key(t)`, `uniques(t)`, `checks(t)`, `foreign_keys(t)`, `indexes(t)`, `identity(t)`, `routine_parameters(key)`, `database()`; pedir un `Kind` no cargado lanza `KindNotLoadedError` |
| `SnapshotCache(max_schemas=8)` | Caché LRU por schema, compartible entre fuentes; una sola carga por clave en hilos y en `asyncio` |
| `AsyncCatalogSource` | Misma API con `await snapshot(...)` sobre un `AsyncCatalogExecutor` |
| `SqlAlchemyCatalogExecutor` / `DbapiCatalogExecutor` | Ejecutan el SQL de catálogo sobre un `Engine`/`Connection` de SQLAlchemy o sobre una conexión DB-API (traduce `:nombre` al `paramstyle` del driver) |
| `get_catalog_dialect(nombre)` | `CatalogDialect` por `db_type` o nombre de dialecto de SQLAlchemy |

**Vista de reflexión.** Quien necesita tipos u objetos de SQLAlchemy (hoy `comparar`) usa
`metadata.reflection.prefetch_table_metadata(inspector, schema, tablas, kinds=...)`: `Inspector.get_multi_*` y, en SQL
Server (que no los agrupa), consultas por schema con el mismo resultado que `MSDialect` tabla a tabla, columnas
incluidas.

Referencia medida (banco del proyecto): el snapshot completo cuesta 12 consultas con 50, 500 o 5000 tablas; con 5000
tablas, 1,2 s y 26 MB en PostgreSQL 17, 2,2 s en Oracle 23 Free y 2,8 s en SQL Server 2022 (MySQL 8.4 y MariaDB
11.4: 15 y 14 consultas, 2,4 y 2,6 s). Recorrer 500 tablas tabla a tabla con los managers
cuesta 2503 consultas: 70 s en PostgreSQL, 121 s en SQL Server y 365 s en Oracle.

## 6. Ejemplos Relacionados

- [Ejemplo: Caché de Metadatos](../examples/metadata_cache_usage.md) — Uso de `DatabaseMetadataCache` y patrón get-or-cache
