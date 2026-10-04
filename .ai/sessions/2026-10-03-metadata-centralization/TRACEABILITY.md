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
- Usuario: «H-29 y luego C5».
- IMPLEMENT · H-29: `metadata/mariadb/_show_create.py` reconstruye `SHOW CREATE TABLE` de todo el schema con cinco
  consultas a `information_schema` (reglas de formato medidas en el banco: defaults entrecomillados en MySQL y en forma
  SQL en MariaDB, `CHARACTER SET … COLLATE …` si difiere de la tabla, expresión generada entre paréntesis, FK sin
  `NO ACTION` en MySQL y sin `RESTRICT` en MariaDB); `metadata/reflection.py` lo interpreta con
  `dialect._tabledef_parser` y llama a `get_columns`/`get_pk_constraint`/`get_indexes`/`get_table_comment` del dialecto
  sobre una caché privada sembrada con la clave de `_setup_parser` (el decorador `reflection.cache` pasa `schema` como
  argumento con nombre: `("_setup_parser", (tabla,), (("schema", schema),))`). Las FKs replican `get_foreign_keys` sin
  la consulta de corrección de MySQL 8 (los nombres ya salen de `information_schema`). Paridad completa (`repr` de los
  tipos, `computed`, `dialect_options`, `options`) en `test_comparar_prefetch_engines.py` con una tabla de 27 columnas,
  y ≤ 6 sentencias sin `SHOW CREATE`. Banco `comparar` 5000: MySQL 10 010 → 20 consultas / 19,9 → 9,3 s, MariaDB
  16,3 → 10,4 s (el resto es CPU: parseo y comparación de 2 × 5000 tablas).
- IMPLEMENT · C5 (`bulk`): `metadata/facts.py` (consultas puntuales sobre la `Connection` del llamador, con la
  misma forma de llamada que antes: los mocks de los tests siguen valiendo) y `metadata.reflection.reflect_table()`;
  `maintenance_scope` lee FKs (orphan-check de PostgreSQL) y FK/CHECK/UNIQUE (Oracle) con
  `CatalogSource.from_engine(engine).snapshot(schema, kinds, tables=[tabla])`. Trinquete: los 6 ficheros de `bulk/`
  fuera de las dos listas. Hallazgo H-31 (Oracle nunca desactivaba constraints) corregido: `SessionScope.after_end`
  ejecuta la reactivación tras el rollback de la sesión atómica (el DDL de Oracle confirmaría lo pendiente y en otra
  conexión antes del rollback chocaría con los bloqueos de las filas). Nuevo test de integración Oracle que exige la FK
  desactivada dentro del bloque; `_fk_disabled_count` cubre Oracle.
- Verificación C5: `ruff`, `mypy` (422), unitarios 6171 + 4 xfailed, integración 635 + 10 skipped, capas (422,
  pie actualizado), `mkdocs build --strict`. Banco `bulk` 500: mismas consultas puntuales por operación.
- Usuario: formato de `doc` **unificado neutro** (frente a emular el formato por motor; riesgo R1 aceptado con
  diferencias listadas).
- IMPLEMENT · D1 (`doc`): `doc/application/use_cases/catalog_rows.py` (`CatalogRows`: filas neutras desde el snapshot,
  un tipo de objeto por lectura y una vez por sesión); `DocumentationBootstrap`/`DocumentationSession` sirven a los
  renderers esas filas (sus métodos `get_*` se conservan, sin tocar los bucles de los renderers); los helpers de
  `generator_shared` dejan de recibir el motor (`_COLUMN_SPECS_BY_DB`, `is_unique`, `get_flat_column_indexes` y las
  posiciones de FK/índices por motor fuera); hoja/página plana enriquecida en todos los motores; cabeceras comunes en
  `headers_config.json`. `TableMeta.collation` (MySQL/MariaDB). Dorados `*_doc.txt` re-baselineados y revisados
  (H-32, H-15, H-20 en doc) y `*_snapshot.json` (`collation`). Word/Excel/HTML generados en los 6 motores sin errores y
  con cabeceras alineadas. Guarda de consultas: cuenta también `DbapiCatalogExecutor`; `doc` sin `xfail`. Queda tabla a
  tabla: el DDL de tabla (`get_ddl`, registry) y el inventario de almacenamiento (`storage/runtime.py`) → E2.
- Verificación D1: `ruff`, `mypy` (423), unitarios 6178 + 3 xfailed, integración 635 + 10 skipped, capas (423),
  `mkdocs build --strict`. Banco `doc_html` 500: PostgreSQL 2063 → 8 consultas / 57 → 2,1 s, Oracle 2073 → 8 /
  368 → 3,2 s, SQL Server 583 → 8, MySQL/MariaDB 554 → 10.
- IMPLEMENT · D2 (`dump`): `_fk_graph.referred_tables` sobre `prefetch_table_metadata(kinds=["fks"])` (se retira la
  consulta propia de SQL Server de Q9: la cubre B1); el orquestador precarga una vez por volcado columnas y PK de origen
  y columnas de destino (`_side_meta`; sin precarga, `TableMetadata` consulta tabla a tabla) para columnas comunes, PK
  de rangos y aviso LOB; `ConstraintManager` lee FK/CHECK/UNIQUE del destino con un snapshot (nombres pasados por
  `dialect.normalize_name` para citar igual que antes); `IndexManager` y la definición de FK de PostgreSQL vía
  `metadata.facts` (`secondary_nonunique_indexes`, `foreign_key_definition`); `metadata.reflection.table_names` e
  `inspector_for`. Trinquete: los 4 ficheros de `dump/` fuera. Hallazgo en integración: la precarga de SQL Server (B1)
  descartaba filas de tablas pedidas con otro case → `_as_requested` (coincidencia única). Banco `dump` 500: SQL Server
  con 1 repetición dio 93 s (contenedor en frío; con 3 repeticiones, 18,7 s frente a 44,5 s del baseline).
- Verificación D2: `ruff`, `mypy` (423), unitarios 6179 + 3 xfailed, integración 635 + 10 skipped, capas (423),
  `mkdocs build --strict`. `test_query_counts`: `dump` sigue en `xfail` documentado (reflexión de cada `Table` cargada y
  SQLite con `PRAGMA`).
- IMPLEMENT · E1: `connection/mariadb/update_auto_increment.py` → `bulk/_support/auto_increment.py` (exportado en
  `util_bbdd.bulk`; fuera de `connection.mariadb`), sobre el snapshot (`TABLES` + `COLUMNS`, `identity` y `base_type`
  entero) con la conexión del propio `salida_sql()`. Hallazgo H-33 (tablas `SYSTEM VERSIONED` de MariaDB fuera del
  snapshot) corregido en el catálogo y en `_show_create`. Trinquete: `connection/mariadb/update_auto_increment.py`
  fuera de `PENDING_CATALOG`. Verificación: `ruff`, `mypy` (423), unitarios 6180 + 3 xfailed, integración 635 + 10
  skipped, `mkdocs build --strict`.
- Usuario: E2 en 4 commits (E2a `get_*` tipados; E2b DDL de tabla y almacenamiento a `metadata/`; E2c registry JSON,
  adaptadores y cachés fuera; E2d Redshift/Snowflake fuera).
- IMPLEMENT · E2a: `managers/_catalog_facade.py` (`SyncCatalogFacade`/`AsyncCatalogFacade`, bases de los managers):
  `get_*` → modelos de `metadata.model` desde `get_schema_metadata(kinds={…})`, búsqueda sin mayúsculas, sobrecargas de
  routines con todos sus parámetros; `metadata/ddl.py` (`view_ddl`, `routine_ddl`, `mysql_table_ddl`). Fuera de los
  managers: los 16 `get_*`/`_normalized`/`get_metadata_manager` antiguos, sus fetchers y helpers privados muertos,
  `relationship_cache` (también de `CacheService`/`CacheManager`, `doc` y `analysis`) y `MetadataManager`/
  `AsyncMetadataManager`. `SyncMetadataProvider`/`AsyncMetadataProvider` con los tipos nuevos. `analysis` solo con
  `get_schema_metadata` (`RelationshipGraphSource` reducido; `graphviz_ext` sin cachés propias). `doc`: puertos
  `DocumentationCatalogPort`/`DocumentationBackendPort`; el adaptador ya no delega lecturas por objeto. MariaDB:
  `build_table_ddl_from_metadata` sobre modelos (`ColumnMeta.on_update` nuevo para no perder `ON UPDATE`) y sin los
  `fetch_*` de `SourceAdapter` (leían los `get_*` en tuplas; sin consumidores). Hallazgos: `_get_unique_columns` de
  `graphviz_ext` leía el nombre de la restricción como columna (1:1 nunca detectado); MySQL con pool fallaba en
  `get_schema_metadata` (`_ConnectionFairy` de SQLAlchemy → `driver_paramstyle` lo desenvuelve); la caché local de
  cardinalidad que introduje al principio repetía MDC-02 (sin contexto) → eliminada; cada `get_*` reconstruía el
  índice por tabla del snapshot (O(n²) en bucle) → `CatalogSource._assemble` lo reutiliza. Dorados `<motor>.json`
  re-baselineados a modelos (D9-2; FK compuestas por posición), `*_snapshot.json` (`on_update`) y `mariadb_doc.txt`
  (sin `DEFAULT NULL` redundante). Guarda de consultas: `manager_scan` sin `xfail`. Trinquete:
  `managers/_manager_shared_mixin.py` fuera de `PENDING_ENGINE_IMPORTS`.
- Verificación E2a: `ruff`, `mypy` (423), unitarios 6141 + 2 xfailed, integración 641 + 10 skipped, capas (423, sin
  cambios), `mkdocs build --strict`.

- IMPLEMENT · E2b: `metadata/ddl.py` con el SQL del DDL nativo de tabla (`native_table_ddl_sql`, generado desde
  `data/sql_queries.json` con binds `:schema`/`:table_name`) y `metadata/storage.py` (consultas de inventario,
  `read_storage_inventory`, `storage_query_params`). Fachada: `get_ddl` (MySQL/MariaDB desde el snapshot; resto con el
  ejecutor de catálogo del manager, caché `_table_ddl_cache` que vacía `_invalidate_catalog`),
  `get_columns_charset_collation` (snapshot), `get_storage_inventory`, `get_storage_rows`. Fuera de los managers: los 5
  módulos de estrategias/parseo y la resolución de adaptadores (los managers ya no importan `metadata.<motor>`:
  `PENDING_ENGINE_IMPORTS` vacío). `doc`: `storage/runtime.py` sin SQL (fuera de `PENDING_CATALOG`; queda solo
  `comparar/reporters/sql_reporter.py`, excepción registrada). `ManagerCatalogExecutor` envuelve los errores del driver
  en `MetadataError` y hace rollback. Hallazgos: `:table` no es un bind válido en Oracle (ORA-01745) → `:table_name`;
  ciclo de import `metadata.ddl` → `mariadb.common` → adaptador → `ddl` (resuelto quitando del adaptador los métodos
  muertos). Dorados sin cambios. Inventario comprobado a mano en los 6 motores del banco (Oracle: el usuario del banco
  no ve `DBA_DATA_FILES`; error por sección como antes).
- Verificación E2b: `ruff`, `mypy` (419), unitarios 6124 + 2 xfailed, integración 641 + 10 skipped, capas,
  `mkdocs build --strict`.

- IMPLEMENT · E2d (antes que E2c: Redshift/Snowflake dependían de la infraestructura de adaptadores que E2c retira):
  fuera `metadata/redshift`, `metadata/snowflake` y sus tests (unitarios e integración); README, `mkdocs.yml`,
  `docs/functional/*`, `.ai/architecture.md` y `SHARED_INSTRUCTIONS.md` dejan de listarlos. Verificación: `mypy`
  (395), unitarios 5831 + 2 xfailed, capas (395).

- IMPLEMENT · E2c: alcance de `metadata/` por grafo de imports (raíces: código fuera de `metadata/` + núcleo nuevo +
  `<motor>/catalog.py`) → 66 módulos fuera (adaptadores, registro, `mysql/`, builder, fetcher, normalizer,
  `types_advanced`, routines…); poda por símbolo con uso calificado por módulo (el nombre suelto engaña:
  `fetch_tables_sql` existe en 4 motores) → 70 definiciones fuera. Cachés retiradas (`metadata/cache.py`,
  `CacheService`, `CacheManager`, `CacheKeyFactory`); `clear_cache()` sobre `_invalidate_catalog`. JSON de catálogo
  vacío; `DatabaseQueries` sin conveniencia de catálogo; `doc` muestra el SQL de `Kind.DATABASE`. Tests: triage
  automático (tests de código retirado fuera; imports re-apuntados al submódulo cuando el nombre sigue existiendo);
  los del registry/validadores usan `tests/fixtures/sql_queries_sample.json` (las consultas antiguas como fichero de
  usuario). Integración 551 + 10 skipped (menos tests: los de módulos retirados).

- IMPLEMENT · G2: `comparar/reporters/sql_reporter.py` lee el origen con `metadata.reflection` (prefetch por lotes de
  las tablas nuevas; `TableMetadata` para el resto) → sus `Inspector` fuera; queda solo SQL emitido (excepción).
  `PENDING_CATALOG` y `PENDING_ENGINE_IMPORTS` vacíos. `test_query_counts`: sin `xfail`; `comparar` y `dump` descuentan
  la reflexión de SQLAlchemy de SQLite (`PRAGMA` y `sqlite_master` por tabla, en proceso; excepción de ADR-003) y el
  resto no puede crecer. Medido: todo lo que crecía era esa reflexión.
- IMPLEMENT · H: `docs/adr/ADR-003-metadata-centralizada.md` (ACEPTADO, con excepciones registradas y cifras),
  Reglas #1–#3 y #5 de `architecture.instructions.md` reescritas (catálogo por lotes, sin excepción de `comparar`),
  `SHARED_INSTRUCTIONS.md`, `.ai/architecture.md`, `.ai/product.md`, `.ai/DECISIONS_LOG.md` (sustituye a la decisión de
  2026-05-19), `docs/functional/metadata_extraction.md`, `docs/api/managers_sync*.md`; fuera
  `docs/api/managers_metadata_factory.md` (documentaba un módulo retirado en E2b). CHANGELOG con resumen y guía.

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
- **[managers · metadatos]**: los `get_*` de metadatos viven en `managers/_catalog_facade.py` (fachada sobre
  `get_schema_metadata`); el manager solo aporta la fuente. `CatalogSource._assemble` reutiliza el `SchemaSnapshot`
  mientras la caché devuelva los mismos datos: sin ello, `get_columns(t)` en bucle reconstruía el índice por tabla en
  cada llamada (O(n²); 5000 tablas → 0,08 s con la reutilización). Para recorrer el schema, mejor un
  `get_schema_metadata(kinds=…)` y el snapshot.
- **[tests · fakes]**: `tests/unit/_catalog_fakes.py` (`FakeCatalogManager`, `build_catalog`) da un manager con
  snapshot en memoria; `tests/unit` no es paquete: se importa como `from _catalog_fakes import …`.
- **[herramientas · heredocs]**: en Bash, `\b`, `\n` y `\|` dentro de heredocs con Python se degradan (un `\b` acabó
  como carácter de retroceso en una regex); para código con barras, Write/Edit.
- **[banco]**: los schemas `zz_md_*` / `zz_util_bbdd_md_*` / usuarios `ZZ_MD_*` siguen creados en el banco para medir el «después»; `md_bench.py teardown` los borra. Oracle necesita `system` (`ORACLE_PASSWORD` del contenedor) para crear usuarios.

## Veredicto final
Veredicto: GO (implementación completa: grupos HF, QW, A0–A6, B1, C1–C5, D1–D2, E1, E2a–E2d, F0, G1–G2, H)
Pendientes al cierre:
- VERSION (`/version-closure`): versión con rupturas (`pyproject.toml` + CHANGELOG `[Unreleased]` → versión), push.
- Banco: los schemas `zz_*` siguen creados (`python scripts/bench_metadata.py teardown --engines all --volumes 50,500,5000`).
- Fuera de alcance, registrado en ADR-003: DDL de tabla por tabla fuera de MySQL/MariaDB y reflexión por tabla de
  SQLite en `comparar`/`dump`.
