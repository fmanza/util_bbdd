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

> Las sesiones del 2026-06-07 al 2026-06-16 (documentación) constan en `INDEX.md`; este digest no las recoge.

---

## Notas

- **Total sesiones archivadas** en `doc_old/sessions/`: ~65 sesiones (Mar-04 a May-28).
- **Total sesiones activas**: 21 sesiones (May-31 a Jun-05).
- **Test suite**: creció de ~1800 (Abr) → 3826 (Jun-05) → 3859 passed / 4 skipped (Sep-22).
- **Versiones**: v0.6.0 (Mar) → v0.6.7 → v0.6.8 (logging) → v0.6.9 → v0.8.0 → v0.9.0 (Jun-01c) → v0.10.0 (Jun-01d).
