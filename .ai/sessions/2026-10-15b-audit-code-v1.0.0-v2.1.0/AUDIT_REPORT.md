# AUDIT_CODE — util_bbdd v1.0.0 → HEAD (v2.1.0 + Unreleased)

- Fecha: 2026-10-15 · Rama: `develop` · Rango: `v1.0.0` (`d897b69c`) .. `HEAD` (`0c0e6a65`), 64 commits
- Skill: `audit_code` (solo lectura: no se ha editado código) · Foco: todo · Alcance: `src/` + `tests/` + `docs/`
- Evidencia ejecutada: ruff, ruff format, mypy, pytest (shell limpio y con banco), `zensical build --strict`,
  sonda propia (`probe_audit.py`, fuera del repo)

---

## PLAN

### Alcance

| Área | Ficheros | Cambio |
|---|---|---|
| `src/` | 47 | +2268 / −738 |
| `tests/` | 27 | +1865 / −27 |
| `docs/`, `mkdocs.yml`, `README.md`, `.ai/` | ~116 | revisión nivel 2 (v1.1.1) + guías nuevas |

Releases del rango: v1.1.0 (rutas `str`, asyncpg, pyodbc, refactor A5 de `BulkCrud`), v1.1.1 (hotfix `doc`),
v1.2.0 (`DumpResult.constraint_reactivation_error`), v2.0.0 (retirada de 2 excepciones reservadas), v2.1.0
(9 validadores del advisor) y `[Unreleased]` («Condiciones del motor» en `doc`, `bulk` y `dump`).

### Archivos analizados (lectura completa o del diff)

- `connection/`: `performance_advisor.py`, `_advisory.py`, `{mariadb,postgresql,sqlserver,oracle}/_variables.py`,
  `sqlserver/async_pool_connection_sqlserver.py`, `config.py` (`_to_int`/`_to_bool`)
- `audit/`: `readiness.py`, `exporters.py` · `bulk/`: `audit.py`, `crud.py`, `_execution/maintenance.py`,
  `_support/rejects.py`, `_support/validation.py`, `_execution/parallel_loader.py`
- `dump/`: `orchestrator.py`, `reporters.py`, `_models.py`, `_constraints.py`, `_audit_events.py`
- `executors/async_query_executor.py`, `results/normalizer.py`, `managers/sync_mgr.py`, `managers/async_mgr.py`
- `_core/`: `exceptions.py`, `validation/paths.py`, `export_safety.py`, `exceptions.py` (público)
- `doc/`: `application/ports.py`, `use_cases/{engine_conditions,documentation_orchestrator}.py`, `domain/models.py`,
  `database_documentation.py`, `runtime/output_runtime.py`, renderers Word/Excel/HTML, plantillas `detail`/`index`,
  `print_config_manager.py`, adaptador del manager
- Docs: `CHANGELOG.md`, `docs/guides/{performance_readiness_guide,engine_readiness_usage_guide,api_1_0_migration,dump_guide}.md`,
  `docs/api/{dump,dump_reporter,database_documentation}.md`, `docs/roadmap.md`, `.ai/CURRENT_STATE.md`,
  `.ai/sessions/INDEX.md`

---

## AUDIT_PLAN

### Riesgos funcionales

- El volcado puede terminar con las constraints del destino desactivadas y la auditoría estructurada decir `ok` (A-01).
- Recomendaciones del advisor que inducen a error (comandos que no existen o fallan en MySQL/SQL Server) o que
  rebajan la durabilidad (A-04, A-05).
- Traducción de parámetros para asyncpg sin conocer literales SQL (A-02).

### Riesgos técnicos

- Refactors con «sin cambios funcionales» (A5 de `BulkCrud`, `_run_dump`): paridad comprobada con la suite y con un
  diff de líneas movidas; sin incidencias.
- Orden de hojas del Excel de `dump` y contrato «las opcionales al final» (A-03).
- Tipado de `DumpConfig` tras aceptar `str` (A-08).

### Riesgos de seguridad

- Mensajes de error con posibles datos sensibles en Excel/`DumpResult` (A-07, hipótesis).
- Inyección SQL en los nuevos validadores: **descartada** (constantes, lista blanca en `SHOW`, binds en SQL Server
  y Oracle).
- Inyección de fórmulas en las hojas nuevas: **descartada** (`safe_value` + `neutralize_formulas`; `SafeWorkbook`
  neutraliza al guardar). XSS en HTML: **descartada** (autoescape activo en `*.html.j2`).

---

## AUDIT_CODE

### Evidencia ejecutada

| Comprobación | Resultado | Log |
|---|---|---|
| `ruff check src tests` | ✅ sin hallazgos | `build/logs/audit_v1_v2_ruff.txt` |
| `ruff format --check src tests` | ✅ 707 ficheros ya formateados | `build/logs/audit_v1_v2_ruff_format.txt` |
| `mypy src tests/unit/test_protocol_conformance.py` | ✅ 336 ficheros, sin errores | `build/logs/audit_v1_v2_mypy.txt` |
| `pytest` en shell limpio | ✅ 5816 passed, 531 skipped (60,8 s) | `build/logs/audit_v1_v2_pytest_clean.txt` |
| `pytest` con banco (PG, MySQL, MariaDB, Oracle, HSQLDB) | ✅ 6195 passed, 152 skipped, 1 aviso de JPype (191 s) | `build/logs/audit_v1_v2_pytest_bench.txt` |
| `zensical build --strict` | ✅ «No issues found» | `build/logs/audit_v1_v2_docs_build.txt` |

SQL Server **no se pudo validar contra el banco**: `util_bbdd_bench_mssql` no arranca porque el puerto 51433 cae en un
rango excluido por Windows (`netsh … excludedportrange`: 51336–51435). No es un fallo del código; liberar el puerto
requiere permisos de administrador (reiniciar `winnat`) o cambiar `UTIL_BBDD_BENCH_MSSQL_PORT`.

### Hallazgos

Severidad: **Alta** (comportamiento incorrecto con impacto en datos u operación) · **Media** (contrato o información
incorrecta que induce a error) · **Baja** (cosmético, coherencia, deuda). Estado: **Confirmado** (reproducido o
evidente en el código) · **Hipótesis** (requiere verificación adicional).

| ID | Sev. | Estado | Hallazgo |
|---|---|---|---|
| A-01 | Media | Confirmado | El evento `run` de `audit_sink` es `ok` aunque la reactivación de constraints haya fallado |
| A-02 | Media | Confirmado | asyncpg: `:nombre`/`%(nombre)s` dentro de literales SQL se reescriben como `$n` |
| A-03 | Baja | Confirmado | «Errores de Reactivación» rompe la regla «las hojas opcionales al final» y su ancho de columnas |
| A-04 | Media | Confirmado (doc. MySQL/SQL Server) | Recomendaciones del advisor incorrectas: variables no dinámicas y `SET MAXDOP` |
| A-05 | Media | Hipótesis (diseño) | `innodb_flush_log_at_trx_commit=1` (ACID) se marca WARNING y `2` como OK |
| A-06 | Baja | Confirmado | Umbrales y recomendaciones incoherentes en el mismo hallazgo |
| A-07 | Baja | Hipótesis | `reactivation_error = str(exc)` vuelca el mensaje completo del driver al Excel |
| A-08 | Baja | Confirmado | `DumpConfig.output_dir`/`bulk_audit_path`/`rejects_csv_path` quedan tipados `StrPath` |
| A-09 | Baja | Confirmado | Arreglo de casting parcial: PostgreSQL usa `int()`/`bool()` crudos en `check_static` |
| A-10 | Baja | Confirmado | `batch_window_seconds` público sin validar y sin test en `DatabaseDocumentation` |
| A-11 | — | **Descartado** (falso positivo, ver abajo) | Nombre automático de carpeta: nombres reservados de Windows no cubiertos |
| D-01 | Media | Confirmado | `CHANGELOG.md`: `[2.0.0] - Por publicar` con tag `v2.0.0` publicado |
| D-02 | Baja | Confirmado | Sin página de API para `EngineReadinessAdvisor`/`EngineReadinessReport`; enlaces y referencias que no existen |
| D-03 | Baja | Confirmado | `.ai/CURRENT_STATE.md` dice v1.1.1 y `.ai/sessions/INDEX.md` no tiene sesiones desde 2026-10-10 |
| D-04 | Baja | Confirmado | El refactor `21df2668` eliminó comentarios de justificación (M-4, PF-08, PD-11…) |

#### A-01 — Auditoría estructurada `ok` con constraints sin reactivar (Media, confirmado)

- `dump/_audit_events.py:142-143`: `status = "failed" if error is not None or failed_tables else "ok"`; no mira
  `result.constraint_reactivation_error` (v1.2.0). Si `enable_all()` lanza, `ConstraintManager.__exit__`
  (`dump/_constraints.py:71-76`) guarda el mensaje y deja `constraint_results = []`, así que
  `constraints_failed = 0` también.
- Reproducido (sonda, caso 3): `DumpResult(constraint_reactivation_error="conexión perdida")` →
  `status='ok'`, `constraints_failed=0`.
- Impacto: un consumidor de `AuditSink` (el canal estructurado, ADR-002) no se entera de que el destino quedó con FK/CHECK
  desactivadas; solo lo dicen el log, el campo del `DumpResult` y la hoja del Excel.
- Test que falta: `DumpAuditEvents.run` con `constraint_reactivation_error` (y atributo en `attributes`).

#### A-02 — asyncpg reescribe marcadores dentro de literales (Media, confirmado)

- `executors/async_query_executor.py:30` (`_ASYNCPG_PARAM`) y `:127-147` (`_to_asyncpg`): la regex no conoce
  comillas, comentarios ni `$$…$$`.
- Reproducido (sonda, casos 1a/1b): `SELECT ':name' AS lit, :name AS v` → `SELECT '$1' AS lit, $1 AS v`;
  `SELECT '%(n)s' …` → `SELECT '$1' …`. El literal cambia de valor sin error.
- Alcance acotado: solo si el nombre del literal coincide con una clave de `params`. Los tests nuevos
  (`tests/unit/test_async_executor_asyncpg.py`) cubren `::` y `'10:30'`, no literales con el mismo nombre.

#### A-03 — Orden y anchos de la hoja «Errores de Reactivación» (Baja, confirmado)

- `dump/reporters.py:209-210` la inserta antes de `Índices`/`Auditoría Bulk`/`Secuencias PK`, contra la regla del
  propio módulo (`reporters.py:14`, «Las hojas opcionales se añaden siempre al final, para no mover las demás»).
  Sonda (caso 2): sin error `Índices` es la 4.ª hoja; con error, la 5.ª. Quien lea por índice se desplaza. La
  documentación (`docs/api/dump_reporter.md:13,55`) describe el orden real («Hoja 4»), así que el fallo es la regla.
- `reporters.py:349-353`: fija A=22 y B=80 y después llama a `_autowidth`, que los pisa. Sonda: A=65 (la nota larga
  de la fila 4) y B=15 (mensaje corto). El mensaje de error, lo importante, queda en la columna estrecha.
- Cosmético en el mismo bloque: separador `# ----` duplicado y dos secciones «Hoja 4» (`reporters.py:320-356`).

#### A-04 — Recomendaciones del advisor que no funcionan (Media, confirmado por la documentación de los motores)

- `performance_advisor.py:569-570`: `SET GLOBAL innodb_write_io_threads = <value>;` — en MySQL la variable no es
  dinámica (`SET GLOBAL` falla con «read only variable»); requiere `my.cnf` y reinicio. En MariaDB depende de versión.
- `performance_advisor.py:553-555`: «dinámico en MySQL 8.0.30+» para `innodb_log_file_size` — desde 8.0.30 esa
  variable está obsoleta y lo dinámico es `innodb_redo_log_capacity`. Repetido en
  `docs/guides/performance_readiness_guide.md:40-44` (tabla «Tipo: Dinámico»).
- `sqlserver/_variables.py:102` (MAXDOP): «ajustar a nCPU/2 con SET MAXDOP» — no existe esa sentencia; es
  `sp_configure 'max degree of parallelism'` o `ALTER DATABASE SCOPED CONFIGURATION SET MAXDOP`.
- Impacto: el usuario copia el comando de la recomendación y falla, o reinicia sin necesidad.

#### A-05 — Durabilidad: `innodb_flush_log_at_trx_commit` (Media, hipótesis de diseño)

- `performance_advisor.py:519-539`: `2` → OK, `1` (valor por defecto y el único ACID) → WARNING «cambiar a 2»,
  `0` → CRITICAL «inseguro». Con `2` se pierden hasta ~1 s de transacciones confirmadas si cae el sistema operativo;
  con `0`, si cae `mysqld`. Marcar el valor seguro como aviso empuja a rebajar la durabilidad del servidor entero
  (no solo de la carga). Decisión del producto: como mínimo, INFO y la advertencia de pérdida en la recomendación.

#### A-06 — Umbrales incoherentes con su recomendación (Baja, confirmado)

- `write_timeout`: mínimo 30 s (`performance_advisor.py:69`) con el texto «Recomendado ≥60 s»: 45 s sale OK.
- `cost threshold for parallelism`: INFO solo si `< 10`, con el texto «recomendado 50–100»: 20 sale OK.

#### A-07 — Mensaje completo de la excepción en el Excel (Baja, hipótesis)

- `dump/_constraints.py:75`: `self.reactivation_error = str(exc)` → `DumpResult` y hoja del Excel. `DumpConstraintError`
  incluye el mensaje del driver (SQL, nombres de objetos). El advisor sigue la política contraria («solo el tipo,
  nunca el mensaje», `_advisory.py:57`). No se ha visto una URL con credenciales en estos mensajes; conviene
  decidir la política y documentarla.

#### A-08 — Tipado de `DumpConfig` tras aceptar `str` (Baja, confirmado)

- `dump/_models.py:173-186`: los campos se anotan `StrPath` aunque `__post_init__` los deja como `Path`. Quien lea
  `cfg.output_dir / "x"` con mypy recibe un error; prueba de ello, `orchestrator.py` vuelve a validar las rutas en
  `_init_dump_run()` para obtener `Path`.

#### A-09 — Casting a medias en el advisor (Baja, confirmado)

- `588a35e4` («validar casting int/bool») solo cubre MySQL. `postgresql/_variables.py:62-65` sigue con
  `int(conn_params.get(...))` y `bool(conn_params.get("keepalives", True))`: `"abc"` → `ValueError` capturado en
  `_check_postgresql` (`performance_advisor.py:612-614`), que devuelve `[]` y **pierde también los checks
  dinámicos**; `keepalives="false"` → `True`.
- En MySQL, un `autocommit` o `pool_timeout` inválido corta con `return` y también omite los dinámicos
  (`performance_advisor.py:408, 436`).

#### A-10 — `batch_window_seconds` sin validar (Baja, confirmado)

- `doc/database_documentation.py:85-101`: parámetro público nuevo (429a45c5) sin validación (negativo, `bool`, `str`)
  y sin test a través de `DatabaseDocumentation` (los tests lo usan en el runtime interno).

#### A-11 — Nombre automático de carpeta en Windows (descartado en `/tech-debt`)

> **Corrección (2026-10-15, `/tech-debt`)**: falso positivo. El nombre automático es siempre
> `<identificador>-<fecha_hora>` (`output_runtime.py`, `generate_auto_output_filename`) y Windows solo rechaza el nombre
> exacto: `con-20261015_120000`, `con.db-20261015_120000` y `nul.x-1` se crean sin error; `CON`, no (WinError 267,
> comprobado en el scratchpad). Texto original:

- `doc/infrastructure/runtime/output_runtime.py:19`: sustituye `<>:"|?*`, barras, espacio y control, pero no los nombres
  reservados (`CON`, `NUL`, `COM1`…) ni el punto final. Base de datos `con` → misma familia de `OSError` que el
  hotfix ae1e8098 (ahora envuelto en `DocumentationRenderError`).

#### D-01 — CHANGELOG con 2.0.0 «Por publicar» (Media, confirmado)

- `CHANGELOG.md:57`: `## [2.0.0] - Por publicar`, pero existe el tag `v2.0.0` y después se publicó `v2.1.0`. Además,
  la historia tuvo un commit `release: v1.2.1` (`bf21c6b0`) después de `v2.0.0`, corregido en `eacd2eb1`; no hay tag
  `v1.2.1` ni referencias en `docs/` (verificado).

#### D-02 — Documentación de API del advisor (Baja, confirmado)

- `EngineReadinessAdvisor`, `EngineReadinessReport` y `AdvisoryFinding` son públicos en `util_bbdd.connection` y no
  tienen página en `docs/api/`. `docs/guides/performance_readiness_guide.md:353` enlaza «EngineReadinessAdvisor API» a
  `api/validators_system.md`, que no los menciona; `docs/guides/engine_readiness_usage_guide.md:274` cita
  `docs/api/engine_readiness_advisor.md`, que no existe (en texto, por eso `--strict` no lo detecta).
- `engine_readiness_usage_guide.md` es una guía de prompts de IA publicada en la navegación de usuario
  (`mkdocs.yml:118`), con checklists para la IA («Solicito a usuario…»).

#### D-03 — Estado de sesión desactualizado (Baja, confirmado)

- `.ai/CURRENT_STATE.md:5`: «Versión: v1.1.1». `.ai/sessions/INDEX.md`: última fila `2026-10-10-plan-pendientes-global`;
  faltan las sesiones 2026-10-10 a 2026-10-15 (≥ 9 carpetas). Esta sesión tampoco se ha añadido al índice.

#### D-04 — Comentarios de justificación eliminados en un refactor (Baja, confirmado)

- `21df2668` (`refactor(dump): reducir complejidad cognitiva de _run_dump`) quitó los comentarios que explicaban
  decisiones: M-4 (un aviso por volcado), PF-08 (offset del CSV de auditoría), PD-11 (reflejar tablas cargadas),
  «Sin esto, un fallo del informe perdía el resultado», «Sin traza: la excepción se relanza…», orden
  `IndexManager` dentro de `ConstraintManager`. El código es el mismo; se pierde el porqué.

### Contratos públicos sync/async

- v2.0.0: retirada de `PoolExhaustedError` y `DiffReportGenerationError` de raíz, `exceptions` y `_core`: coherente y con
  guía (`docs/guides/api_1_0_migration.md:146-172`). MAJOR correcto.
- Aditivos sin ruptura: rutas `str` (v1.1.0), `DumpResult.constraint_reactivation_error`, `DumpReporter.generate(…,
  constraint_reactivation_error, engine_readiness)`, `AuditManager(engine=)`, `exportar_resumen_excel(engine=)`,
  `SyncDatabaseManager.get_engine_readiness()`, `EngineReadinessAdvisor.assess/engine_report/describe_engine`.
- `EngineReadinessAdvisor.report()` devuelve la lista en lugar de `None`: compatible.
- `[Unreleased]` declara MINOR: correcto. Cambio de comportamiento a señalar en notas: `dump` abre ahora una conexión
  extra al **origen** al empezar (`orchestrator.py:_engine_readiness`).
- Async: no hay equivalente de `get_engine_readiness()` en `AsyncDatabaseManager` (asimetría asumida; documentarla).
- `EngineReadinessReport.db_type` es `"sqlserver"` desde el manager y `"mssql"` desde un engine: el mismo motor sale con
  dos nombres en Word/Excel según el camino.

### Compatibilidad y migraciones

- Sin migraciones de datos. Contrato de hojas del Excel de `dump`: ver A-03.

### Performance

- `dump` verifica origen y destino al empezar: una conexión y entre 3 y 6 consultas de catálogo por motor y proceso.
  Coste despreciable frente a un volcado.
- Sin regresiones observables en la suite; no se ha ejecutado benchmark (fuera del alcance de `audit_code`).

### Seguridad

- Sin hallazgos bloqueantes. Ver A-07 (política de mensajes). El advisor no revela la URL ni la contraseña
  (`report()` redacta; `describe_engine()` omite usuario y contraseña; `error` solo lleva el tipo).

### Tipado

- mypy limpio. `Any` en firmas de validadores (`connection: Any`, `validator: Any` en `_check_mysql_thresholds`/
  `_check_mysql_log_file_size`) heredados del patrón existente. A-08.

### Tests faltantes o insuficientes

1. `DumpAuditEvents.run` con `constraint_reactivation_error` (A-01).
2. `DumpReporter.generate(constraint_reactivation_error=…)`: hoja, orden y anchos (A-03). Solo existe el test de
   `ConstraintManager.__exit__` (`tests/unit/dump/test_constraints.py:560-590`).
3. Orquestador: `DumpResult.constraint_reactivation_error` poblado de extremo a extremo.
4. `_to_asyncpg` con literales que contienen `:nombre`/`%(nombre)s` (A-02).
5. `DatabaseDocumentation(batch_window_seconds=…)` y valores inválidos (A-10).
6. PostgreSQL `check_static` con valores no numéricos / `keepalives="false"` (A-09).
7. `RejectsCoordinator` y `TableMaintenance` no tienen tests propios: los cubre `BulkCrud` (aceptable tras un
   refactor de extracción).

### Deuda técnica

- D-04 (porqués perdidos), D-03 (estado `.ai/`), separadores duplicados en `reporters.py`.
- `_init_dump_run()` revalida rutas que `DumpConfig.__post_init__` ya validó (síntoma de A-08).

### Veredicto

**APROBADO CON CONDICIONES**

Sin bugs de pérdida de datos ni contratos públicos rotos; puertas de calidad en verde. Condiciones antes de la
próxima release:

1. A-01 (auditoría estructurada) y A-04 (comandos que fallan) corregidos.
2. D-01 (CHANGELOG 2.0.0) corregido.
3. Decisión documentada sobre A-05 y A-07.

El resto (A-02, A-03, A-06, A-08 a A-11, D-02 a D-04) puede ir a deuda técnica priorizada.

---

## VERSION

### Commits sugeridos para los cambios derivados

```text
fix(dump): el evento run de audit_sink es failed si falla la reactivación de constraints
fix(connection): recomendaciones del advisor válidas en MySQL y SQL Server
fix(dump): hoja «Errores de Reactivación» al final y con su ancho de columnas
fix(executors): asyncpg no traduce marcadores dentro de literales SQL
fix(connection): casting validado en los checks estáticos de PostgreSQL
docs: CHANGELOG 2.0.0 con fecha; página de API de EngineReadinessAdvisor
```

### Pruebas sugeridas (casos no cubiertos)

- `test_run_event_failed_when_constraint_reactivation_fails`
- `test_reactivation_sheet_keeps_optional_sheet_order` y `…_column_widths`
- `test_dump_result_carries_reactivation_error_end_to_end` (SQLite, `enable_all` que lanza)
- `test_to_asyncpg_keeps_placeholders_inside_string_literals`
- `test_batch_window_seconds_rejects_negative_and_non_int`
- `test_postgresql_static_checks_invalid_values_keep_dynamic_checks`
- Integración SQL Server (pendiente en esta auditoría por el puerto bloqueado): advisor MAXDOP/cost threshold y
  pyodbc rows contra servidor real.
