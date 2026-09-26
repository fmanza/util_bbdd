# CURRENT STATE — util_bbdd

**Generado**: 2026-06-05 (cabecera, tabla de versiones y tests actualizados el 2026-09-26 en el cierre de `v0.17.2`)  
**Fuente**: Sesiones activas Mayo-31–Junio-05 + docs Zenical; `CHANGELOG.md` para `v0.11.0` a `v0.17.2`  
**Versión**: `v0.17.2` (cerrada en `develop`, 2026-09-26; `develop` y el tag publicados en `origin`). Tag de git: `v0.17.2`  
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
| Zenical | Pendiente, sin versión asignada — merge `migrate/zenical-pure` (+80% perf doc builds) cuando Zenical esté instalable |

PR abierta: **PR #18** `feat(connection/bulk): automatización variables MySQL/MariaDB` — revisión pendiente de merge.  
PR en espera: **PR #19** `migrate/zenical-pure` — bloqueada hasta que Zenical v0.0.44 esté en crates.io (o instalación manual de binario).

**Tests actuales**: 5095 passed / 199 skipped sin URLs de servidor (todos los saltos son servidores sin URL); con las URLs del banco (`scripts/bench_env.example.*`), `tests/integration`: 338 passed, 0 skipped en 5 servidores (cierre de `v0.17.2`, 2026-09-26). Banco de rendimiento de `dump`: `scripts/bench_dump.py` (ver `docs/PERFORMANCE_AUDIT_GUIDE.md`).

---

## Trabajo activo (sesiones más recientes)

### Documentación y estándares IA (2026-06-03 a 2026-06-05)
- **Estándar documental v2** implementado: 5 arquetipos × 5 secciones, 7 secciones nav MkDocs, enlace bidireccional api↔examples, autodoc Bulk+Dump corregidos. (`2026-06-03-docs-standard-v2`)
- **`--verify-tools`** (consulta webs oficiales) y **`--verify-build`** (build local + lectura `site/` o `localhost:8000`) incorporados como modificadores del agente Documentation Generator. Guía pública: `docs/doc_verification_guide.md`. (`2026-06-05-verify-docs`)
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

1. **Merge PR #18** (`MySQLVariableValidator`) tras review. Potencial tag `v0.10.1`.
2. **Zenical opción A** (decisión del usuario): descargar binario, validar `zensical build`, merge `migrate/zenical-pure`, tag `v0.11.0`.
3. **FASE 5 doc estándar** (criterios de aceptación): pendiente validación QA — no rellenar `## 4. Criterios de Aceptación` en `docs/functional/*.md` hasta esa sesión.
4. **Push commit `cd22520`** (bootstrap IA) o PR a main — pendiente decisión del usuario.

---

## Motores soportados

| Motor | Como fuente | Como destino | Notas |
|-------|-------------|--------------|-------|
| Oracle | ✅ | ✅ | SEQUENCE+TRIGGER; identity mode opcional |
| MariaDB | ✅ | ✅ | Default collation: `utf8mb4_uca1400_ai_ci` (≥10.10) |
| MySQL | — | ✅ | Comparte estrategia con MariaDB |
| PostgreSQL | ✅ | ✅ | SERIAL/BIGSERIAL/SMALLSERIAL; `PostgresCopyStrategy` |
| SQL Server | ✅ | ✅ | IDENTITY(1,1); `fast_executemany` |
| SQLite | — | ✅ | |
| HSQLDB | — | ✅ | |

**Matriz migrate/** completada: 4 fuentes × 3 destinos = 12 flujos DDL validados.

---

## Calidad actual

Medido el 2026-09-26 (sesión `2026-09-26ze-code-reusability-bulk-dump`):

- **Lint**: `ruff check src tests` → 0 errores
- **Tipos**: `mypy src tests/unit/test_protocol_conformance.py` → 0 errores (356 source files)
- **Tests**: 5095 passed / 199 skipped sin URLs de servidor
- **Cobertura de ramas `bulk/` + `dump/`**: 92 % (`coverage run --branch --source=src/util_bbdd/bulk,src/util_bbdd/dump`;
  `pytest --cov` falla con Python 3.14 + numpy al importar el paquete dos veces)
- **Build docs**: `mkdocs build --strict` → 0 errores, 0 warnings
- **Complejidad cognitiva**: reporters ≤ 4, emitter `_topological_sort` → 0 (desglosado en helpers)
