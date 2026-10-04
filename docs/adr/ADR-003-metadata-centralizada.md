# ADR-003: Extracción de metadatos centralizada y por lotes en `util_bbdd.metadata`

## 1. Contexto y Problema

En v0.30.0 la librería leía el diccionario de datos de los motores por **cuatro caminos** a la vez:

- un registry de 123 consultas en `data/sql_queries.json` (capa 4);
- 174 constructores de SQL repartidos por `metadata/<motor>/`;
- una capa de adaptadores por motor sin ningún uso en producción;
- 34 llamadas a `Inspector` de SQLAlchemy en `bulk`, `dump`, `comparar` y `connection`.

El mismo dato se obtenía de hasta cinco formas (columnas de PostgreSQL), con tres estilos de parámetros y, en el
registry, con `str.format` sobre literales en lugar de bind parameters. El contrato público (`SyncMetadataProvider`)
solo tenía métodos por tabla, y los consumidores importaban SQL de un motor concreto.

Medido contra el banco del proyecto (`docker-compose.bench.yml`): con 500 tablas, recorrer columnas, índices, PK, FK y
UK tabla a tabla costaba 2503 consultas de catálogo y 70 s en PostgreSQL, 121 s en SQL Server y 365 s en Oracle; leer
el mismo schema por tipo de objeto, 0,16 s, 0,22 s y 0,27 s. En Oracle, el SQL con literales forzaba además un *hard
parse* por tabla: con bind variables las mismas consultas bajaban de 749 a 113 ms por tabla.

Fuerzas: el usuario autorizó romper la API pública; la Regla #6 impide a `connection/` y `query/` (capa 4) importar
`metadata/` (capa 5); los consumidores de escritura (`bulk`, `dump`) necesitan objetos y tipos de SQLAlchemy.

## 2. Decisión

1. **`metadata/` es el único lugar con SQL de catálogo y con reflexión `Inspector`.** El SQL de catálogo vive en
   `metadata/<motor>/catalog.py` (`CatalogDialect`), y las consultas puntuales en `metadata/facts.py`,
   `metadata/ddl.py` y `metadata/storage.py`. `data/sql_queries.json` queda sin consultas: `query/` solo sirve las
   consultas con nombre del usuario (`queries_file`).
2. **Lectura por lotes.** `MetadataSource.snapshot(schema, kinds, tables)` (`CatalogSource` / `AsyncCatalogSource`)
   devuelve un `SchemaSnapshot` inmutable de modelos neutros (`TableMeta`, `ColumnMeta`, `ForeignKeyMeta`…). Cada tipo
   de objeto (`Kind`) se lee con **una consulta por schema**, de forma perezosa.
3. **Dos vistas con criterio único.** El catálogo neutro (SQL propio) sirve para leer, documentar y migrar. La
   reflexión de SQLAlchemy (`metadata.reflection`: `get_multi_*` y SQL por schema donde el dialecto va tabla a tabla,
   como SQL Server y MySQL/MariaDB) solo se usa cuando el consumidor necesita tipos u objetos `Table` (`comparar`,
   `dump`, `bulk`).
4. **Un contrato por motor y un estilo de parámetros.** `CatalogDialect` reúne la consulta y el parseo por tipo de
   objeto; todo el SQL usa `:nombre`, traducido al `paramstyle` del driver. Registrar un motor nuevo es añadir su
   `catalog.py` a `catalog_registry`, sin tocar a los consumidores.
5. **Una caché.** `SnapshotCache` por fuente, con clave `(fuente, schema, kind, tablas)`, una sola carga por clave en
   hilos y en `asyncio`, LRU por schema e invalidación explícita tras DDL propio. Los managers la exponen con
   `get_schema_metadata()` y la vacían con `clear_cache()`.
6. **Los `get_*` de los managers devuelven los modelos del snapshot** (decisión D9-2): `get_tables()` →
   `list[TableMeta]`, `get_columns(t)` → `list[ColumnMeta]`, `get_primary_keys(t)` → `PrimaryKeyMeta | None`… iguales
   en todos los motores. Se retiran los adaptadores por motor, el registro global, `MetadataManager`, las cachés
   paralelas (`DatabaseMetadataCache`, `RelationshipMetadataCache`) y los `metadata.redshift` / `metadata.snowflake`,
   que ningún manager soportaba (decisión D9-1).

### Excepciones registradas

| Excepción | Motivo |
|---|---|
| SQL de configuración de servidor o sesión (`connection/*/_variables.py`, `PRAGMA foreign_keys`) | No lee el diccionario de datos |
| SQL emitido (`comparar/reporters/sql_reporter.py`, `migrate/emitters/sqlserver.py`) | Lo ejecuta el destino; no es una lectura |
| DDL de tabla fuera de MySQL/MariaDB (`metadata.ddl.native_table_ddl_sql`) | Una consulta por tabla: el snapshot no guarda la semilla de `IDENTITY`, `CLUSTERED`/`DESC` de la PK ni el criterio de `quote_ident` de PostgreSQL, y `DBMS_METADATA` (Oracle) o el `CREATE` guardado (SQLite) no se reconstruyen |
| Reflexión de SQLAlchemy con SQLite (`comparar`, `dump`) | El dialecto refleja cada tabla con `PRAGMA` y `sqlite_master` por nombre; en proceso, sin red |
| Reflejar cada `Table` que carga `dump` (`BulkCrud`) | Inherente a la carga: una tabla por operación |

Las guardas viven en `tests/unit/test_architecture_metadata_rules.py` (SQL de catálogo, `Inspector` e imports de
`metadata.<motor>` fuera de `metadata/`) y `tests/unit/metadata/test_query_counts.py` (las consultas de catálogo de
cada flujo no crecen con el número de tablas).

## 3. Consecuencias

| Tipo | Descripción |
|---|---|
| Ventaja | Consultas de catálogo O(tipos de objeto) por schema en lugar de O(tablas). HTML de `doc` con 500 tablas: PostgreSQL 2063 → 8 consultas y 57 → 2,1 s; Oracle 2073 → 8 y 368 → 3,2 s. `compare()` con 5000 tablas: SQL Server 11 016 → 20 consultas; MySQL 10 010 → 20 (19,9 → 9,3 s). `dump` de 500 tablas en SQL Server: 44,5 → 18,7 s |
| Ventaja | Un solo sitio por motor y objeto: soportar un motor nuevo es un módulo `catalog.py` |
| Ventaja | Bind parameters en todo el SQL de catálogo: sin `str.format` sobre literales y con reutilización de plan |
| Ventaja | Resultados iguales en todos los motores: las FK compuestas se emparejan por posición (antes, producto cartesiano en PostgreSQL y SQL Server) y la documentación presenta las mismas columnas en todos los motores |
| Compromiso | Ruptura de API: los `get_*` devuelven modelos tipados; desaparecen `MetadataManager`, las cachés de metadatos, los adaptadores por motor, las consultas de catálogo del registry y `UpdateAutoIncrement` en `connection.mariadb` (ahora en `util_bbdd.bulk`). Guía de migración en `CHANGELOG.md` y `docs/api/metadata_manager.md` |
| Compromiso | La primera lectura de un schema enorme trae el schema entero (válvula: `tables=`) y `clear_cache()` con tabla o routine descarta el schema completo |
| Riesgo aceptado | Diferencias de normalización entre los caminos antiguos y el nuevo; caracterizadas por motor en `tests/integration/metadata/characterization/` y re-baselineadas a propósito |
| Deuda técnica | HSQLDB sin contenedor de banco: su `catalog.py` se verificó contra HSQLDB 2.7.4 por JDBC, fuera del banco |

## 4. Alternativas Consideradas

| Alternativa | Pros | Contras | Motivo de rechazo |
|---|---|---|---|
| Paquete nuevo `catalog/` | Empezar limpio | Dos paquetes con la misma responsabilidad; mover caché y contratos igualmente | Sin beneficio frente a ampliar `metadata/` |
| Solo `Inspector` de SQLAlchemy | Mantenido por terceros | Solo agrupa por schema en PostgreSQL y Oracle; no da routines, parámetros, charset ni almacenamiento | Cobertura y rendimiento insuficientes |
| Derivar tipos SQLAlchemy del snapshot neutro | Un solo backend | Reimplementar el parseo de tipos de 7 dialectos | Riesgo alto en `bulk` |
| Mantener el registry JSON y añadir consultas por schema | Cambio menor | Conserva `str.format`, la capa 4 con SQL de catálogo y los caminos duplicados | No resuelve la centralización |

## 5. Estado y Revisión

**Estado:** ACEPTADO e implementado (sesión `2026-10-03-metadata-centralization`, grupos A–G, commits hasta E2c).

Fecha de última revisión: 2026-10-04
