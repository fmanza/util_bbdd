# TRACEABILITY

## Session metadata
- id: 2026-10-27-web-gaps-ola4
- fecha: 2026-10-26 / 2026-10-27
- rama: develop
- skill: new_feature + version-closure
- fase: IMPLEMENT + AUDIT_CODE + VERSION de la ola 4 (v4.4.0)

## Prompt issued
Ola 4 del plan de huecos de util_bbdd_web (volcado, util_bbdd 4.4.0): fases U-V1 … U-V8, un commit por fase en
`develop`; solo parámetros opcionales nuevos, sin cambios de valor por defecto (G30 solo `FutureWarning`); U-V3 antes
que U-V8; progreso con `util_bbdd.progress`. Plan canónico: `docs/plan/UTIL_BBDD_GAPS_PLAN.md` de util_bbdd_web (solo
lectura); PLAN y AUDIT_PLAN aprobados allí (2026-10-25).

## Context sources
- `src/util_bbdd/dump/` en 4.3.0 (orquestador, `_constraints.py`, `_audit_events.py`, `_source_reader.py`, `_models.py`).
- `backend/app/integrations/util_bbdd/dump.py` y `backend/tests/integration/test_bench_dump.py` de util_bbdd_web
  (rodeos de G29, G32, G33, G34) para ajustar la API y reproducir los fallos.
- Contrato de `util_bbdd.progress` (4.1.0) y su uso en `compare()` (4.2.0) y `MigrationPlan.execute()` (4.3.0).

## AI output summary
- Un commit por fase (ruff, ruff format, mypy y pytest completo en cada una; AUDIT_CODE tras cada fase):
  - U-V1 `26414f0e` G29: `DumpOrchestrator.plan()` → `DumpPlan` (`DumpPlanTable`, `DumpPlanWarning`, `DumpWarningCode`).
  - U-V2 `d2eb4ccb` G6: evento `table` de `audit_sink` al terminar cada tabla (`_table_finished`); reintento al final.
  - U-V3 `4887fb17` G31: `constraints_journal.json` en `output_dir` (SQL Server, PostgreSQL, Oracle) y
    `restore_constraints(engine, journal)`; un diario pendiente bloquea `run()` con `DumpConstraintError`.
  - U-V4 `9e9a24f7` G32: causa en `bulk/_support/oracle_batch_errors.py` (lote de una fila → `execute`, sin
    `batcherrors`); listener de `do_execute` con `collect(single_row=True)`.
  - U-V5 `38bcd6d7` G33: texto ISO de columnas de fecha/hora de un origen SQLite → `date`/`datetime`/`time` si la
    columna del destino es de fecha u hora.
  - U-V6 `28eed781` G34 (`security`): `dump/_sql_utils.py::error_message` (primera línea, sin URL, valores
    enmascarados) en `error_msg` de tablas y constraints y en `constraint_reactivation_error`.
  - U-V7 `71b72e8e` G30: `FutureWarning` si `DumpConfig` no recibe `truncate_target` (descriptor `_TruncateTargetField`).
  - U-V8 `c75a699c` G1: `run(on_progress=, cancel_token=)`, operación `"dump"`, fases `"tables"` y `"rows"`.
- Evidencias: pytest 6619 passed, 614 skipped (`build/logs/U-V8_pytest.txt`); mypy limpio (352 ficheros);
  `zensical build --strict` limpio; `-m integration` con el banco: 656 passed y 14 fallos/errores de entorno
  (`asyncpg`/`aioodbc` no instalados, HSQLDB sin `JAVA_HOME`), ninguno en `dump` ni `bulk`
  (`build/logs/ola4_integration.txt`). Banco por fase: U-V3 y U-V8 en PostgreSQL, SQL Server y Oracle; U-V4 y U-V6 en
  los 5 motores (y MariaDB Connector); U-V5 SQLite → los 5 (`build/logs/U-V5_bench_check.txt`).
- `scripts/gen_arquitectura_capas.py`: sin aristas nuevas (`progress` ya es Foundation); 352 ficheros.
- VERSION: `release: v4.4.0`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Ola 4 | `src/util_bbdd/dump/`, `src/util_bbdd/bulk/_support/oracle_batch_errors.py`, `rejects.py` | completado (v4.4.0) |
| Tests | `tests/unit/dump/test_dump_plan.py`, `test_audit_events_during_dump.py`, `test_constraints_journal.py`, `test_sqlite_dates.py`, `test_error_messages.py`, `test_truncate_target_warning.py`, `test_dump_progress.py`; `tests/integration/test_dump_engines.py` (diario, isolate de una fila, `error_msg`, cancelación) | completado |

## Desviaciones del plan
- U-V4: el plan situaba el arreglo en `dump/orchestrator.py` y `dump/_sql_utils.py`; la causa está en `bulk` y el
  arreglo corrige también `BulkCrud` (un último lote de una fila fallaba igual).
- U-V5: solo se convierte si la columna del destino es de fecha u hora, y `TIME` solo hacia `TIME`: hacia texto, o
  `TIME` hacia el `DATE` de Oracle (oracledb rechaza `datetime.time`), el valor sigue como texto.
- U-V7: `pytest.ini` ignora ese `FutureWarning` en los tests que no lo prueban (eran 147 avisos).

## Notas para las fases W-V de util_bbdd_web
- W-V1: `DumpPlan` no cuenta filas ni marca columnas de fecha; `required_target_columns` y `outside_references`
  sustituyen a `_required` y `outside_references` de la vista previa. Los códigos de aviso son `DumpWarningCode`.
- W-V2: progreso `"tables"` (0 de N, luego uno por tabla) y `"rows"` (por lote); el volcado pasa a ser cancelable.
  Con `parallel_pk_ranges` (la web no lo expone) no hay `"rows"`.
- W-V3: el diario está en `output_dir`; la web pasa `output_dir=work_dir` y borra `work_dir` en un `finally`: si
  `DumpResult.constraints_journal` no es `None` (reactivación fallida), hay que conservarlo antes de borrar.
  `restore_constraints` necesita el engine del destino. Un diario pendiente hace que `run()` lance `DumpConstraintError`.
- W-V4: los avisos `isolate_oracle` y `sqlite_dates` sobran; el test de la web de G32 (`test_append_isolates…`) pasa a
  aislar también en Oracle.
- W-V5: `error_msg` ya llega saneado; `redact_values` se mantiene como defensa (regla 5 del plan).

## Directrices para Futuras IAs
- **[dump]**: `plan()` y `run()` comparten `_analyze_dump_phase` y `_compute_load_order`: el orden es el mismo por
  construcción. `plan()` lee las FK una segunda vez (`_fk_graph.referred_tables`) para `outside_references`.
- **[dump]**: `_table_finished` es el único punto de «tabla terminada» (auditoría G6 y progreso G1); se llama solo desde
  el hilo principal (bucle secuencial, `as_completed` y ciclos). `_write_dump_events` omite las tablas ya escritas.
- **[dump]**: el diario de constraints solo existe en `_JOURNALED_DIALECTS` (mssql, oracle, postgresql); se borra en
  `ConstraintManager.enable_all` si ningún resultado es `"failed"`. `restore_constraints` reconstruye el gestor con
  `ConstraintManager.from_journal` y llama a `enable_all`: mismas sentencias que el cierre del volcado.
- **[bulk]**: en Oracle con `isolate`, SQLAlchemy envía un lote de una fila con `execute`, no `executemany`; cualquier
  mecanismo enganchado a `do_executemany` debe cubrir también `do_execute` (`oracle_batch_errors.execute_single_row`).
- **[dump]**: los mensajes de error que acaban en resultados pasan por `dump/_sql_utils.py::error_message`; los
  `error_msg` de `IndexActionResult` y `PKSyncResult` vienen de `bulk` y no se sanean (con `manage_indexes="all"` el de
  índices lista claves duplicadas a propósito).
- **[dump]**: la conversión de fechas de SQLite (`_temporal_parsers`) se calcula en serie tras `_prefetch_metadata`;
  los hilos solo la leen. `Series.map` con `datetime` infiere `datetime64`: se construye `pd.Series(..., dtype=object)`.
- **[dump]**: `_track_batches` envuelve el iterador que recibe `BulkCrud` (después de `_prefetch`); al cerrar hay que
  cerrar las dos capas, o el hilo de `_prefetch` queda vivo con la conexión de lectura.
- **[dump]**: con destino PostgreSQL el lote de escritura por defecto es de 20 000 (`_rebatch`): para probar la
  cancelación entre lotes hace falta `write_batch_size` pequeño.
- **[tests]**: `DumpConfig` sin `truncate_target` emite `FutureWarning` (filtrado en `pytest.ini`); los tests nuevos lo
  pasan explícito. Instancias creadas con `DumpOrchestrator.__new__` en tests: los atributos nuevos se leen con
  `getattr(..., default)`.
- **[herramientas]**: `python - <<'EOF'` también pierde un nivel de barra invertida (un `"\\n"` acabó como salto de
  línea real dentro de una cadena); para código con escapes, Write/Edit.
- **[banco]**: G32 se reproduce con una sola fila en el origen (con tres filas, `executemany`, sí aislaba).

## Veredicto final
Veredicto: CLOSED (ola 4, v4.4.0)
Pendientes al cierre:
- Push de `develop` y del tag `v4.4.0`, fast-forward de `main` y wheel + `.sha256` en GitHub Releases (propietario).
- Registrar la ola 4 en §6 del plan de util_bbdd_web (desde esa sesión; aquí es solo lectura).
- HSQLDB y async del banco sin verificar en este venv (falta `JAVA_HOME`, `asyncpg`, `aioodbc`): no afectan a `dump`.
- Fuera de alcance, sin hueco abierto: si el proceso muere con `manage_indexes`, los índices borrados (PostgreSQL,
  MySQL InnoDB) no tienen diario; el DDL para recrearlos solo queda en el log.
- Olas 5-6 (U-B, U-T) en sesiones aparte.
