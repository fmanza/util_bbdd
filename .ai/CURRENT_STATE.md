# CURRENT STATE — util_bbdd

**Generado**: 2026-06-05 (cabecera y «Próximos pasos» actualizados el 2026-10-10 tras v1.0.0)  
**Fuente**: Sesiones activas Mayo-31–Junio-05 + docs Zenical; `CHANGELOG.md` para `v0.11.0` a `v0.39.1` (la tabla de abajo no recoge todas las versiones intermedias: el detalle está en el CHANGELOG)  
**Versión**: `v1.1.0` (2026-10-10, cerrada en local: sin tag ni push hasta autorización; `v1.0.0` publicada con tag y `main` en v1.0.0). Últimos tags: `v0.35.5` a `v0.35.11`, `v0.36.0`, `v0.36.1`, `v0.37.0`, `v0.38.0`, `v0.39.0` a `v0.39.3`, `v0.40.0`, `v0.40.1`, `v0.40.2`, `v0.40.3`, `v0.41.0`, `v0.41.1`, `v0.41.2`, `v0.41.3`, `v0.42.0`, `v0.42.1`, `v0.43.0`, `v0.44.0`, `v1.0.0`  
**Rama activa**: `develop`

---

## Versión actual y release

| Hito | Estado |
|------|--------|
| `v0.9.0` | Liberado — palancas perf bulk: `commit_every_n_chunks`, `IndexManager`, paralelización FK-topológica, `ParallelBulkLoader`, `bulk_insert_from_chunks` |
| `v0.10.0` | Liberado — fast paths INSERT por motor: `PostgresCopyStrategy` (psycopg3 COPY ~10×), `MySQLMultiRowInsertStrategy` (multi-fila), `InsertStrategyResolver` reescrito |
| `v0.11.0` | Liberado 2026-09-22 (tag creado el 2026-09-24 sobre `166448a`) — auditoría completa del proyecto y remediación de 53 hallazgos P0-P2 (sesión `2026-09-22-audit-completo-remediacion`) |
| `v0.12.0` | Liberado 2026-09-24 (tag sobre `42f6f9c`) — performance-audit de `bulk` con banco contra 6 motores reales: 10 fallos corregidos (SQL Server, JSON, binarios, tabla equivocada en MySQL/MariaDB, `generar_sql`), mejoras de INSERT/UPDATE (~2× a ~12,5×) y `update_via_staging` activo por defecto en MySQL/MariaDB (sesiones `2026-09-23-performance-audit-bulk` a `2026-09-24-version-closure-v0.12.0`) |
| `v0.13.0` | Liberado 2026-09-24 (tag sobre `0faf1fa`) — resto del performance-audit de `bulk`: `generar_sql` por plantilla 17–50× (P-06), preparación por bloques con memoria constante (P-07), DELETE de PostgreSQL por arrays 2,3–27× (P-10), límite de 65.535 parámetros en MariaDB (P-13), P-09; P-08 descartado tras medir; 6 fallos corregidos (P-25 a P-29, captura de errores de `ParallelBulkLoader`), entre ellos la pérdida de todas las filas en PostgreSQL con `commit_every_n_chunks` (P-27) (sesiones `2026-09-24-refactor-p09-update-columns` a `2026-09-24-version-closure-v0.13.0`) |
| `v0.14.0` | Liberado 2026-09-25 (tag sobre `44a7b43`) — auditoría de código de `bulk` con 9 hallazgos corregidos (`chunk_size` sin validar, `maintenance_scope` ocultaba errores y no restauraba con `commit_every_n_chunks`, `sync_pk_sequences` en Oracle nunca funcionaba, DELETE sin cadencia de commit, `DISABLE KEYS` con commit implícito en InnoDB…); contenedores de desarrollo/pruebas propios en `127.0.0.1` y puertos no estándar (`docker-compose.yml` ya no define `postgres_db`); suite sin avisos ni saltos «no aplica»; `mkdocs`/`zensical --strict` sin avisos; entorno de performance-audit de `dump` (commit `19ef481`, otra sesión) (sesiones `2026-09-24-bench-containers-independence` a `2026-09-25-version-closure-v0.14.0`) |
| `v0.15.0` | Liberado 2026-09-25 (tag sobre `2b4391a`) — auditoría de `bulk` coherente con la BD (fila escrita al confirmarse el commit) y fail-open ante fallos del CSV con `audit_strict` y contadores (`audit_failures`, `audited_rows`…) en `BulkCrud`, `ParallelBulkLoader` y `dump`; hojas «Auditoría Bulk» y «Secuencias PK» en el Excel de `dump`; **cambio incompatible**: se retira `AuditTransaction`; `generar_sql` ~2,5× más rápido con el mismo SQL (P-31 a P-34: 1M filas INSERT 12,6 → 4,9 s) y literales binarios correctos por motor (C-1/P-30: Oracle corrompía `b"abc"` sin avisar) (sesiones `2026-09-25-audit-code-audit-manager` a `2026-09-25-version-closure-v0.15.0`) |
| `v0.16.0` | Liberado 2026-09-26 (tag sobre `693f9c2`) — `dump` fiable y más rápido tras auditoría con banco real en 6 motores: 12 fallos de corrección (datos alterados sin aviso, SQL Server con columnas en minúsculas y DECIMAL de 38 dígitos, PK sin resincronizar, validación de FK en PG, volcado repetido en PG, reflexión recursiva por FK…); volcado −15 % a −64 % según motor y driver y memoria acotada (Oracle `arraysize`, cursor de servidor, solape lectura/escritura, lotes COPY de 20 000, `executemany` de MariaDB Connector/Python); nuevo `DumpConfig.write_batch_size` y `strip_strings` en `bulk` (sesiones `2026-09-25b-performance-audit-dump-delta` a `2026-09-26t-version-closure-v0.16.0`) |
| `v0.16.1` | Liberado 2026-09-26 (tag sobre `812a020`) — DECIMAL exacto con pymssql (PD-13: un `0E-10` en el lote redondeaba los DECIMAL grandes), cierre de la conexión de lectura de `dump` y de los lectores de rangos al fallar la escritura (audit-code A1/A2), `strip_strings=False` con `numpy.str_` (A3); 28 tests de integración de `dump` contra servidores reales (sesiones `2026-09-26u-tests-integracion-dump` a `2026-09-26y-version-closure-v0.16.1`) |
| `v0.17.0` | Liberado 2026-09-26 (tag sobre `df94154`) — `dump` con SQL Server sin la consulta de FK de SQLAlchemy por tabla: FK de todo el esquema en una consulta (`metadata/sqlserver`) y reflexión sin FK (`reflect_foreign_keys`, nuevo en `BulkCrud`/`ParallelBulkLoader`); 200 tablas 33,9 → 14,3 s. Q8 aparcado y 3.3 (Oracle `APPEND_VALUES`) descartado: roadmap de rendimiento de `dump` cerrado (sesiones `2026-09-26z-q8-medicion` a `2026-09-26zd-version-closure-v0.17.0`) |
| `v0.17.1` | Liberado 2026-09-26 (tag sobre `5113380`) — `DumpConfig` valida `chunk_size` y `commit_every_n_chunks` al construirse (antes vaciaba el destino y fallaba, o dejaba la tabla vacía con estado `success`); refactor de reutilización de `bulk`/`dump` sin cambios funcionales (`orchestrator.py` y `batch.py` divididos, helpers en `bulk/_support/`) (sesiones `2026-09-26ze-code-reusability-bulk-dump` y `2026-09-26zf-version-closure-v0.17.1`) |
| `v0.17.2` | Liberado 2026-09-26 (tag sobre `ce1314b`) — `rows_committed` ya no cuenta las filas de una `bulk_session` fallida con `commit_every_n_chunks`; SQL de catálogo de `bulk`/`dump` en `metadata/` (R11), DDL de integridad compartida (R12) y `SessionScope`/`CommitCadence` (R14), sin cambios funcionales (sesión `2026-09-26zg-version-closure-v0.17.2`) |
| `v0.17.3` | Liberado 2026-09-27 (tag sobre `acf16f7`) — cierre del refactor de reutilización de `bulk`/`dump`: `self.logger` en 6 clases (R16) y opciones de carga del volcado en `DumpOrchestrator._bulk_options()` (R15), sin cambios funcionales (sesión `2026-09-27-version-closure-v0.17.3`) |
| `v0.17.4` | Liberado 2026-09-27 (tag sobre `fb0986b`) — `rows_committed` cuenta las filas de INSERT que confirma el commit periódico de un DELETE en la misma sesión (sesión `2026-09-27b-pendientes-bulk-dump`) |
| `v0.18.0` | Liberado 2026-09-27 (tag sobre `b3e57ac`) — capacidad del pool `pool_size + max_overflow` en `ParallelBulkLoader` y `dump` (con una conexión por worker); `rows_committed` con DELETE; `AuditError` bajo `DatabaseException`; **se retira `BulkInserter`** (incompatible) (sesión `2026-09-27b-pendientes-bulk-dump`) |
| `v0.18.1` | Liberado 2026-09-27 (tag sobre `61dd5f2`) — verificador read-only de condiciones de ejecución por motor (EngineReadinessAdvisor): checks estáticos/dinámicos de pool config, timeouts y parámetros críticos para PostgreSQL, SQLite, SQL Server, Oracle, MySQL/MariaDB; integración opcional en `BulkCrud.__init__()` con triple try/except; 11 hallazgos auditados, 9 corregidos (SQL injection prevention, exception logging, MySQL OK findings); 78 tests nuevos (sesión `2026-09-27-engine-readiness-advisor`) |
| `v0.18.2` | Liberado 2026-09-28 (tag sobre `ad4b08e`) — `EngineReadinessAdvisor.report_once(engine)`: la verificación de condiciones del motor se hace una vez por `Engine` (antes, una por `BulkCrud`: N informes y N conexiones extra en `ParallelBulkLoader`/`dump`); lectura de URL/pool movida de `bulk/crud.py` a `connection/` (sesión `2026-09-27c-readiness-once-per-engine`) |
| `v0.18.3` | Liberado 2026-09-28 (tag sobre `02d0a0c`) — exportación de informes robusta: el Excel de `dump` ya no se pierde por un CSV de auditoría mal formado (`KeyError 'timestamp'`) ni por su propio fallo (`DumpReportError.result` con el `DumpResult`); CSV de auditoría con cabecera no válida apartado como `.invalid-<fecha>.csv`; lock del CSV sin `resolve()` (en Windows perdía filas con varios hilos); `_core/export_safety` (caracteres de control y fórmulas) en los informes Excel y Word de `dump`, `bulk`, `comparar` y `doc`; `AuditExportError`; diagrama de capas (`bulk → connection` de módulo) (sesión `2026-09-27d-export-safety`) |
| `v0.18.4` | Liberado 2026-09-29 — sin cambios de API: revisión de la configuración IA (commands finos sobre prompts, `/performance-audit-constraints`, tipos de commit, `DOCUMENTATION_STANDARD` canónico, `.claude/settings.json` versionado); `docs/` a minúsculas con guion bajo (65 ficheros); README al día; `docs.yml` construye antes de publicar (Pages roto desde `11fb9f8`); ZIP offline con `start-server.py` y `README_OFFLINE.txt` en Releases y en el sitio (`build_offline_zip`); `docs-zip-release.yml` con YAML válido (sesiones `2026-09-28-config-review` y `2026-09-29-docs-review-hotfixes`) |
| `v0.19.0` | Liberado 2026-09-29 — **MySQL como motor propio** (`db_type="mysql"`: PyMySQL + `QueuePool` sync, aiomysql async; metadatos, documentación, relaciones y `migrate` origen/destino); MariaDB sigue con Connector/Python; adapters de metadatos por registro (`_get_metadata_adapter`); extras `util_bbdd[mariadb]`/`util_bbdd[mysql]`; 6 hotfixes: async directa de MariaDB, conexión directa de PostgreSQL, pool sync de PostgreSQL sin `sslmode` (seguridad), `migrate` ejecutable en los 20 pares (comentarios y defaults), DDL reconstruido de MariaDB/MySQL (sesión `2026-09-29b-feature-mysql-pymysql`) |
| `v0.20.0` | Liberado 2026-09-30 — **vistas de `migrate` reescritas con sqlglot** (opcional, `view_strategy`), `CONNECT BY` → CTE recursiva, `MigrationPlan.validate_views`; auditoría de `migrate/` (A1–A9, B1): `execute()` operativo en los 5 destinos, trigger de identidad Oracle, índices por schema, barras invertidas, límites en bytes, colisiones de mayúsculas, `engine`, saltos de línea en comentarios | Estable |
| `v0.21.0` | Liberado 2026-09-30 — **extractores de `migrate` por schema** (823 → 8 consultas, `plan()` −87 % a −98 %), **comentarios** de tablas y columnas desde/hacia PostgreSQL y SQL Server (recortados al límite de cada destino), **`oracle_type` → `source_type` / `category`** (incompatible, con guía de migración), hotfix de FK compuestas de Oracle, tabla sin columnas = ERROR | Estable |
| `v0.22.0` | Liberado 2026-09-30 — **`CONNECT BY`** con `AND LEVEL <= n`, `CONNECT_BY_ISLEAF`, `NOCYCLE` (destino PostgreSQL) y `SELECT *` → CTE recursiva; **comentarios de vistas** desde/hacia PostgreSQL, SQL Server y Oracle; **`MigrationWarning.code`** (`WarningCode`, 21 códigos); fixes de la auditoría (C1, C2, H1, L1, L2) | Estable |
| `v0.23.0` | Liberado 2026-10-01 — **`CONNECT_BY_ISCYCLE`**, **`NOCYCLE` hacia MySQL/MariaDB/SQL Server** (camino de claves por destino, búsqueda binaria), **`ORDER SIBLINGS BY`** (sin orden en SQL Server), comentarios de rutinas al script, hotfix `exp.Expr`; limitación conocida: rutinas no ejecutables en `execute()` (R4) | Estable |
| `v0.23.1` | Liberado 2026-10-01 — hotfixes: **rutinas en `execute()`** (R4: `CREATE` reconstruido en MySQL/MariaDB, nombre y `CREATE OR REPLACE` en Oracle, rutinas de otro dialecto comentadas), firma de `on_post_build` del plugin ZIP, rutinas de Oracle con nombre y owner en los adaptadores de metadatos | Estable |
| `v0.24.0` | Liberado 2026-10-01 — performance-audit de `bulk` (Fases 0–2): **UPDATE de PostgreSQL por tabla temporal** (26,4 → 10,9 s/1M), **DELETE de SQL Server con OPENJSON** (9,3 → 2,7 s/1M; 10K 20×), INSERT por tuplas (PG 6,0 → 4,4 s), `bulk_update_from_chunks`/`bulk_delete_from_chunks`, `last_operation_rows_committed`, `ParallelBulkLoader.update/delete`, reintentos por código de error con backoff y reanudación (cadencia + `max_retries`); listado de rutinas de Oracle solo con procedimientos y funciones | Estable |
| `v0.25.0` | Liberado 2026-10-01 — **hotfix de la 0.24.0**: el DELETE de SQL Server con OPENJSON borraba filas no pedidas si la clave no cabía en el tipo de la PK (ahora solo OPENJSON si cada valor cabe; si no, `IN`); reintento del lock wait timeout (1205) con el conector `mariadb`; **lote por motor y operación** cuando no se fija `chunk_size` (PG INSERT −15 %, DELETE −11 %, SQL Server DELETE −20 %) y tope de 5000 filas por `DELETE … IN` en MySQL/MariaDB | Estable |
| `v0.28.0` | Liberado 2026-10-02 — `BulkCrud.rejects_scope(*, partition, row_offset)` (varias operaciones como una secuencia para los rechazos; un presupuesto de `max_rejects`); `ParallelBulkLoader` sin acceso a miembros privados de `BulkCrud`; corregido `disable_constraints=True` (posición y `max_rejects` por chunk desde la 0.27.0); audit-code de `isolate` de extremo a extremo (partition entera, enteros de numpy, avance tras fallo); banco sin `mariadb_connector` por defecto | Estable |
| `v0.29.0` | Liberado 2026-10-02 — **módulo de auditoría centralizado `util_bbdd.audit`** (ADR-002): `AuditEvent`, `AuditSink` y destinos JSON Lines/memoria/nulo; `audit_sink` opcional en `BulkCrud`, `ParallelBulkLoader`, `DumpConfig`, `MigrationPlan.execute`/`validate_views` con `run_id` común; el CSV de auditoría y el de rechazos se mueven a `audit` con formato idéntico (test byte a byte); `migrate` deja rastro de sus sentencias; correcciones del audit-code (fallos del destino en modo estricto como `AuditError`, eventos construidos dentro del `try`). Sin cambios incompatibles | Estable |
| `v0.30.0` | Liberado 2026-10-03 — **auditoría de `comparar`**: routines fiables (PostgreSQL con agregados, MariaDB/MySQL en otro schema, SQL Server ya no solo la primera, Oracle sin owner; MySQL con routines), comparación sin distinguir mayúsculas de vistas/routines/columnas de índices y FKs, FKs e índices con nombre generado emparejados por estructura, `SqlDiffReporter` ejecutable (SQLite, T-SQL, escape de `\`, orden por FKs); `compare()` con `get_multi_*` y consultas por schema (PG 4,23 → 0,15 s, Oracle 5,18 → 0,26 s, SQL Server 12,23 → 0,86 s con 200 tablas); hotfix de `metadata.postgresql.fetch_routines_sql` con agregados; `scripts/bench_compare.py` | ✅ |
| `v0.31.0` | Liberado 2026-10-04 — **metadatos centralizados y por lotes (ADR-003)**: `metadata/` único punto con SQL de catálogo e `Inspector`; `CatalogSource`/`SchemaSnapshot` con una consulta por tipo de objeto y schema y `CatalogDialect` por motor (PostgreSQL, Oracle, SQL Server, MariaDB/MySQL, SQLite, HSQLDB); `get_*` de los managers tipados sobre el snapshot; `doc`, `analysis`, `migrate`, `dump`, `bulk` y `comparar` migrados (doc HTML 500 tablas: Oracle 368 → 3,2 s, PostgreSQL 57 → 2,1 s; `compare()` 5000 tablas SQL Server 11 016 → 20 consultas); retirados registry de catálogo, adaptadores, `MetadataManager`, cachés antiguas y `metadata.redshift`/`snowflake`; audit-code con F1/F2 corregidos | ✅ |
| `v0.27.1` | Liberado 2026-10-01 — audit-code de la 0.27.0: conciliación de `ParallelLoadResult` válida sin `partition_errors` (M-1), `VARCHAR2` > 4000 por bisección en el UPDATE de Oracle (B-2); integración de MariaDB también con Connector/Python (`mariadb_connector`, `test_mariadb_engine_e2e.py`; 513 → 572 tests); `bench_bulk.py` con `mariadb_connector` (INSERT 1,9×, UPDATE 1,67× sobre PyMySQL); ORA-03106 reproducido en oracledb 4.0.1, 4.0.2 y 26.0.1 (borrador de issue sin publicar) | Estable |
| `v0.27.0` | Liberado 2026-10-01 — `isolate` en Oracle con `batcherrors` (10 malas 1,22× → 1,08×; aísla ORA-12899/01400/01438; UPDATE con LOB por bisección por ORA-03106), `ParallelBulkLoader(on_error="isolate")` (columna `particion`, sin reintento con rechazos, `max_rejects` por partición), `DumpConfig(on_error="isolate")` (tabla `success` con `rows_rejected`, columna «Filas Rechazadas»); escalado de `ParallelBulkLoader` re-medido (PostgreSQL con psycopg 3 1,05×, no 2,6×) | Estable |
| `v0.26.0` | Liberado 2026-10-01 — `BulkCrud(prefetch_blocks)` (SQL Server INSERT −10,6 %, MySQL/MariaDB −2 % a −6 %) y `BulkCrud(on_error="isolate", rejects_csv_path, max_rejects)` (SAVEPOINT + bisección; 1M limpio 1,00–1,02×, 10 malas 1,13–1,23×, PG 1,65×) con su audit-code (M-1, B-1, B-3, B-4); P-1: filtro de OPENJSON por columna (DELETE 1M SQL Server 2,47 → 2,17 s) | Estable |
| `v0.25.1` | Liberado 2026-10-01 — deuda A3–A5 del audit-code: `*_from_chunks` dentro de un `bulk_session` abierto → `RuntimeError` (antes `database is locked` en SQLite o sesión externa sin conexión); nota «se ejecutó; falló el COMMIT periódico posterior»; `__batch_note` tipado | Estable |
| `v0.35.5`–`v0.35.8` | Liberados 2026-10-08 — correcciones P0–P2 de la FASE 1 de `drivers-connections-audit`: credenciales escapadas en las URL de los Engine, Engine con TLS/charset de `conn_params` (`creator`), lista blanca de `conn_params`, thick mode de Oracle, TLS de aiomysql y cifrado de SQL Server, DSN de Oracle único, HSQLDB nativo corregido, contraseñas fuera de `repr` (sesiones `2026-10-08b` a `2026-10-08e`) | ✅ |
| `v0.35.9`–`v0.35.11` | Liberados 2026-10-09 — FASE 4 sin cambios funcionales: código muerto fuera (B6), helpers de URL de los Engine compartidos (B5), una sola traducción a aiomysql (B4) | ✅ |
| `v0.36.0` | Liberado 2026-10-09 — política de pool común de los Engine sync/async desde `conn_params` (`pool_recycle` 3600), `close_timeout` en `*PoolConfig`, `SyncPoolCloseMixin` (B3; **cambia el pool del Engine sync**) | ✅ |
| `v0.36.1` | Liberado 2026-10-09 — hotfix: el pool async de Oracle no se podía crear (python-oracledb 4.x) | ✅ |
| `v0.37.0` | Liberado 2026-10-09 — validación única de `conn_params` desde las configs; **`AsyncDatabaseManager` lanza `ValidationError`** como el sync; `schema` por defecto (`public`/`dbo`/`PUBLIC`) en todos los caminos (B1; incompatible) | ✅ |
| `v0.38.0` | Liberado 2026-10-09 — `catalog_charset_mode` (`auto`/`native`/`convert`) en MariaDB/MySQL (CS) | ✅ |
| `v0.39.0`–`v0.39.1` | Liberados 2026-10-09 — **TLS en MariaDB** (`ssl`, `ssl_ca`, `ssl_cert`, `ssl_key`, `ssl_verify_cert`) en sync, async, pools y Engine (B2); hotfix F1/F2 de la FASE 5. Decisiones en ADR-005; auditoría `drivers-connections-audit` cerrada | ✅ |
| `v0.40.0`–`v0.40.3` | Liberados 2026-10-09 — URL de los Engine sync/async con la misma semántica; hotfixes de `EngineReadinessAdvisor`, `init_command` y reset del pool MariaDB | ✅ |
| `v0.41.0` | Liberado 2026-10-09 — auditoría de `doc/` + `analysis/`: diagramas Graphviz por lotes (HTML 12,6×), un generador por documentación, inventario de almacenamiento declarativo, **API de `util_bbdd.doc` reducida** (`DatabaseDocumentation` + `DocumentationResult`, errores propios) | ✅ |
| `v0.41.1` | Liberado 2026-10-10 — DDL de tabla de HSQLDB (fallaba siempre), DDL en HTML sin decodificar entidades, orden estable del inventario de almacenamiento | ✅ |
| `v0.41.2` | Liberado 2026-10-10 — hotfix H1: las lecturas de catálogo terminan la transacción que abren (MySQL con `use_pool=False` veía metadatos obsoletos); dorado de Oracle aislado, genéricos con parámetros en `doc`/`analysis`, tests de matplotlib | ✅ |
| `v0.41.3` | Liberado 2026-10-10 — F3/F4 precarga de SQL Server (tablas inexistentes, collation sensible a mayúsculas), F5 `clear_cache` dirigido con usuario Oracle entrecomillado | ✅ |
| `v0.42.0` | Liberado 2026-10-10 — DDL de HSQLDB con PK, `routine_parameters` indexado (F7), workflow de integración en CI | ✅ |
| `v0.42.1` | Liberado 2026-10-10 — condiciones de `/audit-code`: CI con MariaDB Connector/C, H1 en SQL Server con tests, 12 tests unitarios rotos sin el banco | ✅ |
| `v0.43.0` | Liberado 2026-10-10 — **API pública 1.0, fase 0.43.0**: raíz con 13 puntos de entrada y carga perezosa, `util_bbdd.exceptions`, 46 alias deprecados, managers simétricos (`.ai/sessions/2026-10-10-api-1-0/`) | ✅ |
| `v0.44.0` | Liberado 2026-10-10 — excepciones con `__module__` público `util_bbdd.exceptions`; pickles antiguos compatibles (`.ai/sessions/2026-10-10-exceptions-module-name/`) | ✅ |
| `v1.0.0` | Liberado 2026-10-10 (tag sobre `158903b6`; `main` en v1.0.0) — **API pública estable**: alias de 0.x y `close_connection()` retirados; documentación revisada para 1.0; cobertura 91 % (`.ai/sessions/2026-10-10-api-1-0-final/`) | ✅ |
| `v1.1.0` | Cerrado en local 2026-10-10 — rutas `str` en `bulk`/`dump`; **hotfix**: consultas async de PostgreSQL (asyncpg), filas de pyodbc anidadas, `driver_name` en el pool async de SQL Server; `BulkCrud` dividido por dentro (`TableMaintenance`, `RejectsCoordinator`); 0 `ResourceWarning` con `--cov`; guías de rendimiento, constraints y `migrate` revisadas (`.ai/sessions/2026-10-10-plan-pendientes-post-1-0/`) | ✅ (sin push) |
| Zenical | Hecho — `migrate/zenical-pure` fusionada (PR #19, `c6d765a8`); `zensical` 0.0.44 es el generador del CI y lee `mkdocs.yml` (no se usa `zensical.toml`) | ✅ |

PR #18 (`MySQLVariableValidator`): su código (`9a71e056`) está en `main` y `develop`; el estado de la PR en GitHub no se ha comprobado (sin `gh`) — cerrarla si sigue abierta.  
PR #19 (`migrate/zenical-pure`): fusionada.  

**Tests actuales** (v1.1.0, 2026-10-10): `pytest` completo sin URLs del banco 5730 passed, 531 skipped; con el banco y `JAVA_HOME` 6254 passed, 7 skipped; con `--cov`, sin `ResourceWarning` ni `SADeprecationWarning`; mypy sin errores (334 ficheros). Anterior (v1.0.0): 5678 passed, 523 skipped sin banco; 6194 passed con banco; cobertura 91 %. Anterior (v0.44.0): 5679 / 6195 passed. Anterior (v0.43.0): 5594 passed sin banco, 6110 passed con banco; mide siempre también sin el banco, que es lo que ve el CI. Anterior (v0.42.1): 5512 passed, 523 skipped sin banco; 6028 passed, 7 skipped con banco (`tests/integration` 581 passed). Anterior (v0.42.0): `tests/integration` 577 passed; mypy sin errores (331 ficheros). Anterior (v0.39.1): 5397 passed, 497 skipped; integración 552 passed. Medición anterior: 5049 passed, 496 skipped con `pytest` completo sin URLs de servidor y el entorno de referencia `pip install -e ".[dev,docs]"` (v0.31.0, 2026-10-04); con las URLs del banco (`scripts/bench_env.example.*`), `tests/integration`: 551 passed, 10 skipped en 5 servidores (menos que en v0.30.0: se retiraron los tests de los módulos eliminados). mypy sin errores (320 ficheros). Sin las dependencias del extra `dev` los recuentos bajan (módulos que se saltan enteros) y `tests/conftest.py` lo avisa: ver `.ai/sessions/2026-10-02f-test-count-drift/TRACEABILITY.md`.

---

## Trabajo activo (sesiones más recientes)

### Documentación y estándares IA (2026-06-03 a 2026-06-05)
- **Estándar documental v2** implementado: 5 arquetipos × 5 secciones, 7 secciones nav MkDocs, enlace bidireccional api↔examples, autodoc Bulk+Dump corregidos. (`2026-06-03-docs-standard-v2`)
- **`--verify-tools`** (consulta webs oficiales) y **`--verify-build`** (build local + lectura `site/` o `localhost:8000`) incorporados como modificadores del agente Documentation Generator. Guía pública: `docs/guides/doc_verification_guide.md`. (`2026-06-05-verify-docs`)
- **Bootstrap IA cross-project** implementado: prompt `.github/prompts/bootstrap_ai_config.prompt.md` (modelo PULL, 5 plataformas: Claude, Gemini, Copilot, Cursor, Codex). Commit `cd22520` en develop, push/PR pendiente. (`2026-06-05-bootstrap-ai-config`)

### Hotfix crítico MariaDB (2026-06-04)
- **`utf8mb4_uca1400_ai_ci`** establecida como collation por defecto en `migrate/charset.py` (requiere MariaDB ≥ 10.10). Para MariaDB < 10.10 o MySQL pasar `collation=` explícito. (`2026-06-04-mariadb-default-collation-uca1400`)

### Performance bulk (2026-05-31 a 2026-06-02)
- **MySQL auto-config variables**: `MySQLVariableValidator` + `MySQLOptimalConfig` + `BulkCrud.__validate_mysql_config()` — detecta `innodb_buffer_pool_size` / `max_allowed_packet` en `__init__`, logging read-only, sin SUPER requerido. (`2026-06-01g`)
- **SQL template caching** `MySQLMultiRowInsertStrategy._sql_template_cache` por `(num_rows, cols_tuple)` — 5–20% mejora en sub-lotes iguales. (`2026-06-01f`)
- **`RangePartitioner` + `HashPartitioner`** + métricas `PartitionResult`/`ParallelLoadResult` + `maintenance_scope` por worker. (`2026-06-02b`, `2026-06-02`)
- **Paralelismo corregido**: `_resolve_max_workers` acota a `pool_size` (previene deadlock), `_hoist_constraints_for_workers` deshabilita DDL una vez para MSSQL/PG. (`2026-06-02`)
- **`PKSequenceSyncer`**: sincronización automática de contadores PK post-bulk para PostgreSQL/SQLServer/MariaDB/Oracle ≥ 12c. (`2026-05-31-pk-sync-post-bulk`)
- **Dump sin comparación de esquemas**: eliminada cascada N+1 queries (`SchemaComparator.compare()`) del `DumpOrchestrator.run()`. (`2026-06-01b`)

---

## Migración a Zenical

Completada: PR #19 fusionada (`c6d765a8`). `zensical build` (0.0.44, en el entorno `.[docs]`) y `mkdocs build` leen el
mismo `mkdocs.yml`; el CI publica con Zensical. Ver `ZENICAL.md`.

---

## Próximos pasos

**Plan vigente**: `.ai/sessions/2026-10-10-plan-pendientes-post-1-0/PLAN_AUDIT_PLAN.md` (inventario verificado el
2026-10-10; decisiones D1–D6 aceptadas). El historial de planes anteriores está en `CHANGELOG.md` y en
`.ai/sessions/2026-10-10-plan-pendientes-global/`.

| ID | Pendiente | Estado | Bloque / versión |
|---|---|---|---|
| P1 | `main` en v1.0.0 | ✅ Hecho 2026-10-10: fast-forward a `158903b6` y push de `main` | B1 |
| P2 | A5: SRP de `BulkCrud` por dentro (re-alcance D2: mantenimiento de tabla y orquestación del aislamiento a `bulk/_support/`; la auditoría ya estaba fuera) | ✅ Hecho (v1.1.0, `0b0ba205`, `c9bb3598`) | B4 |
| P3 | Rutas `str` en los parámetros de ruta de `bulk`, `ParallelBulkLoader` y `dump` (`DumpConfig(output_dir=str)` carga y pierde el `DumpResult`) | ✅ Hecho (v1.1.0, `587e7f40`) | B3 |
| P4 | 340 `ResourceWarning` con `--cov` (Engines SQLite sin `dispose()` en 40 ficheros de test) y 3 `SADeprecationWarning` en `tests/_core/test_batching.py` | ✅ Hecho (`e7cb3676`, `2369e6ed`) | B2 |
| P5 | Revisión página a página de rendimiento, constraints y `migrate_*` (18 páginas) + instalación por PyPI residual; mover `constraints_*`/`performance_audit_*` a `docs/guides/` | ✅ Hecho (v1.1.0, `e14dd441`, `ac605edc`); nivel 2 (~85 páginas) pendiente | B5 |
| P6 | Esta lista | ✅ Rehecha 2026-10-10 | B0 |
| N1 | `doc_agents.yml` heredado (APIs externas, módulo inexistente) | ✅ Retirado 2026-10-10 | B0 |
| H1 | Hotfix: consultas async de PostgreSQL (asyncpg) rotas desde v0.5.6 (encontrado en B5) | ✅ Hecho (v1.1.0, `d369c8e3`) | — |
| R1 | Release 1.1.0: tag `v1.1.0`, push de `develop` y fast-forward de `main` | Pendiente de autorización | B7 |
| D2 | Revisión de docs nivel 2 (~85 páginas) y `docs/examples/migrate_*` | Pendiente | `docs` |
| A1 | `AsyncDatabaseManager("sqlserver")` sondeado con el ODBC Driver 18 instalado: filas anidadas con pyodbc (también en sync) y pool async sin `driver_name` | ✅ Hecho (v1.1.0, `cf7abb78`, `1c83041b`) | — |
| A2 | `driver_name` por defecto = ODBC Driver 17: con solo el 18 instalado hay que indicarlo (¿detectar el instalado?) | Por decidir | `/new-feature` |
| P7 | Externos (los comprueba el usuario; sin `gh`): PR #18 (probablemente cerrada: no existe `refs/pull/18/merge`), issue del ORA-03106 (`.ai/sessions/2026-10-01y-ora03106-repro/ISSUE_DRAFT.md`), `docs-release.yml` de v0.43.0/v0.44.0/v1.0.0, `integration.yml` | Usuario | B6 |
| N2 | 8 ramas `origin/dependabot/*` (2026-03-31 a 2026-06-23) | Usuario | B6 |
| — | Aparcados: S-1 (`bulk` con procesos, NO_GO hasta ≥ 10M filas/tabla) y las dos limitaciones de driver de `docs/roadmap.md` | Aparcado | — |

---

## Motores soportados

| Motor | Como fuente | Como destino | Notas |
|-------|-------------|--------------|-------|
| Oracle | ✅ | ✅ | SEQUENCE+TRIGGER; identity mode opcional |
| MariaDB | ✅ | ✅ | Default collation: `utf8mb4_uca1400_ai_ci` (≥10.10); driver sync MariaDB Connector/Python; TLS opcional desde v0.39.0; banco validado: 11.4 |
| MySQL | ✅ | ✅ | `db_type="mysql"` (PyMySQL/aiomysql); collation destino `utf8mb4_0900_ai_ci` |
| PostgreSQL | ✅ | ✅ | SERIAL/BIGSERIAL/SMALLSERIAL; `PostgresCopyStrategy` |
| SQL Server | ✅ | ✅ | IDENTITY(1,1); `fast_executemany` |
| SQLite | — | ✅ | |
| HSQLDB | — | ✅ | |

**Matriz migrate/**: 5 motores (Oracle, MariaDB, MySQL, SQL Server, PostgreSQL) → 20 flujos DDL. Con H3/H4 (E5) los 20 pares crean todas las tablas en servidores reales; las vistas siguen en pass-through (revisión manual).

---

## Calidad actual

Medido el 2026-09-26 (sesión `2026-09-26ze-code-reusability-bulk-dump`):

- **Lint**: `ruff check src tests` → 0 errores
- **Tipos**: `mypy src tests/unit/test_protocol_conformance.py` → 0 errores (356 source files)
- **Tests**: 5124 passed / 199 skipped sin URLs de servidor
- **Cobertura de ramas `bulk/` + `dump/`**: 92 % (`coverage run --branch --source=src/util_bbdd/bulk,src/util_bbdd/dump`;
  `pytest --cov` falla con Python 3.14 + numpy al importar el paquete dos veces)
- **Build docs**: `mkdocs build --strict` → 0 errores, 0 warnings
- **Complejidad cognitiva**: reporters ≤ 4, emitter `_topological_sort` → 0 (desglosado en helpers)
