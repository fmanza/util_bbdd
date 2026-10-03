# TRACEABILITY

## Session metadata
- id: 2026-10-03-metadata-centralization
- fecha: 2026-10-03
- rama: develop
- skill: metadata_centralization_audit_and_refactor (`/metadata-centralization`) — Plan Architect + Performance Auditor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (HF, QW, A0 → commits af0976a, eba1d70, 2afc849; A1; A2 en adelante pendiente)

## Prompt issued

```text
/metadata-centralization

Módulo destino: metadata/ ampliado
Ejes: ambos
Motores: todos
Baseline: no (capturar en PLAN)
Volumen de catálogo: 50 / 500 / 5000 tablas
Banco: sí (docker-compose.bench.yml)
Fases autorizadas: PLAN + AUDIT_PLAN
```

## Context supplied
- `.github/prompts/metadata_centralization_audit_and_refactor.prompt.md` (v2.0), `.github/instructions/architecture.instructions.md`
- `.github/agents/plan-architect.agent.md`, `.github/agents/performance-auditor.agent.md`
- `.ai/architecture.md`, `.ai/runtime.md`, `.ai/CURRENT_STATE.md`; código de `src/util_bbdd/` (solo lectura)
- Banco `util_bbdd_bench_*` (5 contenedores) + SQLite local
- Web (2026-10-03): SQLAlchemy 2.0 reflection/whatsnew, SQLite PRAGMA functions, MySQL 8.4 y MariaDB INFORMATION_SCHEMA, SQL Server INFORMATION_SCHEMA, Oracle ALL_TAB_COLUMNS

## AI output summary
- Revalidado el §2 del prompt (medido sobre v0.29.0) contra v0.30.0: `comparar/_routine_fetchers.py` ya no tiene SQL inline; resto confirmado o ampliado.
- Inventario con escaneo `ast` (`bench/scan_catalog.py`): 4 mecanismos de lectura (registry JSON, constructores `metadata/`, adaptadores sin uso, `Inspector`), 174 constructores de SQL, 34 llamadas a `Inspector` fuera de `metadata/`, 18 ficheros que importan `metadata.<motor>`, 2 violaciones directas de la Regla #1 (S-1, S-2); Redshift/Snowflake inalcanzables.
- Arnés de medición `bench/md_bench.py`: schemas `zz_*` de 50/500/5000 tablas en 6 motores; 110 mediciones de 7 flujos (`results/*.json`).
- Micro-benchmarks: PostgreSQL `information_schema` vs `pg_catalog`; Oracle literales vs binds y `ALL_*` vs `USER_*`; MySQL/MariaDB FK por schema; perfil de `migrate`.
- Hallazgos colaterales reproducidos: H-10 (`get_routine_ddl` PG siempre falla), H-17 (`get_routine_parameters` SQL Server siempre falla), H-16 (FK MySQL/MariaDB cuadrática), H-14 (`migrate` cuadrático en CPU), H-12 (literales → hard parse en Oracle, 6,6×), H-11, H-13, H-15.
- Diseño (`03_DISENO.md`), borrador ADR-003, plan por grupos (`04_PLAN.md`) y AUDIT_PLAN (`05_AUDIT_PLAN.md`): **GO_CONDICIONAL**.
- (PLAN) Sin cambios en `src/`, `tests/`, `docs/` ni configuración.
- Usuario: «IMPLEMENT, acepto recomendación» → D9-1 = retirar Redshift/Snowflake; D9-2 = `get_*` con modelos tipados.
- IMPLEMENT · HF (`/hotfix`): H-10 (`managers/_metadata_context.py`: `esquema` también en PostgreSQL/HSQLDB) y H-17
  (`data/sql_queries.json`: `parametros_rutina` de SQL Server sin `PARAMETER_DEFAULT`). Test unitario
  `tests/unit/test_metadata_request_params_resolve.py` (falla sin el fix en PG/HSQLDB) e integración
  `tests/integration/metadata/test_routine_and_view_ddl_engines.py` (falla sin el fix en PG y SQL Server).
- IMPLEMENT · QW (`perf:`): H-16 (`metadata/mariadb/tables.py` FK en dos consultas + `fetch_fk_rules_for_schema_sql`;
  `migrate/extractors/mariadb.py` las une) — 499 FK idénticas en MySQL y MariaDB; `migrate_extract` 5000 tablas MySQL
  20,6 → 5,1 s, MariaDB 8,2 → 3,7 s. H-14 (`migrate/views/transpiler.py`: esquema sqlglot una vez por plan) — DDL
  idéntico en 4 planes de 500 tablas; `plan()` ≈ 6 s → ≈ 1 s.
- IMPLEMENT · A0: dorados por motor (`tests/integration/metadata/characterization/`, `tests/fixtures/metadata_golden/`;
  deterministas en 3 ejecuciones, Oracle sin `doc` por schema no aislado), guarda G1 con trinquete
  (`tests/unit/test_architecture_metadata_rules.py`), conteo de consultas (`tests/unit/metadata/test_query_counts.py`,
  5 `xfail` estrictos verificados con `--runxfail`: p. ej. `manager_scan` 51 → 501, `dump` 127 → 1207 consultas con
  10 → 100 tablas), F0 `scripts/bench_metadata.py` (+ `tests/unit/test_bench_metadata_script.py`, sección en
  `docs/guides/benchmarks.md`).
- IMPLEMENT · A1: `metadata/model.py` (`Kind`, modelos `*Meta`, `SchemaSnapshot`, `KindNotLoadedError`),
  `metadata/contracts.py` (`CatalogQuery`, `CatalogDialect`, `CatalogExecutor`/`Async…`, `MetadataSource`/`Async…`),
  `metadata/_paramstyle.py` (`:nombre` → `named`/`pyformat`/`format`/`qmark`/`numeric`, listas en `IN`, `::` y
  literales intactos), `metadata/snapshot_cache.py` (LRU por schema, single-flight hilos/asyncio),
  `metadata/catalog_registry.py` (importación perezosa por `db_type`/dialecto SQLAlchemy), `metadata/source.py`
  (`CatalogSource`, `AsyncCatalogSource`, `SqlAlchemyCatalogExecutor`, `FILTER_MAX_TABLES = 50`),
  `metadata/postgresql/catalog.py` (12 consultas `pg_catalog`, comentarios por `pg_description`, identidad por
  `pg_depend`). Tests: 52 unitarios de `tests/unit/metadata/` y `test_snapshot_golden.py` (dorado
  `postgresql_snapshot.json` + contraste con el IR de `migrate`: columnas, nulabilidad, PK, FK con reglas e índices
  coinciden). Medido con `bench_metadata.py --flows snapshot`: PostgreSQL 12 consultas con 50/500/5000 tablas, 5000
  tablas 1,18 s y 26 MB. Diagrama de capas regenerado (`metadata → _core`, 414 ficheros). Desviación del plan: el tipo
  `STORAGE` (almacenamiento/tablespaces) se deja para D1, que es su único consumidor (`doc`).
- IMPLEMENT · hotfix H-18 (encontrado en A2 al ver vacío el dorado de managers de Oracle): contexto Oracle = usuario
  en mayúsculas salvo entre comillas (`managers/_metadata_context.py`); test parametrizado en
  `tests/unit/test_manager_internal_helpers.py`; dorado `oracle.json` regenerado (ahora 5 tablas, 1 vista, 2 routines).
- IMPLEMENT · A2: `metadata/oracle/catalog.py` (12 consultas `ALL_*` por owner con binds; routines sueltas + miembros de
  package; sin CHECK `NOT NULL` generados; Oracle 12c+), registro en `catalog_registry.py`,
  `CatalogDialect.normalize_name()` (Oracle: minúsculas → mayúsculas) aplicado por `CatalogSource` a schema, tablas e
  invalidación. 31 tests unitarios (`test_oracle_catalog.py`); `test_snapshot_golden.py` activo para Oracle (dorado
  `oracle_snapshot.json` + igualdad con el IR; el contraste excluye en ambos lados el índice de la PK, que el IR de Oracle
  incluye y el de PostgreSQL no) y corregido para incluir los parámetros de routines en los dorados de snapshot. Medido:
  12 consultas con 50/500/5000 tablas, 5000 tablas 2,2 s (el primer snapshot paga el *hard parse* de las 12 consultas,
  ≈ 6 s; después se reutiliza el plan). Integración completa: 603 passed.
- IMPLEMENT · A3: `metadata/sqlserver/catalog.py` (12 consultas `sys.*` por schema; `OBJECT_DEFINITION`; comentarios
  `MS_Description`; identidad `by default`; OUTPUT → `INOUT`), registro `mssql`/`sqlserver`. `ViewMeta.definition`
  documentada como «tal como la guarda el motor» (`CREATE VIEW` completo en SQL Server/SQLite). 24 tests unitarios;
  dorado `sqlserver_snapshot.json` = IR de `migrate`. Medido: 12 consultas con 50/500/5000 tablas, 5000 tablas 2,75 s.
- IMPLEMENT · A4: `metadata/mariadb/catalog.py` (`MariaDBCatalog`, `MySQLCatalog`: `information_schema` con
  `TABLE_SCHEMA` constante y sin joins entre vistas; UK desde `STATISTICS`; CHECK con `TABLE_NAME` en MariaDB y
  `TABLE_CONSTRAINTS` aparte en MySQL; índices funcionales con `EXPRESSION` solo en MySQL), `CatalogQuery.extra`
  (consultas adicionales del mismo tipo; `parse` recibe la lista de resultados), `build_create_routine` movido desde
  `migrate/extractors/mariadb.py` (que ahora delega). 33 tests unitarios; dorados `mysql_snapshot.json`,
  `mariadb_snapshot.json` = IR de `migrate`; el test de integración comprueba el nº exacto de consultas declarado por
  el dialecto (MySQL 15, MariaDB 14). Medido: 5000 tablas MySQL 2,38 s, MariaDB 2,60 s. Integración completa: 606.
- IMPLEMENT · A5: `metadata/sqlite/catalog.py` (PRAGMA como funciones tabla unidas a `sqlite_master`; solo `main`;
  sin CHECK/nombres de constraint/expresiones: marcador `<expresión>`); `test_sqlite_catalog.py` con SQLite real en
  memoria; flujo `snapshot` en `test_query_counts.py` (sin `xfail`: constante con 10 y 100 tablas); dorado
  `sqlite_snapshot.json`. Medido: 9 consultas con 50/500/5000 tablas, 5000 tablas 0,86 s.
- IMPLEMENT · A6: `metadata/hsqldb/catalog.py` (INFORMATION_SCHEMA estándar + `SYSTEM_TABLES`/`SYSTEM_COLUMNS`/
  `SYSTEM_INDEXINFO`; sin CHECK `SYS_CT_*` de NOT NULL; firma = `SPECIFIC_NAME`), `DbapiCatalogExecutor` en
  `metadata/source.py`. Verificado contra HSQLDB 2.7.4 descargado de Maven Central al scratchpad (SHA1 comprobado) con
  `jaydebeapi` + JDK 25 (`JAVA_HOME`). Encontrado H-19 (9/16 consultas del registry fallan en HSQLDB). Tests: 19
  unitarios (`test_hsqldb_catalog.py`, incl. `DbapiCatalogExecutor` con `sqlite3` en `qmark` y `named`) e integración
  `tests/integration/metadata/test_hsqldb_catalog.py` (con `UTIL_BBDD_TEST_HSQLDB_JAR`).
- IMPLEMENT · B1: `comparar/_prefetch.py` → `metadata/reflection.py` (`git mv`); columnas de SQL Server por schema
  (`_MSSQL_COLUMNS_SQL` + `_mssql_column_type`, mismas reglas que `MSDialect.get_columns`; `sql_variant` con `CAST`
  porque pymssql lo da en bytes; tipo desconocido → la tabla queda fuera y se lee tabla a tabla). Tests: 2 unitarios
  nuevos con `MSDialect` real (sustituyen al que fijaba «columnas nunca por SQL propio»); paridad de integración con
  tabla de tipos variados exigiendo igualdad completa (`repr` del tipo). `comparar` SQL Server 5000 tablas: 261 →
  8,9 s. Pendiente para C4: definiciones de vistas una a una (1000 de las 1018 consultas restantes). La reflexión de
  `Table` para `bulk`/`dump` se hace en C5/D2. Trinquete: `comparar/_prefetch.py` fuera de las dos listas.
- Usuario: aprueba reordenar (C1 aditivo; consumidores uno a uno; ruptura de `get_*` concentrada en E2).
- IMPLEMENT · C1: `managers/_catalog_executor.py` (`ManagerCatalogExecutor`, `AsyncManagerCatalogExecutor` con
  `asyncpg` vía `fetch` y `$n`, `driver_paramstyle` por módulo del driver), `metadata_source`/`get_schema_metadata()` en
  ambos managers, mixin con caché por instancia, schema por defecto (`main` en SQLite) e invalidación desde
  `clear_cache()`; estilo `dollar` en `_paramstyle`; `_char()` en el catálogo de PostgreSQL (asyncpg da `"char"` como
  bytes: identidad, reglas de FK y prokind salían mal). `ViewMeta.definition` documenta que en PostgreSQL depende del
  `search_path`. Tests: 6 unitarios (SQLite sync/async) + `test_manager_snapshot.py` (manager nativo sync = SQLAlchemy =
  dorado en 6 motores; async en 5, SQL Server async omitido por la cadena ODBC de `aioodbc` en este entorno).
- Verificación: `ruff check`/`format`, `mypy` (408 ficheros), unitarios 6066 passed + 5 xfailed, integración 590 (tras
  HF/QW) y 101 de `tests/integration/metadata` (tras A0), `gen_arquitectura_capas.py` sin cambios, `mkdocs build --strict`.
- IMPLEMENT · C2 (`analysis`): relaciones entrantes y salientes desde `get_schema_metadata(kinds={FOREIGN_KEYS})`
  (índice por tabla del snapshot; sin él, camino tabla a tabla); el adaptador síncrono de `doc` expone
  `get_schema_metadata`. Flujo `analysis` de `test_query_counts.py` sin `xfail`. Nuevo
  `characterization/test_analysis_relations.py` (6 motores): destapa H-20 (FK compuestas en producto cartesiano en el
  SQL heredado de PG y SQL Server), corregido en `analysis` y pendiente en `get_foreign_keys` hasta E2.
- Caracterización previa a C3 (commit propio): `test_migrate_ir_types.py` con un catálogo de tipos amplio por motor y
  dorado `<motor>_migrate_ir.json` = IR (más variantes de tipo completo MySQL/MariaDB) + DDL emitido hacia cada destino,
  generado con los extractores de SQL propio. Destapa H-21…H-26 y H-28.
- IMPLEMENT · C3 (`migrate`): `migrate/extractors/_snapshot.py` (`SnapshotSchemaExtractor`: snapshot → IR; invalida el
  schema en la primera lectura de cada extractor; índices sin el de la PK salvo Oracle y sin los de expresiones, con
  aviso) y un extractor fino por motor que solo traduce `ColumnMeta` a las convenciones de `information_schema` que
  esperan los transformers. Catálogos: PostgreSQL `base_type` estilo `information_schema` y longitudes de `bit` y
  dominios; Oracle `base_type` sin modificadores y packages en ROUTINES; SQL Server longitud de tipos alias; MySQL
  defaults literales entre comillas (`quote_literal_default` se muda a `metadata/`). Dorados: MySQL/MariaDB idénticos;
  PostgreSQL/SQL Server/Oracle con los cambios de H-21…H-26 revisados línea a línea (DDL); `postgresql_snapshot.json`
  re-baselineado (`base_type`). Tests: 4 ficheros de extractores reescritos sobre `_snapshot_source.FakeSource`,
  `test_snapshot_extractors.py` nuevo, 4 `test_routines_*_extractor.py` retirados (su parseo vive en los catálogos y
  sus tests). Banco: `DbapiCatalogExecutor` contado; `migrate_extract` 5000 tablas: PG 9 → 7 consultas y 4,3 → 1,5 s,
  SQL Server 5,9 → 2,3 s, Oracle 7,3 → 2,4 s, MySQL 20,6 → 2,7 s, MariaDB 8,1 → 2,0 s (antes = baseline previo a QW).
  Trinquete: los 5 extractores fuera de `PENDING_ENGINE_IMPORTS`.
- Verificación C3: `ruff`, `mypy` (421), unitarios 6180 + 4 xfailed, integración 629 + 4 skipped, capas sin cambios,
  `mkdocs build --strict`.
- IMPLEMENT · C4 (`comparar`): `metadata/reflection.py` gana `catalog_source(inspector)`, `view_definitions()` (una
  consulta por lado; vista a vista con el `Inspector` si el motor no tiene `CatalogDialect` o falla el lote) y
  `schema_routines()` (Oracle sin packages; error de listado → `MetadataIntrospectionError`). `comparator.py` sin
  `Inspector.get_view_definition` ni fetchers propios; `_routine_fetchers.py` retirado; `_ROUTINE_FETCHERS` queda
  como registro de extensión. H-30 (prefijo del propio schema) corregido con `_unqualify` solo para comparar.
  Decisión: `compare()` sigue recibiendo `Inspector` (la reflexión de tipos SQLAlchemy lo necesita); no se rompe su
  firma. Nuevo `tests/integration/test_comparar_views_routines_engines.py` (5 motores), pasado también contra el código
  previo en un worktree para separar regresión de defecto previo. Trinquete: `comparar/comparator.py` y
  `comparar/_routine_fetchers.py` fuera. `test_query_counts`: `comparar` sigue en xfail por H-29.
- Verificación C4: `ruff`, `mypy` (420), unitarios 6146 + 4 xfailed, integración 634 + 4 skipped, capas (420
  ficheros, pie de figura actualizado), `mkdocs build --strict`. Banco `comparar` 5000: SQL Server 11 016 → 20
  consultas / 261 → 4,8 s; PostgreSQL 1026 → 28; Oracle 1072 → 74 (la primera ejecución de Oracle paga el *hard parse*:
  500 tablas 5,5 s con 1 repetición, 1,2 s de mediana con 3).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST / CONTEXT | `00_REQUEST.md`, `00_CONTEXT_SNAPSHOT.md` | emitido |
| PLAN · inventario | `01_INVENTARIO.md` | emitido |
| PLAN · baseline | `02_BASELINE_RENDIMIENTO.md` | emitido |
| PLAN · diseño | `03_DISENO.md`, `ADR-003-borrador.md` | emitido (ADR PROPUESTO) |
| PLAN · plan incremental | `04_PLAN.md` | emitido |
| AUDIT_PLAN | `05_AUDIT_PLAN.md` | GO_CONDICIONAL |
| Arnés y micro-benchmarks | `bench/md_bench.py`, `bench/scan_catalog.py`, `bench/report_baseline.py`, `bench/micro_*.py` | listos para el «después» |
| Resultados crudos | `bench/results/*.json`, `bench/scan_inventory.json` | 110 mediciones |

## Directrices para Futuras IAs
- **[metadata · caminos]**: los managers leen el catálogo con `data/sql_queries.json` (registry, capa 4) en todos los motores salvo MariaDB/MySQL (`managers/_manager_metadata_runtime.py:195-198`); `metadata/<motor>/*_for_schema_sql` solo lo usan `migrate`, `comparar`, `dump` y `bulk`; los adaptadores `fetch_*_sync`/`_async` de `metadata/<motor>/` no tienen ninguna llamada en `src/`.
- **[metadata · motores]**: `metadata/redshift` y `metadata/snowflake` no son alcanzables: `get_supported_db_types()` no los incluye.
- **[metadata · parámetros]**: el SQL de `metadata/` está escrito en el `paramstyle` del driver nativo (`%(schema)s` en psycopg/pymysql, `:owner` en oracledb) porque los managers lo pasan tal cual a `cursor.execute`; para ejecutarlo con SQLAlchemy `text()` hay que traducirlo (o usar `exec_driver_sql`).
- **[rendimiento · catálogo]**: el coste está en el patrón tabla a tabla, no en el motor: con 500 tablas, 70/121/365 s (PG/SQL Server/Oracle) frente a 0,16/0,22/0,27 s leyendo por schema. En PostgreSQL las vistas de constraints de `information_schema` cuestan ≈ 95 ms por consulta según el catálogo **entero** de la base.
- **[rendimiento · Oracle]**: el SQL con literales fuerza hard parse por tabla (FK 540 ms → 21 ms con binds); `USER_*` no mejora a `ALL_*` filtrado por `OWNER` (medido).
- **[rendimiento · MySQL/MariaDB]**: no unir vistas de `information_schema` entre sí (`KEY_COLUMN_USAGE` ⋈ `REFERENTIAL_CONSTRAINTS` es cuadrático: 15,7 s con 5000 tablas); dos consultas unidas en Python.
- **[rendimiento · SQLAlchemy]**: `get_multi_*` solo agrupa en PostgreSQL y Oracle; en SQL Server `get_multi_columns` va tabla a tabla (224 s en `comparar` con 5000 tablas).
- **[medición]**: para contar consultas de los managers hay que parchear `SyncQueryExecutor._execute_sql_with_optional_params` (driver nativo, no pasa por SQLAlchemy) además de escuchar `before_cursor_execute`; lo hace `bench/md_bench.py`.
- **[metadata · lote]**: el punto canónico de lectura del catálogo es `metadata/source.py` (`CatalogSource`); cada motor
  aporta `metadata/<motor>/catalog.py` (`CatalogDialect`) y se registra en `metadata/catalog_registry.py` (`_BUILTIN`).
  El SQL de catálogo nuevo usa siempre `:nombre`; el ejecutor lo traduce (`_paramstyle.to_driver` con DB-API,
  `expand_lists` con SQLAlchemy).
- **[metadata · Oracle]**: el contexto de metadatos de los managers en Oracle es el usuario de la conexión en mayúsculas
  (H-18); `OracleCatalog.normalize_name` aplica la misma regla. La primera lectura de cada consulta de catálogo cuesta el
  *hard parse* (segundos en el contenedor de Oracle Free); no medir el primer snapshot como coste estable.
- **[metadata · pruebas]**: un motor nuevo se valida con `tests/integration/metadata/characterization/test_snapshot_golden.py`
  (se activa solo al registrar su dialecto): dorado del snapshot + igualdad con el IR de `migrate`.
- **[banco]**: los schemas `zz_md_*` / `zz_util_bbdd_md_*` / usuarios `ZZ_MD_*` siguen creados en el banco para medir el «después»; `md_bench.py teardown` los borra. Oracle necesita `system` (`ORACLE_PASSWORD` del contenedor) para crear usuarios.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- Decisiones del usuario D9-1 (Redshift/Snowflake) y D9-2 (forma pública de `get_*`).
- `/hotfix` de H-10 + H-17 y PRs `perf:` de H-16 + H-14 antes de A0.
- IMPLEMENT por grupos, empezando por A0 → A1, cada uno con aprobación explícita.
