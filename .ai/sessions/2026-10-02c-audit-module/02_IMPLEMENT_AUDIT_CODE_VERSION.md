# IMPLEMENT + AUDIT_CODE + VERSION — módulo de auditoría centralizado

Aprobación del usuario: «C3 completo, C4 ok. IMPLEMENT». C1 (nombre `util_bbdd.audit`, capa 3) y C2 (2 `patch` de
`test_audit_subsystem.py`) no se respondieron de forma explícita: se aplicaron tal como estaban en el PLAN y se
declaran aquí. C5 se interpretó como todas las fases (F0–F5), al ser C3 «completo».

Sin commits: el usuario no los pidió. Propuesta en § VERSION.

---

## IMPLEMENT

### Línea base (antes de F0)

- Suite unitaria (`-m "not integration"`): **5722 passed, 32 skipped**.
- C4: ficheros de referencia generados con el código de v0.28.0 **antes de mover nada**:
  `tests/fixtures/audit/legacy_audit_v0_28_0.csv` y `legacy_rejects_v0_28_0.csv`, marcados con `-text` en
  `.gitattributes`, porque se comparan byte a byte (CRLF del módulo `csv`).
- Microbenchmark de escritura (2000 registros, 7 rondas, mediana): `registrar_operacion` 122–126 µs/registro;
  `_registrar_lote(50)` 5,45–5,83 µs/registro.

### Resultado por fase

| Fase | Contenido | Suite unitaria |
|---|---|---|
| F0 | `audit/events.py`, `contracts.py`, `sinks.py` (Null, Memory); `LAYER["audit"]=3`; figura de capas (nodo `audit/` + flecha y etiqueta derivadas de `DRAWN`); `.ai/architecture.md`; conformidad de `Protocol`; tests de formato, eventos, contrato y dirección de imports | 5749 passed |
| F1 | `locks.py`, `files.py`, `legacy_csv.py`, `analytics.py`, `exporters.py`, `html_template.py`, `counters.py` movidos; `bulk/_audit/*` re-exportadores; `AuditManager` fachada; eliminado `bulk/_support/excel.py` (huérfano); 2 `patch` (C2) | 5760 passed |
| F2 | `audit/rejects.py` (`RejectsWriter`, `REJECT_COLUMNS`), `audit/text.py` (`AuditText`); `bulk/_support/rejects.py` conserva `Isolator` y re-exporta | 5773 passed |
| F3 | `dump/_audit_summary.py` delega en `AuditFiles`/`AuditCsvRepository.read_since`; `dump` importa `AuditCounters` de `audit` y `AuditError` de `_core` | 5773 passed |
| F4 | `migrate/_audit_events.py` (`MigrationAuditEvents`, `MigrationAuditRecorder`); `execute(..., *, audit_sink=None)`, `validate_views(..., audit_sink=None)`, `audit_events()`; callback por sentencia en `_execute_statements` y `_execute_with_custom_one` | 5783 passed |
| F5 | `JsonLinesAuditSink`; `bulk/_audit/events.py` y `dump/_audit_events.py`; `audit_sink`/`audit_run_id` en `BulkCrud`, `ParallelBulkLoader`, `DumpConfig`; `*.audit_run_id` en resultados; exportaciones en la raíz; documentación, ADR-002, CHANGELOG | **5809 passed, 32 skipped** |

Integración contra los 5 motores del banco (PostgreSQL, MySQL, MariaDB, SQL Server, Oracle):
`test_bulk_audit_20261001.py`, `test_bulk_engines.py`, `test_dump_engines.py`, `test_migrate_views_e2e.py` →
**408 passed, 1 skipped**.

Rendimiento tras F1 y tras F5 (sin destino): `registrar_operacion` 119–124 µs; lote 5,3 µs. **Sin regresión**
(umbral ≤ 5 %). Con destino: `JsonLinesAuditSink` ≈ 128 µs/evento (como el CSV: domina abrir el fichero);
`MemoryAuditSink` ≈ 2,7 µs/evento.

Calidad: `ruff check` y `ruff format` limpios en `src tests`; `mypy src tests/unit/test_protocol_conformance.py` con
los **mismos 12 errores previos** (`_core/export_safety.py`, `connection/mysql/*`, `migrate/views/*`), ninguno nuevo
(**corrección 2026-10-02f**: no eran del código sino del entorno —faltaban `sqlglot` y `types-PyMySQL` del extra
`dev` y sobraba `types-openpyxl`; ver `.ai/sessions/2026-10-02f-test-count-drift/TRACEABILITY.md`—);
`gen_arquitectura_capas.py` pasa (406 ficheros); `mkdocs build --strict` sin avisos (Zensical no está instalado en
este equipo).

### Desviaciones respecto al PLAN

| Desviación | Motivo |
|---|---|
| Un **tercer test** modificado: `test_planner.py::test_execute_has_no_override_flag` | Fijaba la firma exacta `["self", "target_connection"]`; con `audit_sink` (aprobado en F4) no podía pasar. Se mantiene su intención: ningún parámetro para saltarse el bloqueo; `audit_sink` es keyword-only |
| `parent_id` no se rellena | Las ejecuciones anidadas heredan el `run_id` de la de fuera (volcado → cargas → operaciones), lo que basta para correlacionar. Se conserva el campo para emisores propios |
| Sin `kind="reject"` ni `status="rejected"` | Un evento por fila rechazada sería ruido y duplicaría el CSV de rechazos; `rows_rejected` va en los eventos `partition` y `table` |
| `AuditError` en `dump` importado de `_core` | Era un import de `bulk.audit` (público). Se cambia en F3 por coherencia; sin efecto funcional |
| `dump/_models.py` sigue importando `validate_isolation`/`validate_chunk_size` de partes privadas de `bulk` | No son auditoría: fuera de alcance (backlog) |

---

## AUDIT_CODE

### Hallazgos

| ID | Severidad | `archivo` | Hallazgo | Estado |
|---|---|---|---|---|
| AC-1 | Media | `bulk/_support/persistence.py` (`flush_audit_before_commit`) | Con `audit_strict=True` en `bulk_session`, si el CSV se escribía antes del commit y fallaba `audit_sink`, la sesión se deshacía con las filas ya en el CSV, sin contarlas en `audit_uncommitted_records` | **Corregido** (`_csv_written`); test `test_strict_csv_escrito_y_destino_fallido_cuenta_lo_escrito_sin_commit` |
| AC-2 | Baja | `bulk/_execution/parallel_loader.py` | El primer borrador guardaba el `run_id` de la carga en curso como atributo de instancia (estado compartido si se lanzan dos cargas a la vez con el mismo loader) | **Corregido** antes de cerrar F5: se pasa como argumento a `_load_partition` |
| AC-3 | Baja | `bulk/_support/persistence.py` | `audit_failures` cuenta dos veces un registro que falla en el CSV y en el destino | Aceptado y documentado (docstring, CHANGELOG, `docs/api/audit.md`) |
| AC-4 | Info | `audit/events.py` | `AuditEvent.now(**fields)` necesita un `type: ignore[arg-type]` (kwargs heterogéneos) | Aceptado; mypy sin errores nuevos |

### Matriz de cobertura re-verificada (estado tras F5)

Todas las decisiones de `01_PLAN_AUDIT_PLAN.md` § 2 se cumplen. Cambios de estado: INV-BLK-17 (conciliación) se
comprueba contra `MemoryAuditSink` (`test_carga_paralela_eventos_y_conciliacion`); INV-BLK-19 y INV-DMP-09 adaptados
(`pk_sync`, `table`, `constraint`, `index`); INV-MIG-05/06 adaptados (`statement`, `view_validation`).

### Imports de `audit/` hacia capas superiores

Ninguno (`tests/unit/audit/test_audit_import_direction.py` y `test_architecture_import_rules.py`). Aristas medidas
nuevas: `bulk → audit`, `dump → audit`, `migrate → audit`, todas a una capa inferior.

### CSV de referencia

`test_legacy_format.py` pasa después de cada fase: el CSV de auditoría y el de rechazos son idénticos byte a byte a
los de v0.28.0.

**Veredicto AUDIT_CODE:** GO (sin hallazgos abiertos de severidad media o superior).

---

## VERSION

### Commits propuestos (no ejecutados)

Las fases comparten ficheros (`dump/orchestrator.py` tiene cambios de F3 y F5), así que no se pueden separar por fase
sin reescribir. Propuesta en dos commits:

```text
feat(audit): módulo de auditoría centralizado util_bbdd.audit (ADR-002)

- AuditEvent, AuditSink y destinos JSON Lines/memoria/nulo (capa 3, solo importa _core)
- El CSV de auditoría y el de rechazos se mueven a util_bbdd.audit con su formato congelado
  (test byte a byte contra v0.28.0); bulk/_audit y bulk/_support/rejects re-exportan
- audit_sink opcional en BulkCrud, ParallelBulkLoader, DumpConfig, MigrationPlan.execute y validate_views
- dump deja de importar partes privadas de la auditoría de bulk; migrate deja rastro de sus sentencias
- Docs: functional/audit.md, api/audit.md, ADR-002, CHANGELOG; figura de capas regenerada
```

```text
docs(ai): prompt audit_module, inventario de partida y sesión 2026-10-02c
```

### Impacto en API pública

Solo adiciones opcionales: `util_bbdd.audit` (y 5 nombres en `util_bbdd`); `BulkCrud(audit_sink, audit_run_id)`,
`BulkCrud.audit_run_id`; `ParallelBulkLoader(audit_sink, audit_run_id)`, `ParallelLoadResult.audit_run_id`;
`DumpConfig.audit_sink`, `DumpResult.audit_run_id`; `MigrationPlan.execute(..., *, audit_sink)`,
`validate_views(..., audit_sink)`, `audit_events()`. Nada eliminado de la API pública (`bulk/_support/excel.py` era
privado).

### Rollback

Revertir el commit `feat(audit)`. No hay migraciones de datos: los CSV existentes siguen siendo válidos en los dos
sentidos (formato idéntico). Los ficheros JSON Lines que se hayan generado quedan como ficheros sueltos.

### Backlog

- Retirar el setter obsoleto `AuditManager.columnas_auditoria` (INV-BLK-12; breaking, próxima versión menor).
- `dump/_models.py` → `validate_isolation`/`validate_chunk_size` desde módulos públicos (H-06 fuera de auditoría).
- Lock entre procesos para los ficheros de auditoría (H-05, descartado por ahora).
- Neutralizar fórmulas en `tabla` del CSV heredado solo si se acepta cambiar su formato (riesgo residual de H-07).
- Retirar los re-exportadores de `bulk/_audit/*` en una versión mayor.
- `/version-closure` para numerar la versión (sugerencia: 0.29.0, *minor*, por las adiciones de API).

---

## AUDIT_CODE independiente (`/audit-code`, alcance: todo el módulo, foco: todo)

Veredicto: **APROBADO CON CONDICIONES**. El usuario aprobó corregir los hallazgos 1–4 y añadir los tests 1–3 en esta
sesión.

| # | Sev. | Hallazgo | Corrección | Test |
|---|---|---|---|---|
| 1 | Media | Con `audit_strict`, una excepción de un destino propio que no fuera `AuditError`/`OSError` escapaba del `except` por tabla de `dump` y abortaba `run()` | `persistence._emit` la relanza como `AuditError` (original en `__cause__`) | `dump/test_audit_sink.py::test_strict_destino_propio_…`, `bulk/test_audit_sink.py::test_strict_destino_propio_…` (fallan sin la corrección: comprobado) |
| 2 | Baja | `MigrationPlan.execute`: un fallo de `emit_statements` no dejaba evento `run` | La emisión entra en el `try` que escribe el cierre | `migrate/test_audit_events.py::test_fallo_del_emisor_registra_el_run_fallido` |
| 3 | Baja | `BulkCrud.audit_run_id` devolvía el id recibido sin destino (el docstring y `ParallelBulkLoader` dicen `None`) | `None` sin `audit_sink` | `test_run_id_sin_destino_es_none` |
| 4 | Baja | Logs de `audit_uncommitted_records`/`unaudited_committed_rows` decían «CSV» con solo destino | `_audit_destination` en el mensaje | `test_log_sin_csv_no_menciona_el_csv` |

Tests añadidos además: propagación de `run_id` a `ParallelBulkLoader` por rangos (engine simulado: SQLite fuerza 1
rango), `max_parallel_tables=2` con un `run_id` común, y sentencia fallida por `execute_custom_one`.

Resultado: suite unitaria **5817 passed, 32 skipped**; ruff limpio; mypy sin errores nuevos (los 12 previos;
**corrección 2026-10-02f**: del entorno, no del código — ver `.ai/sessions/2026-10-02f-test-count-drift/TRACEABILITY.md`).

Pendientes (no pedidos): hipótesis 5 (construcción de eventos fuera del `try` en `_write_dump_events`), tests 4–6 de la
lista del audit-code salvo el de `execute_custom_one` (eventos de `update`/`delete` paralelos; solo destino con
`commit_every_n_chunks` y fallo a mitad).

Commit adicional propuesto (no ejecutado):

```text
fix(audit): fallo del destino en modo estricto como AuditError y run de cierre si falla la emisión
```
