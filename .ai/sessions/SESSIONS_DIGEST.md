# SESSIONS DIGEST — util_bbdd

Resumen comprimido de todas las sesiones de trabajo.  
**Sesiones hasta 2026-05-28** → archivadas en `.ai/doc_old/sessions/` (detalle completo allí).  
**Sesiones desde 2026-05-31** → activas en `.ai/sessions/`.

Para el índice maestro detallado ver `INDEX.md`. Para decisiones tomadas ver `.ai/DECISIONS_LOG.md`.

---

## FASE 1 — Refactorización inicial (Mar 2026) → `doc_old/`

| Fecha | Sesión | Cambio principal | Estado |
|-------|--------|-----------------|--------|
| 2026-03-22 | Refactor v0.6.0 | Refactorización relaciones N niveles | CLOSED → `doc_old/` |
| 2026-03-24 | Metodología IA + v0.6.1 HTML | Primer slice HTML reports | CLOSED → `doc_old/` |
| 2026-03-25 | Metodología IA + v0.6.2 | Consolidación semántica | CLOSED → `doc_old/` |

---

## FASE 2 — Foundation y reporters (Abr 2026) → `doc_old/`

| Fecha | Sesión | Cambio principal | Estado |
|-------|--------|-----------------|--------|
| 2026-04-10 | v0.6.7 maturity + tech-debt | Refactor facades legacy; release v0.6.7 | CLOSED → `doc_old/` |
| 2026-04-13 | audit-code capabilities | Duplicación `_core` detectada | CLOSED → `doc_old/` |
| 2026-04-13b | tech-debt comparar/ D1-D6 | Gaps multimotor Fases 0-3 | CLOSED → `doc_old/` |
| 2026-04-13c | version-closure v0.6.7 | Release final v0.6.7 | CLOSED → `doc_old/` |
| 2026-04-13d | v0.6.8-dev init | Phase 4 L1/L2/L3 planificadas | IN_PROGRESS → `doc_old/` |
| 2026-04-14 | SchemaDiff reporters | HTML/Excel/Word/Markdown en `comparar/reporters/` | CLOSED → `doc_old/` |
| 2026-04-15/16 | Reporters OOP + SQL | SqlDiffReporter 7 dialectos; HTML Mermaid tabbed | CLOSED → `doc_old/` |
| 2026-04-16d | Excepciones comparar/ | `ComparerError` + 3 subclases | CLOSED → `doc_old/` |
| 2026-04-18 | Logging typed 36 clases | v0.6.8 Phase 4B logging completo | CLOSED → `doc_old/` |
| 2026-04-20 | Refactor managers/ | `MetadataRequestBuilder`, `CharsetCollationParser`, `DDLNormalizer` (v0.6.9) | CLOSED → `doc_old/` |
| 2026-04-21 | Legacy cleanup | 31 funciones deprecated eliminadas | CLOSED → `doc_old/` |
| 2026-04-21b | tech-debt inventario | 21 ítems `comparar/+doc/`; plan Fases 1-3 | CLOSED → `doc_old/` |
| 2026-04-21c | Refactor estructural comparar/ | RoutineFetcherRegistry, DdlNormalizer, ports split | CLOSED → `doc_old/` |

---

## FASE 3 — DDL Migration + Documentación (May 2026 parte 1) → `doc_old/`

| Fecha | Sesión | Cambio principal | Estado |
|-------|--------|-----------------|--------|
| 2026-05-02 | Documentation Fases 1-6 | SyncDatabaseManager piloto; docs funcional+técnica+ejemplos | CLOSED → `doc_old/` |
| 2026-05-14 | config_review IA | 7 refs `project_copy` eliminadas; Python 3.12+ | CLOSED → `doc_old/` |
| 2026-05-14b | docs-audit 11 hallazgos | Extras pip reales; arquitectura real; v0.8.0 | CLOSED → `doc_old/` |
| 2026-05-18 | migrate/ Oracle→MariaDB | Pipeline 3 capas; 30+ tipos; 82 tests; docs | CLOSED → `doc_old/` |
| 2026-05-19 | migrate/ refactor prod | `int_display_width`; FK externas; PK→AUTO_INCREMENT | CLOSED → `doc_old/` |
| 2026-05-19b | reporters complejidad | `markdown.py` 25→≤2; `text.py` 22→≤2 | CLOSED → `doc_old/` |
| 2026-05-19c | emitter refactor | `_topological_sort` 29→0 | CLOSED → `doc_old/` |
| 2026-05-19d | docs-audit migrate/ | 2 L1 + 5 L2 aplicados; typo "pérdida" | CLOSED → `doc_old/` |
| 2026-05-19g | hotfix NUMBER PK v3 | NUMBER PK→INT(11) AUTO_INCREMENT definitivo | CLOSED → `doc_old/` |
| 2026-05-20 | migrate/ Oracle→SQLServer | `OracleToSQLServerTransformer`; 113 tests | CLOSED → `doc_old/` |
| 2026-05-20b | migrate/ Oracle→PostgreSQL | SERIAL/BIGSERIAL; `pg_schema`; 122 tests | CLOSED → `doc_old/` |
| 2026-05-20c | migrate/ vistas 3 targets | `CanonicalView` IR; `rewrite_oracle_view()`; 93 tests | CLOSED → `doc_old/` |
| 2026-05-20d | migrate/ MariaDB→Oracle/SS/PG | `MariaDBSchemaExtractor`; 177 tests | CLOSED → `doc_old/` |
| 2026-05-21 | migrate/ SQLServer→3 targets | Completa matriz 3×3; ~184 tests | CLOSED → `doc_old/` |
| 2026-05-21b | migrate/ PostgreSQL→3 targets | Completa matriz 4×3 (12 flujos); 205 tests | CLOSED → `doc_old/` |
| 2026-05-21c | tech-debt migrate/ P1-P2 | 8 bugs (SEQ/TRG duplicados, FK RESTRICT, etc.) | CLOSED → `doc_old/` |
| 2026-05-21d | SQL desacoplado extractors | `migrate/sql/` creado (luego eliminado en 2026-05-22) | CLOSED → `doc_old/` |
| 2026-05-21e | docs full audit 6 fases | 72 ficheros verificados; nav sincronizado | CLOSED → `doc_old/` |
| 2026-05-21f | hotfix MariaDB charset crash | `SET NAMES 'binary'` vía SQL; 18 tests | CLOSED → `doc_old/` |
| 2026-05-21g | hotfix PostgreSQL schema | `schema` campo añadido a config + conninfo | CLOSED → `doc_old/` |
| 2026-05-21h | tech-debt metadata async | `get_running_loop`; SqlServerAsyncAdapter Protocol | CLOSED → `doc_old/` |
| 2026-05-22 | comparar/ short report names | `_build_short_label()`; IP último octeto; 11 tests | CLOSED → `doc_old/` |
| 2026-05-22b | comparar/ IP hostname | IPv4 último octeto en labels | CLOSED → `doc_old/` |
| 2026-05-22c | hotfix package-data templates | `diff_report.html.j2` ausente en wheel | CLOSED → `doc_old/` |
| 2026-05-22d | governance IA metadata rules | REGLAS #1–#6 metadata access formalizada | CLOSED → `doc_old/` |
| 2026-05-22e | migrate/ routines | `CanonicalRoutine` IR; 4 extractores+emisores; 67 tests | CLOSED → `doc_old/` |
| 2026-05-22f | hotfix masked_pass | password con `@` enviaba `***` al servidor | CLOSED → `doc_old/` |
| 2026-05-22g | hotfix sqlserver routines | `execute()` API inválida → `_query()`; 4 tests | CLOSED → `doc_old/` |
| 2026-05-22h | hotfix mariadb autoincrement | AUTO_INCREMENT siempre `INT(11)` | CLOSED → `doc_old/` |
| 2026-05-22i | hotfix PythonFinalizationError | `sys.is_finalizing()` guard en pool PG | CLOSED → `doc_old/` |
| 2026-05-22j | reporters rutinas | Markdown+Text con body PROCEDURE/FUNCTION | CLOSED → `doc_old/` |
| 2026-05-22k | hotfix sqlserver tests | Tests reescritos tras cambio API routines | CLOSED → `doc_old/` |
| 2026-05-22l | PACKAGE BODY Oracle | `_fetch_routine_body("PACKAGE BODY")`; source info | CLOSED → `doc_old/` |
| 2026-05-22m | hotfix SS FUNCTION | `sys.objects FN/IF/TF`; 3 tests | CLOSED → `doc_old/` |
| 2026-05-22n | hotfix package member body | `_emit_create_routine` return anticipado eliminado | CLOSED → `doc_old/` |
| 2026-05-24 | hotfix Oracle routine exact copy | Body verbatim sin CREATE OR REPLACE | CLOSED → `doc_old/` |
| 2026-05-25 | dump/ módulo nuevo | `DumpOrchestrator`, `DumpPlanner`, `DumpReporter`; 50 tests; docs | CLOSED → `doc_old/` |
| 2026-05-25b | bulk override_identity | `OVERRIDING SYSTEM VALUE` PG GENERATED ALWAYS | CLOSED → `doc_old/` |
| 2026-05-25c | migrate oracle_identity_mode | `sequence_trigger` vs `identity_by_default_on_null` | CLOSED → `doc_old/` |
| 2026-05-25d | bulk sqlserver IDENTITY INSERT | `SET IDENTITY_INSERT ON/OFF` automático | CLOSED → `doc_old/` |
| 2026-05-25e | bulk exclude_autoincrement_pk | Excluye PK autoincremental del INSERT | CLOSED → `doc_old/` |
| 2026-05-26 | bulk audit+fix | Bug inmutabilidad DataFrame; timing; dead code | CLOSED → `doc_old/` |
| 2026-05-26b | dump tech-debt D1-D8 | Import circular→`_models.py`; quoting→`_sql_utils.py` | CLOSED → `doc_old/` |
| 2026-05-26c | dump audit+fix | `_disabled_pg` tracking; FK BFS; Oracle batch | CLOSED → `doc_old/` |
| 2026-05-26d | BulkInserter Protocol | `dump/_protocols.py`; desacopla dump de BulkCrud | CLOSED → `doc_old/` |
| 2026-05-26e | dump+comparar audit | B1-B3 quoting, NULL DDL, default guard | CLOSED → `doc_old/` |
| 2026-05-26f | comparar audit+fix | FK anónimas; SS functions; PG overloads; password `@` | CLOSED → `doc_old/` |
| 2026-05-26g | comparar tech-debt D1-D12+N1-N19 | TC006/RUF/BLE001/PERF401/TID252; 279 tests | CLOSED → `doc_old/` |
| 2026-05-26h | tech-debt cross dump+comparar | CP1-CP4, RF1-RF2, ciclos FK PG BFS; S3776 | CLOSED → `doc_old/` |
| 2026-05-28 | hotfix migrate routine header | `-- PROCEDURE: name` antes del NOTE | CLOSED → `doc_old/` |

---

## FASE 4 — Performance + Estabilización (May-31 – Jun-05 2026) → ACTIVAS

| Fecha | Sesión | Cambio principal | Estado |
|-------|--------|-----------------|--------|
| 2026-05-31 | dump cross-engine + DumpAuditSummary | 6 bugs cross-engine; `DumpAuditSummary` dataclass; 3440 passed | CLOSED |
| 2026-05-31b | perf bulk/dump | hot-path triple str-key; `fast_executemany`; `execute_values`; TRUNCATE híbrido SS | CLOSED |
| 2026-05-31c | dump performance | Identity Map `_table_cache`; `bulk_session(atomic=True)`; `collect_row_counts` | CLOSED |
| 2026-05-31d | hotfix Oracle DEFAULT doble comillado MariaDB | Strip comillas externas en `_format_default` | CLOSED |
| 2026-05-31e | hotfix mismo DEFAULT PG+SS | Mismo fix en `postgresql.py` y `sqlserver.py` | CLOSED |
| 2026-05-31f | PKSequenceSyncer | Auto-sync contadores PK tras bulk; 4 motores; 28 tests | CLOSED |
| 2026-06-01 | dump comparator columns case-insensitive | `_compare_columns_from_raw` case-insensitive; 5 tests | CLOSED |
| 2026-06-01b | dump sin comparación de esquemas | Eliminada cascada N+1 `SchemaComparator.compare()` | CLOSED |
| 2026-06-01c | v0.9.0 palancas rendimiento | `commit_every_n_chunks`, `IndexManager`, `ParallelBulkLoader`, `bulk_insert_from_chunks`; v0.9.0 | CLOSED |
| 2026-06-01d | v0.10.0 fast paths INSERT | `PostgresCopyStrategy` (~10×); `MySQLMultiRowInsertStrategy`; `InsertStrategyResolver`; v0.10.0 | CLOSED |
| 2026-06-01e | SonarQube+Pylance fixes | S1244 float; reportArgumentType; BLE001 async | CLOSED |
| 2026-06-01f | SQL template caching MySQL | `_sql_template_cache` por `(num_rows, cols_tuple)`; 5-20% mejora; 11 tests | CLOSED |
| 2026-06-01g | MySQL variables auto-config | `MySQLVariableValidator`, `MySQLOptimalConfig`, `__validate_mysql_config()`; 26 tests; PR #18 | CLOSED |
| 2026-06-02 | maintenance_scope bug crítico | `RuntimeError` explícito sin `bulk_session`; PG superuser fix | CLOSED |
| 2026-06-02b | RangePartitioner + métricas | `PartitionResult`, `ParallelLoadResult`; `maintenance_scope` por worker | CLOSED |
| 2026-06-02c | Paralelismo safe + HashPartitioner | `_resolve_max_workers` acota pool_size; constraints one-time DDL; 77 tests; 3826 passed | CLOSED |
| 2026-06-03 | Estándar documental v2 | 5 arquetipos × 5 secciones; 7 nav; autodoc alias fix; `mkdocs build --strict` 0 errores | CLOSED |
| 2026-06-04 | hotfix MariaDB collation UCA1400 | `DEFAULT_COLLATION` → `utf8mb4_uca1400_ai_ci`; MariaDB ≥ 10.10 | CLOSED |
| 2026-06-04b | Zenical migration impl. | `zensical.toml` 634L; CI/CD; instrucciones IA; rama `migrate/zenical-pure` lista | CLOSED |
| 2026-06-05 | Bootstrap IA cross-project | `.github/prompts/bootstrap_ai_config.prompt.md`; modelo PULL; 5 plataformas; commit `cd22520` | CLOSED |
| 2026-06-05b | `--verify-tools` + `--verify-build` | Modificadores Documentation Generator; `docs/doc_verification_guide.md` | CLOSED |

---

## FASE 5 — Reglas de dependencia y capas (Sep 2026) → ACTIVAS

| Fecha | Sesión | Cambio principal | Estado |
|-------|--------|-----------------|--------|
| 2026-09-21 | Regla #6: capas estrictas y ciclo `connection`⇄`factory` | Ciclo eliminado reescribiendo `UpdateAutoIncrement` (`Engine`, Inspector; commit `92e6c7c`); Regla #6 con 7 capas (`LAYER` como fuente única) y guarda `test_architecture_import_rules.py`; `metadata`/`analysis`/`doc` dependen de Protocols y solo el `__init__` raíz importa `managers`; capas sin commitear | IN_PROGRESS |
| 2026-09-23 | Performance audit de `bulk/` | Solo lectura con benchmarks SQLite 1K–1M; veredicto SIGNIFICATIVO; P-05 DELETE SQL Server >2100 parámetros (hotfix pendiente), vía MySQL multi-fila 8× más lenta que PyMySQL nativo, fast_executemany inefectivo en INSERT MSSQL, normalización = 62 % del INSERT | CLOSED |
| 2026-09-24 | Banco de pruebas bulk (Fase 0) | `scripts/bench_bulk.py` + `docker-compose.bench.yml` + tests de integración por motor (P-05 como xfail estricto); línea base con 6 motores reales (P-02 ~2× y P-04 confirmados; nuevo P-17 SQL Server+pymssql) | CLOSED |
| 2026-09-24 | Hotfix P-18 + P-01 (SQL Server + pyodbc) | fast_executemany vía dialecto en lugar de listener: UPDATE con DATETIME corregido e INSERT ~12× | CLOSED |
| 2026-09-24 | Hotfix P-05 (DELETE en SQL Server) | Troceo ≤ 2000 parámetros y PK compuesta sin constructor de fila; DELETE 1M con pyodbc en 8,9 s | CLOSED |
| 2026-09-24 | Refactor P-02 (INSERT MySQL/MariaDB + PyMySQL) | executemany del driver sin tipos: ~2,1× con valores idénticos; nuevo P-19 (UPDATE corrompe JSON) | CLOSED |
| 2026-09-24 | Hotfix P-19 (JSON serializado dos veces) | Columnas JSON enlazadas sin procesador: UPDATE PG/MySQL/SQLite e INSERT SQLite corregidos; nuevo P-20 (generar_sql con JSON) | CLOSED |
| 2026-09-24 | Hotfix P-22 (filas en la tabla equivocada, MySQL/MariaDB) | Clave de caché de plantillas con la tabla; nuevo P-21 (UPDATE BLOB UTF-8) | CLOSED |
| 2026-09-24 | Feature P-04 (UPDATE vía tabla temporal, MySQL/MariaDB) | `update_via_staging=True` por defecto: ~12,5× con estado final idéntico | CLOSED |
| 2026-09-24 | Fallback `update_via_staging` + hotfix P-21 (binarios UTF-8) | Sin privilegio → UPDATE fila a fila con WARNING; bytes UTF-8 intactos en columnas binarias (6 motores) | CLOSED |
| 2026-09-24 | Refactor P-03 (preparación por columnas) | Resultado idéntico; preparación 2,9× (~5,6 s menos por millón de filas en todos los motores) | CLOSED |
| 2026-09-24 | P-17 descartada (pymssql `bulk_copy`) | No aplica CHECK/FK; se recomienda pyodbc + ODBC 17/18 con un INFO en el log | CLOSED |
| 2026-09-24 | Hotfix P-20 (generar_sql con JSON) | JSON como literal de cadena; nuevo P-23 (`%` duplicados en el SQL generado) | CLOSED |
| 2026-09-24 | Hotfix P-23 (`%` en el SQL generado) | Duplicación deshecha en PostgreSQL y MySQL/MariaDB; nuevo P-24 (generar_sql con Oracle por service_name) | CLOSED |
| 2026-09-24 | Hotfix P-24 (nombre del fichero de generar_sql) | Oracle por service_name y SQLite con ruta absoluta corregidos | CLOSED |
| 2026-09-24 | Cierre de versión v0.12.0 | CHANGELOG `[0.12.0]` + `pyproject.toml`; checklist verde (4558 passed / 68 skipped, build 0.12.0) | CLOSED |
| 2026-09-24 | Refactor P-09 + copia superficial | UPDATE solo con PK + columnas actualizables (3,1×); nuevos P-25 y P-26 | CLOSED |
| 2026-09-24 | Hotfix P-25 + P-26 | Alias de PK sin colisión; DELETE dentro de `bulk_session`; nuevo P-27 CRÍTICA (PostgreSQL + `commit_every_n_chunks`) | CLOSED |
| 2026-09-24 | Hotfix P-27 (PostgreSQL + `commit_every_n_chunks`) | Transacción iniciada antes del cursor del driver: 0/10 → 10/10 filas (psycopg 3 y psycopg2); nuevo P-28 | CLOSED |
| 2026-09-24 | Hotfix P-28 (errores del driver en PostgreSQL) | `IntegrityError`/`OperationalError` de SQLAlchemy; `ParallelBulkLoader` anota el error de la partición en lugar de abortar | CLOSED |
| 2026-09-24 | Hotfix P-13 (límite de parámetros) | INSERT multi-fila y DELETE troceados a ≤ 65.535 parámetros (MariaDB + conector `mariadb`) | CLOSED |
| 2026-09-24 | P-10 (DELETE de PostgreSQL por arrays) | `ANY` / `unnest`: 2,3–2,8× con psycopg 3 y 24–27× con psycopg2 | CLOSED |
| 2026-09-24 | P-06 (`generar_sql` por plantilla) + fix P-29 | 17–50× con salida idéntica; sin RETURNING/OUTPUT en el INSERT generado; `%(nombre)s` conservado | CLOSED |
| 2026-09-24 | P-07 (por bloques) | Memoria adicional con 200K filas 70–176 MB → 4–7 MB, mismo tiempo | CLOSED |
| 2026-09-24 | P-08 descartado | Coste por partición < 2%; escalado 1,6–3,9× con 4 hilos (SQLite no escala) | CLOSED |
| 2026-09-24 | Hotfix loader + paquete de tests | `partition_errors` recoge cualquier excepción; `metadata/__init__.py` deja de tapar el driver `mariadb` | CLOSED |
| 2026-09-24 | Cierre de versión v0.13.0 | CHANGELOG `[0.13.0]` + `pyproject.toml`; checklist verde (4727 passed / 164 skipped, build 0.13.0, integración 162/24) | CLOSED |
| 2026-09-24 | Independencia de los contenedores del banco | Puertos en `127.0.0.1` y configurables; base `bench` en SQL Server; plantillas de URLs; fixtures de `localhost:5432` eliminadas; `postgres_db` intacto | CLOSED |
| 2026-09-24 | Saltos y aviso de la suite | Aviso (`__del__` de Oracle) y test de `matplotlib` corregidos; sin saltos "no aplica"; MariaDB `bench` con permisos `zz_util_bbdd_*`; 0 avisos; con URLs 0 saltos y 0 errores | CLOSED |
| 2026-09-24 | Avisos de `mkdocs --strict` | Referencias a `INSTALLATION.md`/`ROADMAP.md` con el nombre exacto; mkdocs y zensical estrictos limpios; test de enlaces | CLOSED |
| 2026-09-24 | audit_code de bulk + hotfix 1–3 | `chunk_size` validado; `maintenance_scope` no oculta errores y restaura con `commit_every_n_chunks`; loader sin conexión retenida; 4–8 pendientes | CLOSED |
| 2026-09-24 | Hotfix hallazgos 4–8 (+9) | Loader con tabla reflejada; `pk_sync` en PostgreSQL/Oracle (Oracle nunca funcionaba); nombre de fichero saneado; DELETE con `commit_every_n_chunks`; `DISABLE KEYS` solo MyISAM/Aria | CLOSED |
| 2026-09-25 | Cierre de versión v0.14.0 | CHANGELOG `[0.14.0]` + `pyproject.toml`; checklist verde (4783/160, con URLs 4943/0, build 0.14.0, docs estrictas sin avisos) | CLOSED |
| 2026-09-25 | Serialización SQL (P-31 a P-34) | `generar_sql` ~2,5× más rápido con el mismo SQL: 1M filas INSERT 12,6 → 4,9 s; P-35 descartado tras medir | CLOSED |
| 2026-09-25 | Hotfix literales binarios (C-1/P-30) | Literal hexadecimal por motor; Oracle corrompía `b"abc"` sin avisar; 9/9 en los 6 motores | CLOSED |
| 2026-09-25 | Cierre de versión v0.15.0 | CHANGELOG `[0.15.0]` + `pyproject.toml`; checklist verde (4938/165, build 0.15.0, docs estrictas sin avisos); tag `v0.15.0` | CLOSED |
| 2026-09-25 | Auditoría delta de `dump` + banco real | `scripts/bench_dump.py` real; línea base v0.15.0 en 6 motores; PD-01…PD-09 abiertos | CLOSED |
| 2026-09-25/26 | Hotfixes PD-01…PD-12 | 12 fallos de `dump`/`bulk` corregidos y verificados en servidores reales | CLOSED |
| 2026-09-26 | Fase 1 de rendimiento (Q1–Q4) | Oracle `arraysize` −29 %; cursor de servidor (memoria −60/−81 %); solape lectura/escritura −15/−29 %; guía de rangos | CLOSED |
| 2026-09-26 | MariaDB Connector/Python (PF-09) | `executemany` del driver con tipos uniformes: `dump` 80 → 29 s | CLOSED |
| 2026-09-26 | Fase 2 (Q5, Q6, 2.3) + 3.4 | `write_batch_size` (PG −22 %); guía `manage_indexes`; aviso LOB; resumen de auditoría incremental; Q9 replanteado | CLOSED |
| 2026-09-26 | Cierre de versión v0.16.0 | CHANGELOG `[0.16.0]` + `pyproject.toml`; checklist verde (5054/165; integración 303/0; build 0.16.0; docs estrictas); tag `v0.16.0` | CLOSED |
| 2026-09-26 | Tests de integración de `dump` | 28 tests contra 5 servidores (origen PostgreSQL); 17 fallan con v0.15.0; hallazgo PD-13 | CLOSED |
| 2026-09-26 | Hotfix PD-13 + audit-code + A1–A3 | DECIMAL exacto con pymssql; auditoría independiente (APROBADO CON CONDICIONES) y sus 3 hallazgos corregidos | CLOSED |
| 2026-09-26 | Cierre de versión v0.16.1 | CHANGELOG `[0.16.1]` + `pyproject.toml`; checklist verde (5067/193; integración 331/0; build 0.16.1); tag `v0.16.1` | CLOSED |
| 2026-09-26 | Q8: medición de la etapa pandas | Cota de la ruta sin pandas ≈ 1,7–2,0 s por 3,5M filas (PG ≈ 15 %, resto 3–7 %); aparcado | CLOSED |
| 2026-09-26 | Q9: FK por esquema en SQL Server | `sys.foreign_keys` en una consulta para el orden de carga y la limpieza; 200 tablas 33,9 → 15,8 s; SQL en `metadata/sqlserver` | CLOSED |
| 2026-09-26 | Q9b: reflexión sin FK | `BulkCrud(reflect_foreign_keys=False)` en dump (SQL Server 32 → 16 ms/tabla); 200 tablas 15,8 → 14,3 s (−58 % vs v0.16.1) | CLOSED |
| 2026-09-26 | 3.3: Oracle APPEND_VALUES | Descartada: +20 % sin commit por lote; con commit por lote las tablas crecen 10–127× | CLOSED |
| 2026-09-26 | Cierre de versión v0.17.0 | CHANGELOG `[0.17.0]` + `pyproject.toml`; checklist verde (5079/199; integración 338/0; build 0.17.0); enlaces de CONSTRAINTS_AUDIT_INDEX corregidos; tag `v0.17.0` | CLOSED |
| 2026-09-26 | Refactor de reutilización bulk/dump + fix DumpConfig | R1–R10 sin cambios funcionales (código movido idéntico por AST, sabotaje por punto de uso); `DumpConfig` valida antes de vaciar el destino | CLOSED |
| 2026-09-26 | Cierre de versión v0.17.1 | CHANGELOG `[0.17.1]` + `pyproject.toml`; checklist verde (5089/199; integración 338/0; build 0.17.1); `[Unreleased]` históricos corregidos; tag `v0.17.1` | CLOSED |
| 2026-09-26 | Cierre de versión v0.17.2 | R11, R12, R14 sin cambios funcionales; fix de `rows_committed`; checklist verde (5095/199; integración 338/0; build 0.17.2); tag `v0.17.2` | CLOSED |
| 2026-09-27 | Cierre de versión v0.17.3 | R15 y R16 sin cambios funcionales; plan de reutilización de bulk/dump completo; checklist verde (5095/199; integración 338/0; build 0.17.3); tag `v0.17.3` | CLOSED |
| 2026-09-27 | Pendientes de bulk/dump → v0.17.4 y v0.18.0 | fix de `rows_committed` con DELETE en la sesión; regla de pool `size + max_overflow` con una conexión por worker; `rows_committed` con DELETE; `AuditError` bajo `DatabaseException`; `BulkInserter` retirado (incompatible) | CLOSED |
| 2026-09-28 | Exportación de informes → v0.18.3 | El Excel de `dump` no se generaba: CSV de auditoría re-guardado fuera de la librería (líneas entre comillas) → `KeyError 'timestamp'` tras la carga. Resumen tolerante, `DumpReportError.result`, CSV con cabecera no válida apartado, lock del CSV sin `resolve()` (perdía filas en Windows), `_core/export_safety` en los informes Excel y Word; checklist verde (5288/199) | CLOSED |
| 2026-09-28 | Revisión de la configuración IA | Commands finos sobre prompts gemelos, `/performance-audit-constraints`, tipos de commit ampliados, `DOCUMENTATION_STANDARD` canónico, `applyTo` sobre rutas reales, `.claude/settings.json` versionado; 12 ficheros retirados | CLOSED |
| 2026-09-29 | Revisión de documentación y hotfixes → v0.18.4 | README al día; `docs/` a minúsculas con guion bajo; Pages roto desde `11fb9f8` (deploy sin build); ZIP offline de Releases sin `start-server.py`; `docs-zip-release.yml` nunca ejecutado por YAML inválido; checklist verde (5295/199) | CLOSED |
| 2026-09-29 | Motor MySQL propio + hotfixes → v0.19.0 | `mysql` con PyMySQL/aiomysql (MariaDB ya usaba Connector/Python en sync); adapters por registro; `migrate` 20 pares; 6 defectos previos hallados al probar contra servidores reales (incl. pool PostgreSQL sin `sslmode`); checklist verde (5483/205, integración 344) | CLOSED |
| 2026-09-30 | Vistas de migrate + auditoría de migrate → v0.20.0 | Vistas reescritas con sqlglot (V0 spike → V1–V4, `validate_views`, `CONNECT BY` → CTE); auditoría de `migrate/` contra el banco: `execute()` solo funcionaba hacia MySQL (A1) y 8 defectos más del DDL (A2–A9, B1), todos con test-first en el e2e de 20 pares; plan de deuda D1–D3 para 0.21.0 | `2026-09-29c-migrate-views`, `2026-09-29d-migrate-audit` |
| 2026-09-30 | Deuda de migrate + auditoría → v0.21.0 | D1 extractores por schema (823 → 8 consultas; destapó un producto cartesiano en las FK compuestas de Oracle → hotfix); D2 `oracle_type` → `source_type` + `category` (corte directo con guía de migración); D3 comentarios desde/hacia PostgreSQL y SQL Server; auditoría de la 0.21.0: comentarios recortados al límite del destino (C1), filas por tabla sin distinguir mayúsculas (H1), tabla sin columnas = ERROR (H2) | `2026-09-30-migrate-d1-extract-batching`, `2026-09-30b`…`2026-09-30d` |
| 2026-09-30 | Deuda de la 0.21.0 + auditoría → v0.22.0 | E3 `CONNECT BY` (`AND LEVEL <= n`, `CONNECT_BY_ISLEAF`, `NOCYCLE` hacia PostgreSQL con array de antepasados, comparado con Oracle); E2 comentarios de vistas; E1 `MigrationWarning.code`; auditoría: `NOCYCLE` con claves VARCHAR/NUMERIC (C1) y NULL (C2), `SELECT *` en jerarquías (H1), emisión idempotente (L1), guardián de códigos (L2) | `2026-09-30e`…`2026-09-30h` |
| 2026-10-01 | Deuda de la 0.22.0 → v0.23.0 | F2 `CONNECT_BY_ISCYCLE` (semántica medida en Oracle); F3 `NOCYCLE` hacia MySQL/MariaDB/SQL Server con `_KeyPath` por destino y búsqueda binaria; F1 `ORDER SIBLINGS BY` (CTE de hermanos + `cb_order`); F4 comentarios de rutinas; hotfix `exp.Expr`; R4 (rutinas no ejecutables) confirmado y pendiente | `2026-10-01-migrate-connect-by-3`, `2026-10-01b`, `2026-10-01c` |
| 2026-10-01 | Hotfixes → v0.23.1 | R4: rutinas en `execute()` (`CREATE` reconstruido en MySQL/MariaDB, nombre y `CREATE OR REPLACE` en Oracle, rutinas de otro dialecto comentadas); firma de `on_post_build` del plugin ZIP; rutinas de Oracle con nombre y owner en los adaptadores de metadatos; MySQL del banco con `--log-bin-trust-function-creators=1` | `2026-10-01d`…`2026-10-01f` |
| 2026-10-01 | Performance-audit de bulk → v0.24.0 | Auditoría por objetivos (1M filas, 6 motores; SIGNIFICATIVO) e implementación de las Fases 0–2: UPDATE PG por staging 2,4×, DELETE SQL Server con OPENJSON 3,4× (10K 20×), INSERT por tuplas, nota de lote en errores, reintentos por código + backoff, `*_from_chunks`, checkpoints y reanudación, `ParallelBulkLoader.update/delete`; deadlock InnoDB en DELETE paralelo → 2 reintentos mínimos | `2026-10-01h` |
| 2026-10-01 | B-04, audit-code y hotfix → v0.25.0 | Lote por motor y operación (`chunk_size=None`: PG INSERT −15 %, DELETE −11 %, SQL Server DELETE −20 %; tope de 5000 en `DELETE … IN` de MySQL/MariaDB); audit-code de Fases 0–2 + B-04 RECHAZADO por A1 (OPENJSON borraba filas no pedidas con claves fuera del tipo de la PK, en la 0.24.0) y A2 (lock wait de `mariadb` sin reintento) → hotfix con test-first | `2026-10-01i`, `2026-10-01j` |
| 2026-10-02 | rejects_scope y audit-code de isolate → v0.28.0 | Deuda «`_tag_rejects` privado usado por el loader» → `BulkCrud.rejects_scope`; al analizarlo, bug de la 0.27.0 con `disable_constraints` (posición y `max_rejects` por chunk); audit-code de `isolate` de extremo a extremo: B-1 a B-4 + dos abiertos de la 0.27.0 | `2026-10-02`, `2026-10-02b` |
| 2026-10-02 | Módulo de auditoría centralizado → v0.29.0 | Prompt `audit_module` + inventario `INV-*` de la auditoría de `bulk`/`dump`/`migrate`; paquete `util_bbdd.audit` (capa 3, ADR-002) en fases F0–F5 con CSV congelado byte a byte; `/audit-code` (APROBADO CON CONDICIONES, 4 hallazgos corregidos) y endurecimiento de la construcción de eventos en los 4 emisores | `2026-10-02c`, `2026-10-02d` |
| 2026-10-03 | Auditoría de `comparar` → v0.30.0 | `/audit-code` de `comparar` (RECHAZADO: routines, mayúsculas entre motores, SQL inválido e inyectable) y tres entregas: fix B1–B7/S1, perf con `get_multi_*` y consultas por schema (PG ×28, Oracle ×20, SQL Server ×14), refactor (`_ddl.py`, SQL a `metadata`, tipos); FKs e índices con nombre generado; hotfix de `fetch_routines_sql` (agregados); `scripts/bench_compare.py` | `2026-10-02g` |
| 2026-10-03 | Centralización de metadatos → v0.31.0 | `/metadata-centralization` (PLAN/AUDIT_PLAN, ADR-003) e IMPLEMENT por grupos: hotfixes H-10/H-17, `CatalogSource`/`SchemaSnapshot` y `CatalogDialect` de 6 motores, consumidores migrados (C1–C5, D1–D2, E1), `get_*` tipados y retirada de registry, adaptadores, cachés y Redshift/Snowflake (E2a–E2d), trinquete a cero (G2), ADR publicado (H); `/audit-code` APROBADO CON CONDICIONES → F1/F2 corregidos | `2026-10-03-metadata-centralization` |
| 2026-10-01 | MariaDB Connector/Python y audit-code → v0.27.1 | El driver por defecto de la librería para MariaDB no se probaba (banco con PyMySQL): motor `mariadb_connector` en la integración y el banco (INSERT 1,9×, UPDATE 1,67×); ORA-03106 reproducido en 3 versiones de oracledb; audit-code de la 0.27.0: M-1 conciliación, B-1, B-2 | `2026-10-01v` a `2026-10-01z` |
| 2026-10-01 | Pendientes de bulk → v0.27.0 | Escalado de `ParallelBulkLoader` re-medido (la guía daba 2,6× en PostgreSQL de antes de B-03/B-04; hoy 1,05×); spike S-5 `batcherrors` (datos idénticos, ORA-03106 en UPDATE con LOB); `isolate` en Oracle por `batcherrors`, en `ParallelBulkLoader` (columna `particion`, sin reintento con rechazos) y en `dump` (tabla `success` con `rows_rejected`) | `2026-10-01p` a `2026-10-01u` |
| 2026-10-01 | Fase 3 de bulk → v0.26.0 | P-1 filtro de OPENJSON por columna (2,47 → 2,17 s); spikes S-1..S-4; `prefetch_blocks` (opt-in); `on_error="isolate"` con CSV de rechazos (opt-in); audit-code: M-1 (fallo del CSV de rechazos) y B-1/B-3/B-4 (XACT_ABORT ON, sqlite3 `autocommit=True` perdía filas, lock y cabecera del CSV) | `2026-10-01l`, `2026-10-01m`, `2026-10-01n`, `2026-10-01o` |
| 2026-10-01 | Deuda del audit-code → v0.25.1 | A3: `*_from_chunks` dentro de un `bulk_session` abierto → `RuntimeError`; A4: nota del COMMIT periódico fallido sin culpar al lote; A5: `__batch_note` tipado; test-first | `2026-10-01k` |
| 2026-10-08 | FASE 1 de `drivers-connections-audit` (sin bump; v0.35.4) | `/audit-code` de connection/metadata/_drivers/managers RECHAZADO: S1 URLs de engine sin escapar (redirección de host reproducida), B1 lista blanca JSON rechaza `oracle_thick_mode`/`close_timeout`/…, B2 thick mode Oracle muerto, S4 camino SQLAlchemy sin TLS/charset, T1 tests rojos; skill corregida a v1.0.3 (10 premisas refutadas); campos de versión sincronizados a 0.35.4 | `2026-10-08-drivers-connections-audit-fase1` |
| 2026-10-08 | Hotfix P0 de drivers → v0.35.5 | S1 credenciales escapadas con `URL.create`; S4 Engine con `creator`/`async_creator` sobre `ConnectionFactory` (+ `found_rows` para no perder `CLIENT.FOUND_ROWS`); B1 lista blanca JSON alineada con `*Config` (+ guardián); B2 thick mode Oracle; T1 charset CLEAN con servidor latin1 (decisión del usuario); suite 5201 passed, integración 551 passed + 1 fallo Oracle preexistente | `2026-10-08b-hotfix-drivers-p0` |
| 2026-10-08 | P1 de drivers → v0.35.6 | Y3 TLS aiomysql (`SSLContext`) + bug sync `ssl_verify_*`; Q1 `encryption` en pymssql con verificación fail-closed (FreeTDS de Windows no cifra); bug CNX-02 `Server={host},puerto` (pyodbc/aioodbc no conectaban desde v0.11.0) y `Encrypt=yes/no`; Y2/M3 charset adaptativo con pool MySQL y en async; M1 `SET NAMES <charset>`; P1 extra `postgresql`; suite 5231 passed, integración 552 passed | `2026-10-08c-fix-drivers-p1` |
| 2026-10-08 | P2 de drivers → v0.35.7 | Regresión M1 de v0.35.6 revertida (Connector/Python solo admite utf8mb4: `charset="latin1"` no conectaba); `encoding_errors` obsoleto (ningún driver lo admite: nunca se aplicó); sync ya no envía `charset`/`encoding_errors` (2 reintentos y 2 WARNING por conexión); S3 `password` fuera de `repr`; G1 Engine cacheado por manager; suite 5246 passed, integración 552 passed | `2026-10-08d-fix-drivers-p2` |
| 2026-10-08 | Resto de P2 de drivers → v0.35.8 | `close()` sin ejecutor ya no lanza (bloque pegado desde v0.6.6); G2 errores de pool visibles; H1 firma de `jaydebeapi.connect` corregida (HSQLDB nativo no funcionaba) + `connection_properties`; H2 Engine HSQLDB con error claro; O2 `protocol=tcps` en Oracle (`_dsn.py` único); P2–P6 asyncpg `sslmode`/`timeout`, `schema` validado, IPv6, `PoolTimeoutError`; Q2 pool SQL Server sin lock al conectar; L1, M5–M7; suite 5281 passed, integración 552 passed | `2026-10-08e-fix-drivers-p2b` |
| 2026-10-09 | Hotfix advisor/dispose → v0.40.1 (`2026-10-09h-hotfix-advisor-dispose`) | `/audit-code` de un log de `pruebas_util`: el advisor no es lento (9–12 ms; el minuto es el INSERT de 1M); H1 el informe de MariaDB/MySQL ya no da por buenos `autocommit`/timeouts no leídos; H2 `dispose(close=False)` del Engine sync en la finalización del intérprete | CLOSED |
| 2026-10-09 | Hotfix init_command → v0.40.2 (`2026-10-09i-hotfix-init-command`) | `/audit-code` de un traceback de `pruebas_util`: `init_command` con dos sentencias (límite del servidor, no regresión); F2 `ValidationError` al validar `conn_params`; F1 `DatabaseConfigurationError` con `db_type` en su sitio; guía § 6 | CLOSED |
| 2026-10-09 | Hotfix reset del pool MariaDB → v0.40.3 (`2026-10-09j-hotfix-pool-reset`) | Log de `pruebas_util`: documentación MariaDB con `use_pool=True` falla con `SystemError … fetchrows`; RCA: `mariadb.ConnectionPool` reinicia la sesión (latin1 del servidor) sin repetir `init_command`; fix: reaplicarlo en cada `get_connection()` | CLOSED |
| 2026-10-09 | Auditoría de arquitectura de `doc/` + `analysis/` → v0.41.0 (`2026-10-09k-doc-architecture-audit`) | 26 hallazgos; diagramas Graphviz por lotes (`dot -O`: el coste es arrancar `dot`), un generador por documentación (B-02), almacenamiento declarativo (B-01), API de `util_bbdd.doc` reducida con `DocumentationConfigError`/`DocumentationRenderError`; cobertura 61 % → 81 %. Plan de pendientes en `2026-10-09l-plan-pendientes-doc` |
| 2026-10-10 | Pendientes de la auditoría de `doc/` → v0.41.1 (`2026-10-09l-plan-pendientes-doc`) | B-04 DDL de HSQLDB (`LISTAGG` sin `WITHIN GROUP`, rama de vistas con columna inexistente, relleno `CHAR`); S-02 entidades en el DDL de HTML (ningún motor las devuelve); orden total del inventario; docstrings con `DatabaseConnectionError` |
| 2026-10-10 | Plan de pendientes global → v0.41.2 (`2026-10-10-plan-pendientes-global`) | H1 confirmado con sondas y corregido (lecturas de catálogo sin fin de transacción: PostgreSQL `idle in transaction`, MySQL con metadatos obsoletos); H2 no reproducido; P5–P7 de doc publicados |
| 2026-10-10 | Plan de pendientes global, Q3 → v0.41.3 (`2026-10-10-plan-pendientes-global`) | F3/F4 confirmados en SQL Server (PK/FK vacías para tablas inexistentes; mezcla de `Users`/`users` con collation CS) y corregidos; F5 (`clear_cache` dirigido con usuario Oracle entrecomillado) corregido; H2 fijado con test |
| 2026-10-10 | Plan de pendientes global, Q4–Q5 → v0.42.0 (`2026-10-10-plan-pendientes-global`) | CI de integración (PostgreSQL/MySQL/MariaDB, manual y nocturno; simulado en local); DDL de HSQLDB con PK; `routine_parameters` indexado (0,91 s → 0,003 s con 2000 routines) |
| 2026-10-10 | `/audit-code` de v0.41.2–v0.42.0 → v0.42.1 (`2026-10-10-plan-pendientes-global`) | APROBADO CON CONDICIONES → resueltas: CI con MariaDB Connector/C y `skip_reason()`; H1 en SQL Server fijado con tests (`@@TRANCOUNT` = 1 desde que conectan pymssql/pyodbc/aioodbc); 12 tests unitarios que fallaban sin el banco |
| 2026-10-10 | API pública 1.0, fase 0.43.0 → v0.43.0 (`2026-10-10-api-1-0`) | Raíz de 56 a 13 símbolos con carga perezosa (`import util_bbdd` ~1,1 s → ~0,3 s); `util_bbdd.exceptions` público; 46 alias con `DeprecationWarning`; `init`/`release_connection` en ambos managers; guía `docs/guides/api_1_0_migration.md` |
| 2026-10-10 | Módulo público de las excepciones → v0.44.0 (`2026-10-10-exceptions-module-name`) | `__module__ = "util_bbdd.exceptions"` en las 40 excepciones (trazas, logs, pickle); pickle de v0.43.0 sigue cargando (test con bytes reales del tag) |
| 2026-10-10 | API 1.0 final → v1.0.0 (`2026-10-10-api-1-0-final`) | 46 alias de la raíz y `close_connection()` retirados; README reescrito; instalación, drivers PostgreSQL, extra `doc` inexistente, `SchemaDiffReporter` y métodos inexistentes corregidos en docs; cobertura 91 % |
| 2026-10-10 | Pendientes tras 1.0 → v1.1.0 (`2026-10-10-plan-pendientes-post-1-0`) | `main` en v1.0.0; rutas `str` en `bulk`/`dump` (`output_dir` como `str` perdía el `DumpResult`); hotfix: consultas async de PostgreSQL (asyncpg) rotas desde v0.5.6, filas de pyodbc anidadas desde v0.5.0 y pool async de SQL Server sin `driver_name`; `BulkCrud` 1943 → 1564 líneas (`TableMaintenance`, `RejectsCoordinator`); 340 → 0 `ResourceWarning` con `--cov`; guías de rendimiento/constraints/migrate revisadas; `doc_agents.yml` retirado |
| 2026-10-10 / 11 | Revisión de docs nivel 2 + 2 hotfix de `doc` → v1.1.1 (`2026-10-10-docs-review-nivel-2`, `2026-10-11-hotfix-doc-auto-filename`, `2026-10-11-hotfix-doc-render-error`) | 82 páginas revisadas contra el código (2 consolidadas; 17 ejemplos ejecutados, SQLite y banco); `doc`: nombre de salida sin caracteres prohibidos en Windows y `DocumentationRenderError` al preparar la salida; `PoolExhaustedError`/`DiffReportGenerationError` reservadas (retirada en 2.0.0) | CLOSED |
| 2026-10-14 | Reactivación de constraints, retirada de excepciones reservadas y validadores del advisor → v1.2.0, v2.0.0, v2.1.0 (`2026-10-14-dump-constraint-reactivation`, `2026-10-14-remove-reserved-exceptions`) | `DumpResult.constraint_reactivation_error` y su hoja; MAJOR 2.0.0 sin `PoolExhaustedError`/`DiffReportGenerationError`; 9 validadores de rendimiento | CLOSED |
| 2026-10-15 / 16 | Condiciones del motor + audit-code v1.0.0→v2.1.0 + tech-debt + T-06 → v2.2.0 (`2026-10-15-engine-conditions-doc`, `2026-10-15-engine-readiness-audit-sheets`, `2026-10-15-refactor-doc-readiness`, `2026-10-15b-audit-code-v1.0.0-v2.1.0`, `2026-10-16-refactor-advisor-strategy`) | Sección/hojas «Condiciones del motor»; audit-code APROBADO CON CONDICIONES (A-01/A-02/A-04/D-01 hotfix; A-05/A-07 decididas); deuda T-01–T-11 cerrada; advisor como Strategy (732 → 501 líneas) con caracterización de 205 casos; SQL Server del banco en 51833 | CLOSED |
| 2026-10-16 | Riesgos residuales del advisor de MySQL → v2.2.1 (`2026-10-16b-fix-mysql-redo-variables`) | `read_variables` con `WHERE Variable_name =` y filas inesperadas omitidas; MySQL 8.0.30+ evaluado con `innodb_redo_log_capacity` (banco: 48 MB ignorados → 100 MB reales) | CLOSED |
| 2026-10-16 | Avisos de SonarLint y Pylance → v2.2.2 (`2026-10-16c-sonarlint-cleanup`) | ~35 avisos en `analysis`, `bulk`, `comparar`, `connection`, `factory`, `metadata`, `migrate`; `_connect_by_hierarchy` (complejidad 81) y `_transpile_view` divididas con comparación antes/después (1086 casos, 0 diferencias); `logger.exception` en las 14 conexiones | CLOSED |

> Las sesiones del 2026-06-07 al 2026-06-16 (documentación) constan en `INDEX.md`; este digest no las recoge.

---

## Notas

- **Total sesiones archivadas** en `doc_old/sessions/`: ~65 sesiones (Mar-04 a May-28).
- **Total sesiones activas**: 21 sesiones (May-31 a Jun-05).
- **Test suite**: creció de ~1800 (Abr) → 3826 (Jun-05) → 3859 passed / 4 skipped (Sep-22).
- **Versiones**: v0.6.0 (Mar) → v0.6.7 → v0.6.8 (logging) → v0.6.9 → v0.8.0 → v0.9.0 (Jun-01c) → v0.10.0 (Jun-01d).
