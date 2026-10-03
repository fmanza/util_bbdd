# 01 · INVENTARIO — extracción de metadatos en util_bbdd

Sesión `2026-10-03-metadata-centralization` · árbol `develop` @ `c1e5c1f` (v0.30.0) · Explore + Plan Architect

Método: escaneo `ast` de `src/util_bbdd` (`bench/scan_catalog.py`, salida completa en `bench/scan_inventory.json`:
cadenas de código con SQL de catálogo sin contar docstrings, llamadas a `inspect()`/`Inspector.*` e imports de
`metadata`), búsqueda de uso real de cada constructor de SQL (`fetch_*`/`build_*`) y lectura de los caminos de los
managers. Las cifras de coste son del baseline (`02_BASELINE_RENDIMIENTO.md`).

---

## 0. Revalidación del «Punto de partida» del prompt (§2, medido sobre v0.29.0)

| Afirmación del prompt | Estado en v0.30.0 | Evidencia |
|---|---|---|
| `comparar/_routine_fetchers.py` tiene SQL inline (`all_procedures`, `DBMS_METADATA.GET_DDL` por objeto, `sys.procedures`, `sys.sql_modules`, `SHOW CREATE`) | **Ya no**: importa `fetch_standalone_routine_sources_for_schema_sql` (Oracle), `fetch_routines_with_definition_for_schema_sql` (PG, SQL Server) y la plantilla `SHOW CREATE` de `metadata.mariadb.tables` | `comparar/_routine_fetchers.py:31-34`, `:174-176`; commits `a7f2938`, `2ff6a3b`, `1ea0579` |
| `bulk/_support/pk_sync.py`: `pg_get_serial_sequence` inline | Sigue | `bulk/_support/pk_sync.py:154` |
| Recuento `^def fetch_.*_sql`: pg 21, oracle 20, sqlserver 13, mariadb 9, mysql 1; redshift/snowflake/sqlite 0 | Desfasado: hay **174** constructores de SQL en `metadata/` (79 `*_sql`, 43 `*_query`, 43 `fetch_*_sync`, 9 otros) | §2 |
| Registry JSON usado por `metadata/fetcher.py`, `managers/`, `executors/`, `validators/`; HSQLDB sin subpaquete | Se confirma; además es el camino **principal** de los managers para todos los motores salvo MariaDB/MySQL | §1.1 |
| Reflexión SQLAlchemy en `dump/`, `bulk/crud.py`, `comparar/`, `connection/mariadb/update_auto_increment.py` | Se confirma; 34 llamadas, todas fuera de `metadata/` | §1.3 |
| Contrato solo por tabla (`metadata/contracts.py`) | Se confirma | `metadata/contracts.py:16-39` |
| `comparar/_prefetch.py` usa `get_multi_*` | Se confirma y se amplió en v0.30.0 (PK, índices y comentarios de SQL Server por schema) | `comparar/_prefetch.py` |
| Caché por tabla sin lock; managers tocan dicts privados | Se confirma, y se añade un fallo de claves (H-11) | §4 |

---

## 1. Caminos de extracción (cómo se leen hoy los metadatos)

Hay **cuatro mecanismos** de lectura y **tres estilos de parámetros** conviviendo:

| # | Mecanismo | Dónde vive | Quién lo usa | Granularidad | Parámetros |
|---|---|---|---|---|---|
| M1 | Registry JSON (`obtener_tablas`, `columnas_tabla`, `indices`, `claves_*`, `create_*`, `ficheros_fisicos`…) | `data/sql_queries.json` (123 consultas, 7 motores) + `query/registry.py`/`resolver.py` (capa 4) | `managers/` (sync y async) para **todos** los `get_*` en Oracle, PostgreSQL, SQL Server, SQLite, HSQLDB; `validators/` | Por tabla | `str.format` sobre literales (`'{esquema}'`): 95 de 123 consultas; validación por lista blanca `^[A-Za-z0-9_$#]+$` (`validators/base_validator.py:16`) |
| M2 | Constructores de SQL por motor (`fetch_*_sql`, `*_for_schema_sql`, `build_*_query`) | `metadata/<motor>/*.py` | `migrate/extractors`, `comparar/`, `dump/`, `bulk/` (importados por motor), adaptadores MariaDB/MySQL de los managers | Por schema (`*_for_schema_sql`) o por tabla | `:bind` (SQLAlchemy `text`) y `%(schema)s` (pyformat del driver, p. ej. `metadata/postgresql/tables.py` `fetch_columns_for_schema_sql`) |
| M3 | Adaptadores por motor (`SourceAdapterSync`/`RoutineAdapterSync`: `fetch_tables_sync`, `fetch_columns_sync`…) | `metadata/<motor>/sync_adapter.py`, `async_adapter.py`, `_adapter_helpers.py` | **Nadie en `src/`**: 0 llamadas de producción a `fetch_*_sync`/`fetch_*_async`; solo tests (`tests/unit/test_*_adapter_parity.py`, 16-18 ficheros por método) | Por tabla | `:bind` |
| M4 | `Inspector` de SQLAlchemy (`get_columns`, `get_pk_constraint`, `get_foreign_keys`, `get_multi_*`…) | Fuera de `metadata/` | `dump/`, `bulk/crud.py`, `comparar/`, `connection/mariadb/update_auto_increment.py` | Por tabla salvo `get_multi_*` en `comparar/_prefetch.py` | SQLAlchemy |

### 1.1 Managers (`SyncDatabaseManager` / `AsyncDatabaseManager`)

- `get_tables/get_views/get_routines/get_columns/get_indices/get_primary_keys/get_foreign_keys/get_unique_constraints/get_ddl/get_view_ddl/get_routine_ddl/get_routine_parameters`:
  `managers/sync_mgr.py:680-1080`, `managers/async_mgr.py:638-910`. Todos por tabla salvo los listados.
- Estrategia: `managers/_manager_metadata_runtime.py:195-198` — solo `mariadb`/`mysql` usan el adaptador especializado
  (`MariaDBMetadataFetchStrategy`); el resto (`GenericMetadataFetchStrategy`, `:55-69`) **descarta** el adaptador
  (`del specialized_fetcher`) y ejecuta la consulta del JSON.
- Ejecución: `executors/sync_query_executor.py:285-289` (`cursor.execute` del driver nativo: psycopg, oracledb,
  pymssql/pyodbc, mariadb, pymysql). No pasa por SQLAlchemy.
- `metadata/manager.py` (`MetadataManager`, expuesto por `get_metadata_manager()`, `sync_mgr.py:1483-1502`) añade una
  segunda caché sobre la misma `db_cache` con claves fijas (H-11).

### 1.2 SQL de catálogo escrito fuera de `metadata/` (escaneo `ast`)

| ID | Ruta:línea | SQL | Clasificación |
|---|---|---|---|
| S-1 | `bulk/_support/pk_sync.py:154` | `SELECT pg_get_serial_sequence(:tbl, :col)` | **Violación Regla #1** (introspección de secuencia) |
| S-2 | `doc/infrastructure/storage/runtime.py:46` | `SELECT default_tablespace, temporary_tablespace FROM user_users` | **Violación Regla #1** (inventario de almacenamiento Oracle) |
| S-3 | `connection/mariadb/_variables.py:69` | `SHOW VARIABLES LIKE '{…}'` | Configuración de servidor (`EngineReadinessAdvisor`); decidir alcance (§1 del prompt) |
| S-4 | `connection/postgresql/_variables.py:238,249` | `SHOW {param}` | Ídem |
| S-5 | `connection/sqlserver/_variables.py:135,145` | `sys.configurations`, `sys.databases` | Ídem |
| S-6 | `connection/sqlite/_variables.py:161,172` | `PRAGMA {name}` | Ídem (configuración de sesión) |
| S-7 | `connection/sqlite/{connection,pool_connection,async_connection}_sqlite.py` | `PRAGMA foreign_keys = ON` | Configuración de sesión: fuera de alcance |
| S-8 | `comparar/reporters/sql_reporter.py:1088` | `DECLARE … FROM sys.default_constraints` | SQL **emitido** (script de nivelación): fuera de alcance |
| S-9 | `migrate/emitters/sqlserver.py:407` | `EXEC sys.sp_addextendedproperty` | DDL emitido: fuera de alcance |

`data/sql_queries.json` (123 consultas de catálogo) también está fuera de `metadata/` (capa 4) y es la mayor fuente.

### 1.3 Reflexión `Inspector` (34 llamadas, todas fuera de `metadata/`)

| Consumidor | Llamadas | Patrón |
|---|---|---|
| `dump/orchestrator.py:110-111,200,439,676,684,1044,1055,1057,1142` | `get_table_names`, `get_pk_constraint`, `get_columns` ×4 sitios | Por tabla; columnas y PK leídas **3 veces por tabla** en un volcado (baseline) |
| `dump/_constraints.py:250,270,362` | `get_foreign_keys`, `get_unique_constraints`, `get_check_constraints` (Oracle) | Por tabla |
| `dump/_fk_graph.py:58` | `get_foreign_keys` | Por tabla salvo SQL Server (consulta por schema, Q9) |
| `bulk/crud.py:1337` | `inspect(conn).reflect_table` | Por operación de `BulkCrud` (sin FKs desde v0.17.0) |
| `bulk/crud.py:1787-1788,1847-1857` | `get_foreign_keys`, `get_check_constraints`, `get_unique_constraints` | Por tabla (orphan-check, constraints Oracle) |
| `comparar/_prefetch.py:116-143` | fallback por tabla de `get_multi_*` | Por schema donde el dialect lo soporta |
| `comparar/comparator.py:1036` | `get_view_definition` | Por vista |
| `comparar/reporters/sql_reporter.py:507-571` | `get_columns`, `get_pk_constraint`, `get_foreign_keys`, `get_indexes` | Por tabla nueva |
| `connection/mariadb/update_auto_increment.py:90-128` | `inspect`, `get_table_names`, `get_columns` | Por tabla; **capa 4** (no puede importar `metadata/`, capa 5); clase pública `UpdateAutoIncrement` |

### 1.4 Imports de `metadata` desde otros paquetes (42)

- **Detalle por motor importado por consumidores** (acoplamiento a `metadata/<motor>/…`): `bulk/` (7: `delete_strategies.py:46`,
  `parallel_loader.py:39`, `staging_update.py:27`, `_support/dialect.py:9`, `_support/pk_sync.py:22`, `crud.py:53-54`),
  `comparar/` (6: `_prefetch.py:30-31`, `_routine_fetchers.py:31-34`), `dump/` (5: `_constraints.py:19`,
  `_fk_graph.py:16`, `_indexes.py:30,33,36`), `migrate/extractors/` (9), `managers/` (2: `_manager_shared_mixin.py:24`,
  `_metadata_parser.py:286`).
- **API de paquete** (`metadata`, `metadata.cache`, `metadata.adapters`): `managers/` (8), `analysis/contracts.py:13`,
  `doc/application/ports.py:9`, `doc/application/use_cases/documentation_orchestrator.py:12`, `util_bbdd/__init__.py:59`.

Consecuencia: cada consumidor ramifica por motor (`if dialect == "postgresql": … fetch_…_sql()`), justo el anti-patrón
«condicionales por motor repartidos por toda la base de código» de `architecture.instructions.md`.

### 1.5 Consumidores por tabla de la API de managers

| Consumidor | Llamadas | Patrón |
|---|---|---|
| `doc/application/use_cases/documentation_orchestrator.py`, `doc/infrastructure/renderers/{html,word,excel}_generator.py`, `renderers/shared/generator_shared.py`, `doc/infrastructure/adapters/sync_database_manager_adapter.py` | `get_columns`, `get_indices`, `get_primary_keys`, `get_foreign_keys`, `get_unique_constraints`, `get_ddl`, `get_columns_charset_collation`, `get_view_ddl`, `get_routine_ddl`, `get_routine_parameters` | 4–7 consultas por tabla + 1–2 por vista/routine |
| `analysis/base.py:535-538` (`_build_parent_relations_index`) | `get_tables` + `get_foreign_keys` de **todas** las tablas | Para dibujar el grafo de **una** tabla recorre el schema entero, una consulta por tabla |
| `analysis/base.py:361,384,399,476`, `analysis/graphviz_ext.py` | `get_foreign_keys`, `get_columns`, `get_primary_keys`, `get_unique_constraints` | Por tabla alcanzada |
| `migrate/planner.py` → `migrate/extractors/*` | `execute_custom_many` con `*_for_schema_sql` | **Por schema** (9 consultas para 50 tablas en PG): el patrón bueno |

---

## 2. Constructores de SQL en `metadata/` (174) y uso real

| Estilo | Nº | Consumidores reales en `src/` |
|---|---|---|
| `fetch_*_sql` / `*_for_schema_sql` | 79 | `bulk`, `comparar`, `dump`, `migrate`, `metadata` |
| `build_*_query` | 43 | `metadata`, `migrate` (`build_sqlserver_routines_query`) |
| `fetch_*_sync` (módulo) | 43 | solo `metadata` (los adaptadores M3, a su vez sin uso en producción) |
| otros (`build_*_ddl`, `build_public_*`) | 9 | `metadata` |

Sin ningún uso en `src/`: `metadata/snowflake/_adapter_helpers.py` `build_snowflake_databases_query`,
`build_snowflake_indexes_query`.

Tamaño de los subpaquetes por motor (líneas): postgresql 2677, oracle 2454, sqlserver 2151, snowflake 2071,
mariadb 1779, mysql 1613, redshift 1347, sqlite 1218 — **15 310** en total.

**Redshift y Snowflake no son alcanzables**: `SyncDatabaseManager.get_supported_db_types()` devuelve
`['mariadb', 'mysql', 'oracle', 'postgresql', 'hsqldb', 'sqlserver', 'sqlite']`; sus adaptadores se registran pero
ningún `db_type` los resuelve (3418 líneas + tests de paridad).

---

## 3. Matriz motor × objeto (camino que la librería usa hoy)

Leyenda: **J** = registry JSON por tabla · **S** = `metadata/` por schema · **T** = `metadata/` por tabla ·
**I** = `Inspector` · **—** = no se extrae · **n/a** = el motor no lo tiene.

| Objeto | MariaDB | MySQL | Oracle | PostgreSQL | SQL Server | SQLite | HSQLDB | Redshift / Snowflake |
|---|---|---|---|---|---|---|---|---|
| Tablas / vistas | J S | J S | J S | J S | J S | J I | J | T (inalcanzable) |
| Columnas | J S I | J S I | J S I | J S I | J S I | J I | J | T |
| PK / UK | J S I | J S I | J S I | J S T I | J S I | J I | J | T |
| FK | J S I | J S I | J S I | J S I | J S I | J I | J | T |
| CHECK | I | T(M3) I | I (bulk) | T(M3) I | I | I | — | — |
| Índices | J S I | J S I | J S I | J S I | J S I | J I | J | T |
| Routines + parámetros | J S | J S | J S | J S | J S | n/a | J | T |
| Definición routine / vista | J S (`SHOW CREATE` por routine en `comparar`) | ídem | J S | J S | J S | J (vistas) | J (vistas; routines sin DDL) | — |
| Triggers | — | — | — | T(M3) | T(M3) | T(M3) | — | — |
| Secuencias / identidad | T (`bulk`) | T | T (`fetch_identity_generation_sql`) | inline S-1 | T | n/a | — | — |
| Comentarios | J S | J S | J S | J S | J S | — | — | T |
| Charset / collation | J | J | J | J | J | J | J | — |
| Almacenamiento / tablespaces | J | J | J + inline S-2 | J | J | J | J | — |
| Particiones | — | — | — | — | — | n/a | — | — |

Los `?` del prompt quedan resueltos así: **triggers**, **CHECK**, **secuencias** y **particiones** no tienen hoy un
camino de producción completo en ningún motor (solo adaptadores M3 sin uso o `Inspector` puntual). Ningún consumidor
actual los necesita salvo CHECK (`bulk`/`dump` en Oracle) y secuencias (`bulk/pk_sync`, `dump` fase 6a); el diseño
(`03_DISENO.md`) decide si entran en el snapshot.

---

## 4. Duplicados (mismo dato por varios caminos)

| Dato | Caminos | Ejemplo |
|---|---|---|
| Columnas de PostgreSQL | **5**: J `columnas_tabla`, T `fetch_columns_sql`, S `fetch_columns_for_schema_sql`, T `build_columns_safe_sql`, I `get_columns` | `data/sql_queries.json` (postgresql), `metadata/postgresql/tables.py`, `dump/orchestrator.py:684` |
| FK de SQL Server | 4: J `claves_foraneas`, S `fetch_fk_for_schema_sql`, S `fetch_schema_fk_details_sql`/`fetch_schema_fk_references_sql`, I | `metadata/sqlserver/{tables,constraints}.py`, `dump/_fk_graph.py`, `comparar/_prefetch.py` |
| PK/columnas en `dump` | I leído 3 veces por tabla en la misma ejecución | baseline `dump`: 150 `get_pk_constraint` + 150 `get_columns` con 50 tablas |
| Caché de tablas/columnas | `db_cache` con clave `(contexto, tabla)` (managers) y `("default", tabla)` / `"tables"` (`MetadataManager`) | `managers/sync_mgr.py:710-716`, `metadata/manager.py:77-110` |
| Cuatro cachés | `DatabaseMetadataCache`, `RelationshipMetadataCache`, caché propia del `Inspector` por instancia, `TableMetadata` de `comparar/_prefetch.py` | — |

---

## 5. Hallazgos colaterales (fuera del alcance de este refactor; registrar)

| ID | Hallazgo | Evidencia | Severidad |
|---|---|---|---|
| H-10 | `SyncDatabaseManager.get_routine_ddl()` **siempre falla en PostgreSQL**: `create_rutina` del JSON usa `'{esquema}'`, pero `add_context_params` solo añade `esquema` en Oracle/SQL Server (`managers/_metadata_context.py`); `QueryValidationError`. `doc` lo absorbe y documenta routines **sin DDL** sin avisar | Reproducido contra el banco (PG 17, schema `zz_md_50`): `QueryValidationError: Validation failed for query 'create_rutina' on db_type 'postgresql'. Provided params: ['rutina', 'tipo_rutina', 'database']` | Alta (fallo silencioso) → candidato a `/hotfix` independiente |
| H-11 | `MetadataManager` comparte `db_cache` con el manager pero usa claves fijas (`"tables"`, `("default", tabla)`): duplica memoria y `clear_by_context()` no la invalida; con dos contextos devolvería el del primero | `metadata/manager.py:77-110,183` | Media (PLAUSIBLE; no reproducido) |
| H-12 | 95/123 consultas del registry se construyen con `str.format` sobre literales: sin bind parameters (texto SQL distinto por tabla → sin reutilización de plan en Oracle/SQL Server) y rechazo de identificadores legítimos con espacios, guiones o no ASCII | `query/resolver.py:168-191`, `validators/base_validator.py:16` | Media (seguridad mitigada por lista blanca; funcional y rendimiento) |
| H-13 | Tres estilos de parámetros en SQL de catálogo (`{format}`, `:bind`, `%(name)s`): el SQL de `metadata/` se escribe en el `paramstyle` de cada driver porque los managers lo pasan tal cual al driver nativo | §1; `executors/sync_query_executor.py:285-289` | Baja (mantenibilidad) |
| H-14 | `migrate` es cuadrático en CPU: `migrate/views/transpiler.py:92` (`_schema_for_sqlglot`) reconstruye el schema de tipos de sqlglot de **todas** las tablas para **cada** vista. PostgreSQL 500 tablas / 50 vistas: 17,7 de 20,4 s en esa función (150 000 `DataType.build`); catálogo solo 0,16 s | `cProfile` de `MigrationPlanner.plan()` (sesión); baseline `migrate`: 0,4 s (50) → 21,4 s (500) en PG, 0,4 → 19,2 s en SQL Server | Alta para `migrate` (fuera de alcance: no es extracción) → `/refactor` independiente: calcularlo una vez por `transpile_views` |
| H-16 | La consulta de FK por schema de MariaDB/MySQL (`metadata/mariadb/tables.py:147-168`, `KEY_COLUMN_USAGE` ⋈ `REFERENTIAL_CONSTRAINTS` sin schema constante en `rc`) es **cuadrática**: MySQL 162 ms (500 tablas) → 15,7 s (5000); MariaDB 4,5 s (5000). Dos consultas sin join unidas en Python: MySQL 52 ms, MariaDB 183 ms | `bench/micro_mysql_fk.py`; baseline `migrate_extract` MySQL 5000: 15,7 de 17,6 s de catálogo | Alta en `migrate` desde MySQL/MariaDB → mejora rápida independiente (`perf(metadata)`), absorbida después por A4 |
| H-17 | `get_routine_parameters()` **siempre falla en SQL Server**: `parametros_rutina` (sqlserver) usa `INFORMATION_SCHEMA.PARAMETERS.PARAMETER_DEFAULT`, columna que SQL Server no tiene (`Invalid column name 'PARAMETER_DEFAULT'`, error 207). `doc` lo absorbe y documenta routines sin parámetros | Reproducido contra el banco (SQL Server 2022, `zz_util_bbdd_md_50`, función `f0000`) | Alta (fallo silencioso) → candidato a `/hotfix` junto a H-10 |
| H-18 | Oracle con el usuario en minúsculas (`user="bench"`): todos los `get_*` de metadatos de los managers devuelven vacío (el contexto es el usuario tal cual y 11 de 13 consultas Oracle del registry comparan `owner = '{database}'` sin `UPPER`). Encontrado en A2 al revisar el dorado de Oracle (vacío) | Reproducido: `bench` → 0 tablas/vistas/routines/columnas; `BENCH` → 5/1/2/5 | Alta → `/hotfix` (corregido en `managers/_metadata_context.py`) |
| H-19 | HSQLDB: 9 de las 16 consultas del registry fallan con HSQLDB 2.7.4 (`obtener_tablas`, `obtener_vistas`, `columnas_tabla` piden `REMARKS` a vistas que no lo tienen; `indices` usa `INFORMATION_SCHEMA.INDEXES`, que no existe; `create_table`/`create_view`/`temp_tablespaces`/`database_version`/`database_charset_collation` con sintaxis o vistas inexistentes) y `claves_unicas` devuelve vacío con UK presentes: los metadatos de HSQLDB de los managers no funcionan | Probado por JDBC (`jaydebeapi`) contra HSQLDB 2.7.4 en memoria (sesión, A6) | Alta, sin banco → lo resuelve C1 (managers sobre `HSQLDBCatalog`, verificado) |
| H-20 | `get_foreign_keys()` en PostgreSQL y SQL Server devuelve el **producto cartesiano** de columnas en FK compuestas: `claves_foraneas` une `constraint_column_usage` (PG) o `sys.foreign_key_columns` con `KEY_COLUMN_USAGE` (SQL Server) sin emparejar por posición (FK `(a, b)` → 4 filas: a→a, a→b, b→a, b→b). `analysis` dibujaba aristas falsas | Encontrado en C2 por `test_analysis_relations.py` (snapshot vs tabla a tabla, schema `zz_gold_*`) | Media → `analysis` corregido en C2 (lee del snapshot); `get_foreign_keys` lo corrige E2 (`get_*` tipados) |
| H-21 | Oracle: `migrate` tomaba `DATA_LENGTH` (bytes) como longitud de los tipos de texto: `VARCHAR2(30 CHAR)` → `VARCHAR(120)` en el destino, `NVARCHAR2(20)` → 40 | Dorado `oracle_migrate_ir.json` (C3, AL32UTF8) | Media → corregido en C3 |
| H-22 | Oracle: las columnas virtuales se emitían como `DEFAULT <expresión>` (`DOUBLE DEFAULT '"N10"*2'`) | Ídem | Media → corregido en C3 (columna normal, como en el resto de motores) |
| H-23 | Oracle: índices `DESC` y de expresiones con columnas ocultas `SYS_NC…$` en el DDL destino; PostgreSQL y MySQL descartaban los de expresiones sin aviso | Ídem | Media → corregido en C3 (`DESC` por nombre; expresiones con aviso `INDEX_EXPRESSION_SKIPPED`) |
| H-24 | Oracle: los miembros de package salían todos como `PROCEDURE` | Ídem | Baja → corregido en C3 |
| H-25 | SQL Server: las columnas `INCLUDE` de un índice se emitían como sus primeras columnas clave (`(ty, si, bi)` en vez de `(si, bi)`) | Dorado `sqlserver_migrate_ir.json` | Media → corregido en C3 |
| H-26 | PostgreSQL: las columnas `GENERATED … AS IDENTITY` no eran `auto_increment` en el IR (solo `serial`) | Dorado `postgresql_migrate_ir.json` | Media → corregido en C3 |
| H-27 | Snapshot (A1–A3) con datos de tipo incompletos para `migrate`: PostgreSQL sin longitud en `bit(n)` ni en dominios, SQL Server sin longitud en tipos alias, Oracle `base_type` sin `WITH TIME ZONE` | Contraste con el IR de los extractores con SQL propio (C3) | Media → corregido en C3 en los catálogos |
| H-28 | `migrate` pierde información que el IR no modela: precisión de `datetime2(n)`/`time(n)` (SQL Server) y `timestamp(n)` (PostgreSQL), predicado de índices parciales/filtrados, longitud de prefijo de índices MySQL, `ON UPDATE CURRENT_TIMESTAMP`, expresiones de columnas calculadas (se migran como columnas normales) | Dorados `*_migrate_ir.json` (comportamiento conservado en C3) | Baja-media → PENDIENTE (fuera de alcance: requiere ampliar el IR) |
| H-15 | Con la misma configuración de `imprimir`, `doc` pide PK, FK e índices por tabla en PostgreSQL pero no en SQL Server, MySQL ni SQLite (solo columnas) | Huellas de consulta del baseline `doc_html` | PENDIENTE DE VERIFICACIÓN (posible diferencia de contenido entre motores) |
