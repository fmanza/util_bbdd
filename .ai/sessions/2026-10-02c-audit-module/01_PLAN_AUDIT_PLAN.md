# PLAN + AUDIT_PLAN — módulo de auditoría centralizado (`util_bbdd.audit`)

Contrato: `.github/prompts/audit_module.prompt.md` (manda sobre `new_feature`). Agente: Plan Architect.
Rutas `archivo:línea` verificadas el 2026-10-02 sobre `12d055c` (v0.28.0); rutas relativas a `src/util_bbdd/`
salvo que empiecen por `tests/`, `docs/`, `scripts/` o `.ai/`.

---

## PLAN

### 1. Supuestos (inputs por defecto del prompt)

| Input | Valor aplicado |
|---|---|
| Nombre del paquete | `src/util_bbdd/audit/` |
| Capa | **3** (ver § 5) |
| Fases de esta sesión | PLAN + AUDIT_PLAN |
| Compatibilidad | Sin breaking changes; API pública, mensajes y loggers idénticos; CSV byte a byte |
| Consumidores | `bulk/`, `dump/`, `migrate/` |
| Nuevas capacidades | Opt-in, desde `H-02`, `H-03` y `H-04` (§ 3) |
| Dependencias nuevas | Ninguna |

### 2. Matriz de cobertura

Leyenda: **C** = centralizado (pasa a `audit/`), **Q** = se queda en el módulo de origen, **A** = adaptado
(el origen lo convierte en `AuditEvent`). La fase indica cuándo cambia.

| ID | Decisión | Destino / motivo | Fase |
|---|---|---|---|
| INV-BLK-01 `AuditManager` | Q (fachada) | Sigue en `bulk/audit.py` con su logger `util_bbdd.bulk.audit` (lo fijan `tests/unit/test_audit_subsystem.py:413,422`); delega en `audit/` | F1 |
| INV-BLK-02 `AuditRecord`, `AUDIT_OPERATIONS` | C | `audit/legacy_csv.py`; `bulk/_audit/record.py` re-exporta | F1 |
| INV-BLK-03 formato CSV | C | `audit/legacy_csv.py` (`LegacyCsvAuditSink`), **formato congelado** y test de referencia byte a byte | F1 |
| INV-BLK-04 `rowcount` = filas enviadas | Q | Lo calcula `BulkCrud`; en `AuditEvent` se documenta `rows` como «filas enviadas» | F1 |
| INV-BLK-05 validación de parámetros | C | `audit/legacy_csv.py` (`validate_record`); mismos mensajes y `AuditValidationError` | F1 |
| INV-BLK-06 aviso único «deshabilitada» | Q | Política de la fachada (y de `dump`, INV-DMP-02); mensaje y logger fijados por tests | — |
| INV-BLK-07 lock por ruta | C | `audit/locks.py` (`path_lock`), **un único registro** en el proceso; `bulk/_audit/repository.py` re-exporta `_get_file_lock = path_lock` | F1 |
| INV-BLK-08 apartar cabecera ajena | C | `audit/files.py` (`set_aside`, `aside_path`, `first_line`), común al CSV de auditoría y al de rechazos | F1 |
| INV-BLK-09 lectura + caché (TTL + firma) + `parse_frame` | C | `audit/legacy_csv.py` (`AuditCsvRepository` se mueve con nombre y atributos; `bulk/_audit/repository.py` re-exporta) | F1 |
| INV-BLK-10 analítica | C | `audit/analytics.py` (`AuditAnalyticsService`), logger inyectado como hoy | F1 |
| INV-BLK-11 exportadores Excel/JSON/HTML | C | `audit/exporters.py` + `audit/html_template.py`; mismos nombres de fichero (`auditoria.xlsx/.json/.html`) | F1 |
| INV-BLK-12 setter obsoleto `columnas_auditoria` | Q | Se queda en la fachada con su `DeprecationWarning`; retirarlo es breaking → backlog | — |
| INV-BLK-13 auditoría diferida de `bulk_session` | Q | Lógica transaccional de `bulk/_support/persistence.py`; solo cambia el objeto en el que escribe | — |
| INV-BLK-14 política `audit_strict` | Q | Política del consumidor (`persistence.py`) | — |
| INV-BLK-15 4 contadores en `BulkCrud` | Q | Propiedades de `bulk/crud.py` | — |
| INV-BLK-16 `AuditCounters`, `SupportsAuditCounters` | C | `audit/counters.py`; `bulk/_audit/counters.py` re-exporta; el `Protocol` entra en `tests/unit/test_protocol_conformance.py` | F1 |
| INV-BLK-17 `ParallelBulkLoader` + invariante de conciliación | Q | Lógica de ejecución; la invariante se cubre con un test de contrato que use `MemoryAuditSink` | F5 |
| INV-BLK-18 `generar_sql` audita al momento | Q | `persistence.py` | — |
| INV-BLK-19 `PKSyncResult` | A | El tipo se queda en `bulk/_models.py`; adaptador → evento `pk_sync` | F5 |
| INV-REJ-01 `RejectsWriter`, `REJECT_COLUMNS` | C | `audit/rejects.py`; `bulk/_support/rejects.py` re-exporta (`tests/unit/bulk/test_on_error_isolate.py:26` sin cambios). El logger conserva el nombre `util_bbdd.bulk._support.rejects` de forma explícita | F2 |
| INV-REJ-02 neutralización de fórmulas en CSV | C | `audit/text.py` (`safe_csv_cell`), reutilizable por cualquier sink tabular nuevo | F2 |
| INV-REJ-03 import de privados (`_get_file_lock`, `AuditCsvRepository._ruta_apartado`, `bulk/_support/rejects.py:26,216`) | C | Desaparece: `rejects` usa `audit.locks` y `audit.files` (públicos del paquete). Resuelve `H-06` | F2 |
| INV-REJ-04 `Isolator`, `max_rejects`, `rejects_scope`, `_REJECTS_FAILURE_NOTE` | Q | Lógica de ejecución de `bulk` (SAVEPOINT y bisección), no de auditoría | — |
| INV-REJ-05 `validate_isolation`, `optional_non_negative_int` | Q | Validación de configuración de `bulk` | — |
| INV-DMP-01 `DumpConfig.bulk_audit_*`, rechazos | Q | Campos públicos; F5 añade `audit_sink` opt-in | F5 |
| INV-DMP-02 aviso único por volcado | Q | — | — |
| INV-DMP-03 agregación de contadores | Q | Usa `audit.AuditCounters` en lugar de `bulk._audit.counters` (`dump/orchestrator.py:44`) | F3 |
| INV-DMP-04 `DumpAuditSummary`, `build_audit_summary` | Q | Tipo público de `dump`; pasa a leer con `audit.legacy_csv` | F3 |
| INV-DMP-05 lectura incremental, `file_size`, `file_identity` | C | `audit/files.py` (`file_size`, `file_identity`) y `audit/legacy_csv.py` (`read_since`); `dump/_audit_summary.py` conserva delegados (`DumpOrchestrator._file_size` etc. los usan) | F3 |
| INV-DMP-06 filtro por `desde` (H3) y WARNING de discrepancia | Q | Regla del resumen del volcado; logger `util_bbdd.dump.orchestrator` | — |
| INV-DMP-07 `dump` importa privados de `bulk` (`dump/_audit_summary.py:17-18`) | C | Desaparece: `dump` importa de `audit` (capa 3). Resuelve `H-06` | F3 |
| INV-DMP-08 `DumpReporter` (6 hojas) | Q | Informe del volcado, ya usa `SafeWorkbook` (`dump/reporters.py:29`) | — |
| INV-DMP-09 `TableDumpResult`, `ConstraintResult`, `IndexActionResult`, `PKSyncResult` | A | Los tipos se quedan; `dump/_audit_events.py` los convierte en eventos `table`, `constraint`, `index`, `pk_sync` | F5 |
| INV-DMP-10 el volcado no aborta si falla el resumen/Excel | Q | Se extiende a los sinks opt-in: un fallo del sink se registra y no aborta (ver § 7) | F5 |
| INV-MIG-01 `MigrationWarning` | A | Se queda en `migrate/ir/models.py` (IR pública); `migrate/_audit_events.py` → eventos `plan_warning` | F4 |
| INV-MIG-02 recolección de avisos y colisiones | Q | `migrate/planner.py` | — |
| INV-MIG-03 sincronización de avisos de emisión | Q | `MigrationPlan._sync_warnings_from_tables` | — |
| INV-MIG-04 `execute` bloqueado con `ERROR`; contadores | Q | `migrate/ir/models.py:286,356`; el bloqueo también genera un evento si hay sink | F4 |
| INV-MIG-05 ejecución sentencia a sentencia | A | `execute(..., *, audit_sink=None)` opt-in: evento `statement` por sentencia (posición, `ok`/`failed`, duración, primera línea útil truncada a 120 como el error actual de `migrate/ir/models.py:398-402`). Resuelve `H-03` | F4 |
| INV-MIG-06 `ViewValidationResult` | A | Adaptador `view_validation_events(results)` sin cambiar `validate_views` | F4 |
| INV-MIG-07 informes texto/Markdown | Q | Formatean el plan, no son rastro de auditoría | — |
| INV-X-01 excepciones `Audit*` | Q | Siguen en `_core/exceptions.py`; `audit/` las importa de ahí y las re-exporta | F1 |
| INV-X-02 capas | C | `audit` = capa 3 (§ 5) | F0 |
| INV-X-03 tests | Q | Pasan sin cambios salvo los de § 8 | todas |
| INV-X-04 docs | — | Se actualizan (§ Documentación) | F5 |
| **INV-X-05** (nuevo) `_core/export_safety.py` + re-export `bulk/_support/excel.py` | Q | Punto único de escritura segura en Excel de toda la librería (capa 1); `audit/exporters.py` lo importa directamente | F1 |

### 3. Decisión sobre los huecos `H-*`

| Hueco | Decisión |
|---|---|
| H-01 sin modelo de evento común | **Incorporar en F0**: `AuditEvent` (§ 6) |
| H-02 sin correlación | **Incorporar en F5**, opt-in: `run_id`/`parent_id` en los eventos de los sinks nuevos; el CSV heredado no cambia |
| H-03 `migrate` sin rastro | **Incorporar en F4**, opt-in (`audit_sink`) |
| H-04 timestamp sin zona, coma decimal | **Incorporar en F5** solo en un sink nuevo `JsonLinesAuditSink` (ISO 8601 con zona, punto decimal). El CSV heredado no se toca |
| H-05 lock solo intra-proceso | **Descartar**. Exigiría `fcntl`/`msvcrt` por plataforma o una dependencia (`portalocker`), y hoy no hay multiproceso en `bulk`/`dump`. Backlog |
| H-06 imports de privados entre módulos | **Incorporar** en F2 (rechazos) y F3 (`dump`) |
| H-07 neutralización/escape en exportadores | **Descartado tras verificar**: el Excel pasa por `safe_frame` + `neutralize_formulas` (`bulk/_audit/exporters.py:83-84,102-103`, de `_core/export_safety.py:49,60`); el HTML usa `DataFrame.to_html`, que escapa por defecto (`exporters.py:160-168`), y lo demás que sustituye la plantilla son números y fechas generados; el JSON no se interpreta como hoja de cálculo. **Riesgo residual**: el CSV de auditoría no neutraliza `tabla` (nombre del esquema del usuario); corregirlo cambiaría bytes del formato congelado, así que solo se aplica en sinks nuevos |

### 4. Estructura del paquete

```text
src/util_bbdd/audit/
  __init__.py        # solo re-exporta la API del paquete
  events.py          # AuditEvent, AuditSource, AuditStatus, AuditKind (F0)
  contracts.py       # Protocol AuditSink y AuditEventSource (F0)
  sinks.py           # NullAuditSink, MemoryAuditSink (F0); JsonLinesAuditSink (F5)
  locks.py           # path_lock(): registro único de locks por ruta (F1)
  files.py           # set_aside, aside_path, first_line, file_size, file_identity (F1, F3)
  text.py            # safe_csv_cell, one_line (quita CR/LF/tabulador) (F2)
  legacy_csv.py      # AuditRecord, AUDIT_OPERATIONS, validate_record, AuditCsvRepository, read_since (F1, F3)
  analytics.py       # AuditAnalyticsService (F1)
  exporters.py       # AuditExporters (F1)
  html_template.py   # AUDIT_HTML_TEMPLATE (F1)
  counters.py        # AuditCounters, SupportsAuditCounters (F1)
  rejects.py         # RejectsWriter, REJECT_COLUMNS (F2)
```

Adaptadores (viven en el origen, por la regla de dependencias):

```text
src/util_bbdd/migrate/_audit_events.py   # plan_events, statement_event, view_validation_events (F4)
src/util_bbdd/dump/_audit_events.py      # table/constraint/index/pk_sync → AuditEvent (F5)
src/util_bbdd/bulk/_audit/events.py      # operación bulk / partición / pk_sync → AuditEvent (F5)
```

`bulk/_audit/{record,repository,service,exporters,html_template,counters,errors}.py` y
`bulk/_support/{rejects,excel}.py` quedan como **re-exportadores** (sin lógica) para no romper imports.

### 5. Capa y cambios de arquitectura

- **Capa 3** (Level 2 · Servicios, junto a `results/` y `validators/`). `audit/` importa solo de `_core`
  (capa 1), pandas, openpyxl y la stdlib. Es un servicio transversal sin dependencias de la librería; en
  capa 3 lo pueden usar en el futuro `connection`/`query` (4) o `executors`/`metadata` (5) sin moverlo.
- **Alternativa descartada: capa 5.** También funciona para `bulk`, `migrate` y `dump`, pero impediría
  auditar desde `executors`/`factory`/`metadata` sin otra reubicación, y no aporta nada.
- `scripts/gen_arquitectura_capas.py`: `LAYER["audit"] = 3`; `DRAWN` añade `("bulk","audit")`,
  `("dump","audit")` (F1/F3) y `("migrate","audit")` (F4). Se actualiza en la fase que crea cada arista
  (el script falla si el dibujo no coincide).
- `.ai/architecture.md` § Capas: fila 3 → `results/`, `validators/`, `audit/`. Árbol de Level 2: `audit/`.
- Guardas: `tests/unit/test_architecture_import_rules.py` y un test nuevo que comprueba que nada en
  `audit/` importa `util_bbdd.bulk|dump|migrate` (tampoco bajo `TYPE_CHECKING` ni de forma perezosa).

### 6. Contratos (firmas tipadas)

```python
# audit/events.py
AuditSource = Literal["bulk", "dump", "migrate"]
AuditStatus = Literal["ok", "failed", "skipped", "rejected", "info", "warning", "error"]
AuditKind = Literal[
    "operation", "partition", "reject", "run", "table", "constraint", "index",
    "pk_sync", "plan_warning", "statement", "view_validation",
]
AttributeValue = str | int | float | bool | None

@dataclass(frozen=True, slots=True)
class AuditEvent:
    source: AuditSource
    kind: AuditKind
    status: AuditStatus
    timestamp: datetime                      # con zona (UTC); __post_init__ rechaza naive
    engine: str | None = None                # db.system.name
    namespace: str | None = None             # db.namespace (esquema)
    target: str | None = None                # db.collection.name / objeto (tabla, vista, constraint…)
    operation: str | None = None             # db.operation.name (INSERT, UPDATE, DELETE, CREATE, ENABLE…)
    rows: int | None = None                  # filas ENVIADAS (INV-BLK-04); ≠ db.response.returned_rows
    elapsed_s: float | None = None
    error_type: str | None = None            # error.type (nombre de la clase)
    message: str | None = None               # texto libre, una línea, truncado
    run_id: str | None = None                # correlación (H-02)
    parent_id: str | None = None
    attributes: tuple[tuple[str, AttributeValue], ...] = ()   # inmutable y hashable

    @classmethod
    def now(cls, **fields: Any) -> AuditEvent: ...   # timestamp = datetime.now(UTC)

# audit/contracts.py
@runtime_checkable
class AuditSink(Protocol):
    def write(self, events: Sequence[AuditEvent]) -> None: ...   # atómico por llamada; thread-safe
    def close(self) -> None: ...

class AuditEventSource(Protocol):           # lectura para tests y resúmenes
    def events(self) -> Sequence[AuditEvent]: ...

# audit/sinks.py
class NullAuditSink:     # write/close no hacen nada
class MemoryAuditSink:   # lista protegida con lock; events() devuelve copia (también AuditEventSource)
class JsonLinesAuditSink:  # F5: UTF-8, una línea JSON por evento, lock por ruta, set_aside si no es JSONL

# audit/locks.py
def path_lock(path: Path) -> threading.Lock: ...    # = _get_file_lock actual, misma normalización

# audit/legacy_csv.py
AUDIT_OPERATIONS: tuple[str, ...]
@dataclass(frozen=True, slots=True) class AuditRecord: ...             # sin cambios
def validate_record(tabla, motor, operacion, rowcount, elapsed) -> None  # mensajes actuales
class AuditCsvRepository: ...                                           # se mueve tal cual
def read_since(path: Path, start_offset: int | None) -> pd.DataFrame     # = dump.read_audit_csv
```

Equivalencia con OpenTelemetry (sin depender de su SDK): `engine`↔`db.system.name`,
`namespace`↔`db.namespace`, `target`↔`db.collection.name`, `operation`↔`db.operation.name`,
`attributes["batch_size"]`↔`db.operation.batch.size`, `error_type`↔`error.type`. `rows` **no** equivale a
`db.response.returned_rows` (son filas enviadas). `db.query.text` no se registra (§ 7).

Decisión: `AuditEvent` **no** sustituye a `AuditRecord`. El CSV heredado sigue escribiendo `AuditRecord`
con su formato; un evento `operation` se emite además solo si hay un `AuditSink` configurado (F5). Así
F1–F4 no cambian ni un byte ni el coste de la ruta actual.

### 7. Seguridad (diseño)

- Ningún evento lleva `conn_params`, URL ni credenciales. Test: un evento construido desde una operación
  con contraseña en `conn_params` no la contiene al serializarse.
- `message` pasa por `one_line()` (sin CR/LF/tabulador) y se trunca (500 caracteres). Los mensajes de
  `IntegrityError` pueden contener valores de clave (PII): en eventos `reject`/`failed`, `error_type`
  siempre y `message` solo en sinks que el usuario configura de forma explícita; se documenta.
- Valores de filas: solo en el CSV de rechazos con ruta explícita (INV-REJ-01, sin cambios).
- `safe_csv_cell` en todo sink tabular nuevo; los exportadores Excel siguen con `_core/export_safety`.
- SQL: no se registra. Para `migrate` solo la primera línea útil de la sentencia (DDL generado, sin datos
  de filas), truncada a 120, como ya hace el mensaje de error.
- Un fallo de un sink opt-in nunca aborta la operación de negocio: se registra como ERROR y se cuenta
  (`audit_failures`), igual que `audit_strict=False`. Con `audit_strict=True` se propaga (misma semántica).

### 8. Tests

- **F0**: contrato de `AuditSink` con sustitución (Null, Memory) parametrizado; `AuditEvent` inmutable,
  rechaza timestamp sin zona, `attributes` hashable; `Protocol` en `tests/unit/test_protocol_conformance.py`;
  guarda de imports de `audit/`.
- **F0 (preparación de F1)**: fichero de referencia `tests/fixtures/audit/legacy_v0_28_0.csv` generado con
  v0.28.0 (operaciones fijas, `timestamp` fijado) y su test; debe pasar antes y después de F1.
- **F1**: identidad del registro de locks (`bulk._audit.repository._get_file_lock is audit.locks.path_lock`);
  concurrencia (N hilos, misma ruta, mismo fichero desde `bulk` y desde `audit`); CSV byte a byte.
- **F2**: rechazos con cabecera ajena y fórmulas, desde `bulk` y desde `audit`.
- **F3**: `tests/unit/dump/test_audit_summary_offset.py` sin cambios.
- **F4**: eventos `plan_warning` (severidad → `status`), `statement` ok/failed en SQLite en memoria, plan
  bloqueado; `execute` sin `audit_sink` idéntico a hoy.
- **F5**: invariante de conciliación de `ParallelLoadResult` comprobada contra `MemoryAuditSink`; `run_id`
  común en un volcado; JSONL legible línea a línea; fallo del sink no aborta.
- **Tests existentes que hay que cambiar** (solo destinos de `patch` a rutas privadas):
  - `tests/unit/test_audit_subsystem.py:225` — `patch("util_bbdd.bulk._audit.repository._get_file_lock", wraps=…)`:
    con el código movido, el espía no intercepta. Nuevo destino: `util_bbdd.audit.legacy_csv.path_lock`.
  - `tests/unit/test_audit_subsystem.py:276` — `patch("util_bbdd.bulk._audit.repository.pd.read_csv")`: el
    destino deja de existir si el re-exportador no importa pandas. Nuevo destino: `util_bbdd.audit.legacy_csv.pd.read_csv`.
  - El resto (`test_audit_subsystem.py:14-21,237`, `test_audit_threadsafe.py:9`,
    `test_audit_error_handling.py:20`, `test_parallel_loader_audit_fidelity.py:28`,
    `test_on_error_isolate.py:26`) funciona por los re-exportadores y `AuditManager._repository` se conserva.

### 9. Plan de fases (cada una con la suite verde y su commit)

| Fase | Contenido | Cambio visible | Commit |
|---|---|---|---|
| **F0** núcleo | `audit/` con `events`, `contracts`, `sinks` (Null, Memory); `LAYER`; `.ai/architecture.md`; fixture CSV de referencia; microbenchmark de línea base de `AuditManager.registrar_operacion` y `_registrar_lote` | Ninguno (paquete nuevo sin consumidores) | `feat(audit): núcleo del módulo de auditoría (AuditEvent, AuditSink)` |
| **F1** `bulk` | Mover `locks`, `files`, `legacy_csv`, `analytics`, `exporters`, `html_template`, `counters` a `audit/`; `bulk/_audit/*` → re-exportadores; `AuditManager` → fachada; 2 tests con `patch` actualizados | Ninguno | `refactor(audit): la auditoría CSV de bulk pasa a util_bbdd.audit` |
| **F2** rechazos | `RejectsWriter`, `REJECT_COLUMNS`, `safe_csv_cell` → `audit/rejects.py`, `audit/text.py`; `bulk/_support/rejects.py` conserva `Isolator` y re-exporta | Ninguno | `refactor(audit): CSV de rechazos en util_bbdd.audit` |
| **F3** `dump` | `read_since`, `file_size`, `file_identity` desde `audit`; `dump` deja de importar privados de `bulk` | Ninguno | `refactor(dump): resumen de auditoría con util_bbdd.audit` |
| **F4** `migrate` | `migrate/_audit_events.py`; `MigrationPlan.execute(..., *, audit_sink=None)` | Parámetro opt-in nuevo | `feat(migrate): rastro de auditoría opcional de MigrationPlan.execute` |
| **F5** capacidades + docs | `audit_sink` opt-in en `BulkCrud`, `ParallelBulkLoader`, `DumpConfig`; `run_id`/`parent_id`; adaptadores de `bulk` y `dump`; `JsonLinesAuditSink`; exports en la API raíz; ADR definitivo; docs | Parámetros opt-in nuevos | `feat(audit): sinks opcionales con correlación para bulk y dump` |

F1–F3 son `refactor` (solo mueven código, sin cambio funcional). Si se prefiere, F2 y F3 pueden fusionarse con F1.

### 10. Borrador de ADR (`docs/adr/ADR-002-modulo-auditoria.md`, se crea en F0)

1. **Contexto y problema**: la auditoría vive en `bulk/_audit` y `bulk/_support/rejects.py`; `dump` la consume
   importando privados de `bulk`; `migrate` no deja rastro; cada módulo describe lo ocurrido con tipos
   distintos y sin correlación.
2. **Decisión**: paquete `util_bbdd.audit` en capa 3 con un modelo de evento (`AuditEvent`), un contrato de
   destino (`AuditSink`) y la persistencia CSV actual congelada como `legacy_csv`. Los módulos de origen
   adaptan sus tipos a eventos (el paquete no conoce a sus consumidores). Capacidades nuevas solo opt-in.
3. **Consecuencias**: + un punto canónico, sin imports privados entre módulos, `migrate` auditable,
   eventos comparables entre módulos; − re-exportadores a mantener hasta una versión mayor, dos formatos
   (CSV heredado y JSONL), 2 tests cambian el destino de `patch`.
4. **Alternativas consideradas**: (a) dejarlo en `bulk` y que `migrate` importe de `bulk` — misma capa 6,
   prohibido por la Regla #6; (b) sustituir el CSV por eventos — rompe el formato y `dump`; (c) adoptar el
   SDK de OpenTelemetry — dependencia nueva y fuera de alcance; (d) capa 5 — ver § 5.
5. **Estado**: Propuesto (2026-10-02).

### 11. Referencias externas consultadas

- <https://opentelemetry.io/docs/specs/semconv/database/database-spans/> (atributos y estabilidad; saneado de `db.query.text`)
- <https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html> (qué registrar y qué excluir; inyección CR/LF)
- <https://owasp.org/www-community/attacks/CSV_Injection>

### 12. Riesgos (resumen; detalle en AUDIT_PLAN)

Dos registros de locks por error (corrupción del CSV con hilos), cambio de nombre de loggers al mover código,
desfase de bytes del CSV, aumento de alcance de F5.

---

## AUDIT_PLAN

### Riesgos funcionales

- **Semántica de contadores y conciliación** (INV-BLK-14/15/17): F1–F3 no tocan `persistence.py` ni el
  loader; el riesgo aparece en F5 al emitir eventos además del CSV. Mitigación: el evento se emite en el
  mismo punto que `register_operation` (`bulk/_support/persistence.py:134`) y con el mismo `rowcount`;
  test de la invariante contra `MemoryAuditSink`.
- **Auditoría diferida** (INV-BLK-13): en F5, los eventos de sesión deben seguir la misma regla
  (se emiten al confirmar el commit; con `audit_strict`, antes). Si no, el sink diría «ok» de algo deshecho.
  Condición de diseño para F5.
- **Timestamp**: `AuditRecord.timestamp` es naive local; `AuditEvent` es UTC. No se mezclan (formatos
  distintos); el adaptador convierte con `astimezone(UTC)`.

### Riesgos técnicos

- **Registro de locks duplicado** (crítico si ocurre): si `bulk` y `audit` tuvieran cada uno su `_FILE_LOCKS`,
  dos hilos obtendrían locks distintos para el mismo CSV. Mitigación: el re-exportador no define nada,
  solo `from ...audit.locks import path_lock as _get_file_lock`; test de identidad (§ 8).
- **Nombres de logger**: el código movido usa el logger que recibe por inyección (repository, analytics,
  exporters ya lo hacen) y los que tienen logger de módulo lo fijan con su nombre actual
  (`util_bbdd.bulk._support.rejects`; `util_bbdd.dump.orchestrator` ya está fijado en `dump/_audit_summary.py`).
- **Regla #6**: `audit` en capa 3 no puede importar `results`/`validators` (misma capa); no los necesita.
- **LSP de los sinks**: el test de contrato parametrizado (Null, Memory, JSONL) fija `write` atómico por
  llamada, idempotencia de `close` y thread-safety.
- **sync/async**: no hay código async en los tres consumidores; los sinks son síncronos. Si en el futuro se
  audita desde `AsyncDatabaseManager`, se hará con `asyncio.to_thread`; fuera de alcance.
- **ISP**: escritura (`AuditSink`) y lectura (`AuditEventSource`) separadas; el CSV heredado mantiene su
  propia interfaz (`AuditCsvRepository`) porque la lectura devuelve `DataFrame`, no eventos.

### Riesgos de seguridad (revisión con criterio de Security Reviewer)

- **PII en mensajes de error** (medio): `IntegrityError` incluye valores de clave. Mitigación de § 7
  (`error_type` siempre; `message` solo en sinks explícitos, una línea, truncado) y advertencia en la doc.
- **Inyección en ficheros** (bajo): CR/LF/tabulador eliminados en texto libre; `safe_csv_cell` en sinks tabulares.
- **Residual aceptado**: el CSV heredado no neutraliza `tabla` (H-07); cambiarlo rompe el formato congelado.
- **Credenciales** (bajo): los eventos no tienen campo para ellas y no se construyen desde `conn_params`; test.
- Sin críticos. Nada bloquea.

### Riesgos de compatibilidad

- Imports públicos y privados usados por tests: cubiertos por re-exportadores; 2 destinos de `patch`
  cambian (§ 8).
- Formato CSV: test byte a byte con fixture de v0.28.0 antes de mover nada.
- Mensajes de log exactos fijados por tests (`test_audit_subsystem.py:413-416`): siguen en la fachada.
- Pickling/multiproceso: no aplica (no se usa en `bulk`/`dump`).
- API raíz: solo adiciones en F5.

### Coste de rendimiento

- F1–F4: misma ruta de escritura, con una llamada más de la fachada al repositorio movido (ya lo hacía).
  Es por **operación**, no por fila: < 1 µs frente a milisegundos de cada lote. Se mide con el
  microbenchmark de F0 (umbral ≤ 5 %).
- F5 sin sink: un `if sink is None` por operación. Con `MemoryAuditSink`/`JsonLinesAuditSink`: una
  construcción de evento y una escritura por operación; se mide en F5 y se documenta.

### Simplificaciones posibles

1. Fusionar F1, F2 y F3 en un solo `refactor(audit)` (menos commits; diff mayor).
2. Dejar `analytics`/`exporters` en `bulk`: solo los usa `AuditManager`. **No recomendado**: el objetivo es
   centralizar, y son la parte de lectura del mismo CSV.
3. Aplazar `JsonLinesAuditSink` (H-04) si nadie lo necesita aún: F5 quedaría con correlación y adaptadores
   sobre `MemoryAuditSink` y sinks del usuario.
4. Prescindir de `AuditEventSource` y leer `MemoryAuditSink.events` directamente (un `Protocol` menos).

### Veredicto: **GO_CONDICIONAL**

Condiciones:

1. **C1** — Aprobar el nombre `util_bbdd.audit` y la **capa 3**.
2. **C2** — Aceptar el cambio de los 2 destinos de `patch` de `tests/unit/test_audit_subsystem.py` (§ 8).
3. **C3** — Decidir el alcance de F5: completo, sin JSONL (simplificación 3) o aplazado.
4. **C4** — El fixture CSV de referencia y el microbenchmark se hacen en F0, **antes** de mover código (F1).
5. **C5** — Indicar qué fases se aprueban para IMPLEMENT (recomendado: F0 y F1 en la primera iteración).
