# CURRENT STATE — util_bbdd

**Generado**: 2026-06-05 (cabecera, tabla de versiones y tests actualizados el 2026-09-29 en los cierres de `v0.18.0` a `v0.18.4`)  
**Fuente**: Sesiones activas Mayo-31–Junio-05 + docs Zenical; `CHANGELOG.md` para `v0.11.0` a `v0.18.4`  
**Versión**: `v0.18.4` (liberada 2026-09-29). Tags de git: `v0.17.4`, `v0.18.0`, `v0.18.1`, `v0.18.2`, `v0.18.3`, `v0.18.4`  
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
| `v0.27.0` | Liberado 2026-10-01 — `isolate` en Oracle con `batcherrors` (10 malas 1,22× → 1,08×; aísla ORA-12899/01400/01438; UPDATE con LOB por bisección por ORA-03106), `ParallelBulkLoader(on_error="isolate")` (columna `particion`, sin reintento con rechazos, `max_rejects` por partición), `DumpConfig(on_error="isolate")` (tabla `success` con `rows_rejected`, columna «Filas Rechazadas»); escalado de `ParallelBulkLoader` re-medido (PostgreSQL con psycopg 3 1,05×, no 2,6×) | Estable |
| `v0.26.0` | Liberado 2026-10-01 — `BulkCrud(prefetch_blocks)` (SQL Server INSERT −10,6 %, MySQL/MariaDB −2 % a −6 %) y `BulkCrud(on_error="isolate", rejects_csv_path, max_rejects)` (SAVEPOINT + bisección; 1M limpio 1,00–1,02×, 10 malas 1,13–1,23×, PG 1,65×) con su audit-code (M-1, B-1, B-3, B-4); P-1: filtro de OPENJSON por columna (DELETE 1M SQL Server 2,47 → 2,17 s) | Estable |
| `v0.25.1` | Liberado 2026-10-01 — deuda A3–A5 del audit-code: `*_from_chunks` dentro de un `bulk_session` abierto → `RuntimeError` (antes `database is locked` en SQLite o sesión externa sin conexión); nota «se ejecutó; falló el COMMIT periódico posterior»; `__batch_note` tipado | Estable |
| Zenical | Pendiente, sin versión asignada — merge `migrate/zenical-pure` (+80% perf doc builds) cuando Zenical esté instalable |

PR abierta: **PR #18** `feat(connection/bulk): automatización variables MySQL/MariaDB` — revisión pendiente de merge.  
PR en espera: **PR #19** `migrate/zenical-pure` — bloqueada hasta que Zenical v0.0.44 esté en crates.io (o instalación manual de binario).

**Tests actuales**: 5978 passed, 367 skipped sin URLs de servidor (cierre de `v0.27.0`); con las URLs del banco (`scripts/bench_env.example.*`), `tests/integration`: 513 passed en 5 servidores (cierre de `v0.27.0`, 2026-10-01; SQL Server con pyodbc; `isolate and mssql` también con pymssql).

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

| Estado | Detalle |
|--------|---------|
| **Configuración** | `zensical.toml` (634 L) completo y validado. 92 docs .md, 44 diagramas Mermaid — 100% compatibles, 0 cambios en contenido. |
| **CI/CD** | `.github/workflows/docs.yml` actualizado (`zensical build` + `peaceiris/actions-gh-pages`). |
| **Instrucciones IA** | `CLAUDE.md`, `copilot-instructions.md`, `ZENICAL.md` — referencias actualizadas. |
| **Bloqueador** | Zenical v0.0.44 NO publicado en crates.io (solo v0.0.3 placeholder). |
| **Solución A (ahora)** | Descargar binario precompilado desde https://github.com/zensical/zensical/releases/tag/v0.0.44, copiar a `%USERPROFILE%\.cargo\bin\`. |
| **Solución B (esperar)** | Aguardar publicación en crates.io (~2026-Q3), usar `cargo install zensical --version 0.0.44`. |
| **Rama** | `migrate/zenical-pure` (5 commits, lista para merge cuando Zenical esté disponible). |
| **Build actual** | MkDocs Material 9.5 funcional (`mkdocs build` en 5.5s, 0 errores). |

**Ventaja de migrar**: build 300ms → 80ms (−73%), page load 400ms → 100ms (−75%), −50% dependencias docs.

---

## Próximos pasos

0. **Push de `develop` y del tag `v0.27.0`**, pendientes de decisión del usuario (`v0.26.0` ya publicada). Roadmap de `bulk`: S-1 (procesos) NO_GO hasta un caso real ≥ 10M filas por tabla; reportar a python-oracledb el ORA-03106 (UPDATE + LOB + `batcherrors`, `2026-10-01r/s5_ora03106.py`); lock entre procesos del CSV de rechazos y de la auditoría si algún día se usan procesos.
1. **Merge PR #18** (`MySQLVariableValidator`) tras review. Potencial tag `v0.10.1`.
2. **Zenical opción A** (decisión del usuario): descargar binario, validar `zensical build`, merge `migrate/zenical-pure`, tag `v0.11.0`.
3. **FASE 5 doc estándar** (criterios de aceptación): pendiente validación QA — no rellenar `## 4. Criterios de Aceptación` en `docs/functional/*.md` hasta esa sesión.
4. **Push commit `cd22520`** (bootstrap IA) o PR a main — pendiente decisión del usuario.

---

## Motores soportados

| Motor | Como fuente | Como destino | Notas |
|-------|-------------|--------------|-------|
| Oracle | ✅ | ✅ | SEQUENCE+TRIGGER; identity mode opcional |
| MariaDB | ✅ | ✅ | Default collation: `utf8mb4_uca1400_ai_ci` (≥10.10); driver sync MariaDB Connector/Python |
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
