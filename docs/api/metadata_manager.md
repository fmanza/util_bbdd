# Lectura de metadatos

Toda la lectura de metadatos de la librería sale de `metadata/` (ADR-003): cada tipo de objeto (tablas, columnas,
claves, índices, routines…) se lee **con una consulta para todo el schema** y se devuelve en un `SchemaSnapshot`
inmutable de modelos neutros, iguales en todos los motores. Los managers lo exponen con `get_schema_metadata()` y, para
consultas puntuales, con `get_*` que devuelven esos mismos modelos.

## 1. Arquitectura y Diseño

```mermaid
flowchart TD
    A["SyncDatabaseManager / AsyncDatabaseManager"] -->|"get_* (tabla)"| B["get_schema_metadata(kinds)"]
    B --> C{"¿En SnapshotCache?"}
    C -->|Sí| D[SchemaSnapshot cacheado]
    C -->|No| E["CatalogSource: una consulta por Kind"]
    E --> F["CatalogDialect del motor"]
    F --> G[Base de datos]
    E --> C
    D --> H["Modelos neutros: TableMeta, ColumnMeta, ForeignKeyMeta…"]
```

## 2. Modelo de Datos / Contratos

### `get_*` de los managers

Leen el snapshot del schema del contexto (el mismo para todas las tablas) y buscan el objeto sin distinguir mayúsculas.
La primera llamada de cada tipo cuesta una consulta; el resto sale de la caché del manager hasta `clear_cache()`. En
`AsyncDatabaseManager` son corrutinas con la misma firma.

| Método | Retorna |
|---|---|
| `get_tables()` | `list[TableMeta]` (nombre, comentario y, en MySQL/MariaDB, collation) |
| `get_views()` | `list[ViewMeta]` (nombre y definición) |
| `get_routines()` | `list[RoutineMeta]` (en Oracle, también packages y sus miembros `PKG.MIEMBRO`) |
| `get_columns(tabla)` | `list[ColumnMeta]` en orden |
| `get_primary_keys(tabla)` | `PrimaryKeyMeta \| None` |
| `get_foreign_keys(tabla)` | `list[ForeignKeyMeta]` (columnas emparejadas por posición) |
| `get_unique_constraints(tabla)` | `list[UniqueMeta]` |
| `get_indices(tabla)` | `list[IndexMeta]` (incluido el de la PK, con `primary=True`) |
| `get_view_ddl(vista)` | `str`: `CREATE VIEW … AS` + definición (`""` si no existe o no es legible) |
| `get_routine_ddl(rutina, tipo)` | `str`: definición completa (con sobrecargas, la primera) |
| `get_routine_parameters(rutina, tipo)` | `list[RoutineParameterMeta]` (de todas las sobrecargas) |
| `get_database_metadata()` | `DatabaseMeta \| None` (versión, charset, collation) |
| `get_database_version()` | `str` (`"Unknown"` si no se puede leer) |
| `get_database_charset_collation()` | `dict` con `charset`/`collation` cuando el motor los da |
| `get_columns_charset_collation(tabla)` | `list[tuple]`: `(columna, charset, collation)` de las columnas con collation distinta de la de la base (charset solo en MySQL/MariaDB, prefijo de la collation) |
| `get_ddl(tabla)` | `str`: en MySQL/MariaDB, `CREATE TABLE` desde columnas y PK del snapshot; en el resto, el del motor (`DBMS_METADATA` en Oracle, el guardado en SQLite, reconstruido en el catálogo en PostgreSQL, SQL Server y HSQLDB), una consulta por tabla cacheada hasta `clear_cache()` |
| `get_schema_metadata(schema=None, *, kinds=ALL_KINDS, tables=None)` | `SchemaSnapshot` |

```python
from util_bbdd import SyncDatabaseManager

with SyncDatabaseManager("postgresql", conn_params) as manager:
    for table in manager.get_tables():
        columns = manager.get_columns(table.name)  # sin consulta nueva: mismo snapshot
        pk = manager.get_primary_keys(table.name)
        print(table.name, [c.name for c in columns], pk.columns if pk else ())
```

Los modelos están en `util_bbdd.metadata.model` (dataclasses inmutables). Los campos de `ColumnMeta`: `name`,
`ordinal`, `data_type` (tipo completo, `varchar(50)`), `base_type`, `nullable`, `length`, `precision`, `scale`,
`default` (expresión SQL, literales entre comillas en todos los motores), `comment`, `collation`, `identity`,
`generated` y `on_update` (MySQL/MariaDB).

### Errores y casos especiales

| Caso | Comportamiento |
|---|---|
| Tabla, vista o routine inexistente | Lista vacía, `None` o `""` según el método (no lanza) |
| Fallo de conexión o de permisos al leer el catálogo | `MetadataError` (o el error del driver) desde `get_schema_metadata` |
| Snapshot sin un `Kind` pedido | `KindNotLoadedError` (solo si se usa `SchemaSnapshot` a mano con `kinds=` parciales) |

## 3. Componentes y Clases

| Clase | Responsabilidad |
|---|---|
| `CatalogSource` / `AsyncCatalogSource` | Leen el catálogo por tipo de objeto y cachean el snapshot |
| `CatalogDialect` (por motor) | SQL de catálogo y parseo a modelos neutros |
| `SnapshotCache` | Caché LRU de snapshots por schema |
| `SchemaSnapshot` | Vista inmutable del schema, con búsqueda por tabla |
| `metadata.ddl` | DDL: desde los modelos (`view_ddl`, `routine_ddl`, `mysql_table_ddl`) y SQL del DDL nativo de tabla (`native_table_ddl_sql`) |
| `metadata.storage` | SQL del inventario de almacenamiento por motor (`storage_query`, `read_storage_inventory`) |

## 4. Lectura por lotes fuera de un manager: `CatalogSource`

`CatalogSource` lee cada tipo de
objeto (`Kind`: tablas, vistas, columnas, PK, UK, CHECK, FK, índices, identidad, routines, parámetros, base de datos)
con **una consulta por schema**, guarda el resultado en una `SnapshotCache` y devuelve un `SchemaSnapshot` inmutable.
Los managers lo exponen con `get_schema_metadata()` (y `metadata_source`), sobre sus propias conexiones y con su
caché, que `clear_cache()` invalida; lo usan `doc`, `analysis`, `migrate`, `dump`, `bulk` y `comparar`. Lo
implementan PostgreSQL (`metadata.postgresql.catalog`, solo `pg_catalog`) y Oracle 12c+ (`metadata.oracle.catalog`, `ALL_*` por owner con bind variables) SQL Server 2012+ (`metadata.sqlserver.catalog`, `sys.*`) y MariaDB 10.2+ / MySQL 8.0.16+ (`metadata.mariadb.catalog`, `information_schema` sin joins entre vistas: FK y routines con dos consultas) y SQLite 3.16+ (`metadata.sqlite.catalog`, PRAGMA como funciones tabla; solo el schema `main`, sin CHECK ni nombres de constraint, que los PRAGMA no exponen) y HSQLDB 2.x (`metadata.hsqldb.catalog`, por JDBC con `DbapiCatalogExecutor`; sin dialecto de SQLAlchemy). En Oracle, los nombres sin comillas en minúsculas se buscan en mayúsculas (`snapshot("scott")` lee `SCOTT`).

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
11.4: 15 y 14 consultas, 2,4 y 2,6 s). Antes de E2, recorrer 500 tablas con los `get_*` de
los managers costaba 2503 consultas: 70 s en PostgreSQL, 121 s en SQL Server y 365 s en Oracle.

## 5. Migración desde la API anterior (E2 de ADR-003)

| Antes | Ahora |
|---|---|
| `get_tables()` → tuplas por motor (`row[0]`) | `list[TableMeta]` (`table.name`) |
| `get_columns(t)` → tuplas con forma distinta por motor | `list[ColumnMeta]` (`c.name`, `c.data_type`, `c.nullable`…) |
| `get_primary_keys(t)` → `[(columna,), …]` | `PrimaryKeyMeta \| None` (`pk.columns`) |
| `get_foreign_keys(t)` → tuplas (en PostgreSQL y SQL Server, FK compuestas con columnas cruzadas, H-20) | `list[ForeignKeyMeta]` (`fk.columns`, `fk.ref_table`, `fk.ref_columns`) |
| `get_tables_normalized()` / `get_columns_normalized(t)` | `get_tables()` / `get_columns(t)` (ya son homogéneos) |
| `get_metadata_manager()`, `MetadataManager`, `AsyncMetadataManager` | `get_schema_metadata()` o los `get_*` del manager |
| `manager.relationship_cache` / `get_relationship_cache()` | Sin sustituto: `analysis` lee del snapshot |

## 6. Ejemplos Relacionados

- [Ejemplo: Caché de Metadatos](../examples/metadata_cache_usage.md) — Uso de `DatabaseMetadataCache` y patrón get-or-cache
