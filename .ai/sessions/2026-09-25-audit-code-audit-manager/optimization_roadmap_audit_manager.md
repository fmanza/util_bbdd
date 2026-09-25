# Optimization Roadmap — `AuditManager` (bulk, Área A5)

- Origen: `audit_report_audit_manager_20260925.md` (misma carpeta) · Fecha: 2026-09-25 · Rama `develop` @ `5499828`
- Principio rector: **la traza tiene que decir la verdad antes de ser rápida**. El rendimiento no bloquea: < 1 % en motores servidor con `chunk_size=5000`.
- Restricción heredada (sesión 2026-09-23): **el formato del CSV no cambia** (7 columnas, TSV, coma decimal, `Sí/No`).

## Objetivos medibles

| Métrica | Hoy | Objetivo | Cómo se mide |
|---|---|---|---|
| Filas CSV fantasma tras un rollback | todas las de los chunks previos (R3) | **0** | test de rollback + `repro_audit.py` R3 |
| Filas CSV duplicadas por reintentos de `ParallelBulkLoader` | 1 por chunk y reintento | **0** | test de integración con `OperationalError` inyectado |
| Operación persistida que el llamador ve como fallida | sí (R2) | **no**, por defecto | test con CSV no escribible |
| µs por fila CSV (micro, Windows) | ~290 | **≤ 160** | `bench_audit.py micro` |
| Overhead en streaming, SQLite 1M, chunk 500 | 16,5 % | **< 1 %** | medición "tiempo dentro de la auditoría" |
| Overhead en streaming, SQLite 1M, chunk 5000 | 3,35 % | **< 0,5 %** | ídem |

---

## Fase 1: correcciones triviales y quick wins (≈ 3 h en total)

Sin cambio de contrato. Se pueden hacer en un solo `/hotfix` o repartir en varios.

| ID | Cambio | Fichero | Hallazgo | Esfuerzo | Impacto | Riesgo |
|---|---|---|---|---|---|---|
| QW-1 | Escribir la cabecera cuando `not exists() or st_size == 0` (dentro del lock) ✅ corregido | `_audit/repository.py:114` | H4 | 15 min | Evita que el CSV se corrompa para siempre | Nulo |
| QW-4 | `desde = dump_inicio.replace(microsecond=0)` al filtrar ✅ corregido | `dump/orchestrator.py:983` | H3 | 15 min | El resumen del volcado deja de perder operaciones | Nulo |
| QW-2 | Calcular `resolve()` + lock y hacer `mkdir` **una vez** al fijar `audit_csv_path` (también en el setter). Si `open` da `FileNotFoundError`, `mkdir` y reintentar una vez | `_audit/repository.py:27-39, 54, 109-113` | H9 | 1 h | ~−45 % µs por llamada (~290 → ~160) | Bajo |
| QW-3 | Un solo WARNING por instancia con `audit_csv_path=None`; `🟢 … registrado` y `Caché limpiado` a DEBUG | `audit.py:244, 256`; `_audit/repository.py:175` | H10 (P-11) | 30 min | −88 µs/llamada con INFO activo; logs más limpios | Nulo |
| M-3 | Guardar como texto (`data_type='s'`) las celdas que openpyxl toma por fórmula (cadenas que empiezan por `=`) ✅ corregido | `_audit/exporters.py:36-85` | H12 | 1 h | Cierra la inyección de fórmulas | Nulo |

**Tests nuevos**: CSV vacío con 1 registro da cabecera correcta · resumen del dump con la operación en el mismo segundo · la ruta se resuelve una sola vez (mock de `Path.resolve`) · directorio borrado a mitad de carga, se recrea · tabla `=HYPERLINK(...)` sale en el Excel con `data_type == 's'` · con `audit_csv_path=None`, N operaciones dan 1 WARNING.

---

## Fase 2: coherencia auditoría ↔ BD (≈ 1–1,5 días)

Arreglan H1 y H2, las dos ALTAS. M-1 también deja el coste en streaming en ≈ 0.

### M-1: buffer de auditoría por sesión, volcado tras el commit (H2 + H9)

- **Diseño**:
  - `BulkPersistenceManager` pasa a tener dos modos: *directo* (fuera de sesión, como hoy) y *diferido* (dentro de `bulk_session`).
  - En modo diferido, `register_operation` añade la fila a una lista `pending`.
  - `bulk_session` (`crud.py:885-930`), justo después de cada `conn.commit()` (final y parciales de `commit_every_n_chunks`), llama a `persistence.flush_pending()`. Nuevo método del repository `registrar_operaciones(filas)`: **un** `open`, N `writerow` y un solo lock.
  - En un rollback, `discard_pending()` con un `logger.warning("Auditoría: se descartan N registros (X filas) por rollback")`.
- **Resultado**: la traza solo refleja lo commiteado; los reintentos del loader no duplican; streaming con 1 apertura de fichero por commit.
- **Cambio observable**: el `timestamp` de cada fila pasa a ser el del commit, no el del fin del chunk. Documentarlo en el docstring de `bulk_session` y en `CHANGELOG`.
- **Esfuerzo**: 4–6 h · **Riesgo**: bajo. El formato del CSV no cambia. Hay que tocar las 3 ramas de `bulk_session`: atómica, `commit_every_n_chunks` y `atomic=False`.
- **Tests**: rollback da 0 filas CSV · `commit_every_n_chunks=2` con fallo en el chunk 5 da 4 filas CSV · sesión OK con 200 chunks da 200 filas y 1 `open` · `ParallelBulkLoader` con `OperationalError` en el primer intento da sin duplicados · DELETE dentro de la sesión (P-26) también queda diferido.

### M-2: política ante fallo de la auditoría (H1)

- **Decisión que tiene que tomar el mantenedor** (condiciona la API):
  - **Opción A (recomendada): fail-open por defecto**. Si falla la escritura: `logger.error` con los datos de la fila perdida, contador `BulkCrud.audit_failures` y sin excepción. Nuevo `BulkCrud(audit_strict: bool = False)`. Con `True` se mantiene el comportamiento actual (propagar).
  - Opción B: mantener fail-closed y documentarlo mejor. No evita que un reintento duplique datos.
- **Justificación**: la traza es un CSV externo a la transacción, así que no puede ser atómica con la BD. Si una operación ya commiteada se presenta como fallida, provoca reintentos que duplican datos, lo que es peor que perder una fila de telemetría que queda registrada en el log. OWASP *Logging Cheat Sheet* pide que un fallo del registro no provoque fallos en la aplicación, salvo requisito explícito, que es lo que cubriría `audit_strict`.
- **Esfuerzo**: 2–3 h · **Riesgo**: **cambio de comportamiento** (hoy lanza) → `CHANGELOG` + `COMPATIBILITY.md`.
- **Tests**: CSV bloqueado (directorio en su lugar o permiso denegado): la operación termina, los datos están, `audit_failures == 1` y hay ERROR en el log · con `audit_strict=True` la excepción se propaga (y dentro de sesión provoca el rollback).

### M-4: caché de lectura validada con el fichero (H6)

- Guardar `(st_mtime_ns, st_size)` al cachear e invalidar si cambian (1 `stat`, ~4 µs). El TTL queda como tope.
- Esfuerzo: 1 h · Riesgo: nulo · Test: A lee, B escribe, A ve el dato nuevo.

---

## Fase 3: contrato y deuda (≈ 2–3 h + versión mayor para L-2)

| ID | Cambio | Hallazgo | Tipo |
|---|---|---|---|
| L-1a | Docstring y docs: `total_filas` = "filas enviadas a la operación", no las afectadas | H5 | Doc |
| L-1b | `columnas_auditoria.setter`: `DeprecationWarning` ahora y retirarlo en la siguiente versión menor | H7 | Deprecación |
| L-1c | `class AuditConfigError(AuditError, ValueError)` y lanzarla en `validar_ruta` | H8 | Compatible |
| L-1d | Tipar `AuditTransaction.__exit__` (`type[BaseException] \| None`, …) | Tipado | Compatible |
| L-2 | Decidir el futuro de `AuditTransaction`: documentar que es un contador en memoria **o** retirarlo en una versión mayor | H11 | Versión mayor |
| L-3 | Corregir `.github/prompts/audit_audit_manager_bulk.prompt.md` y `.claude/commands/performance-audit-bulk.md:50` con las rutas reales (`bulk/audit.py`, `bulk/_audit/`, `bulk/_support/persistence.py`, `bulk/crud.py`) y un scope sin async/buffer/tabla | H14 | Config IA |

---

## Descartado (con motivo)

| Idea | Motivo |
|---|---|
| Logging async (`QueueHandler`/hilo de volcado) | 1 fila por chunk: la ganancia sobre M-1 es marginal y añade riesgo de perder filas si cae el proceso |
| Handle de fichero persistente | 4,4 µs frente a ~160, pero en Windows bloquea el CSV a otras herramientas y obliga a gestionar `close()`/rotación. M-1 consigue lo mismo con 1 `open` por commit |
| Auditoría en una tabla de la BD destino | DDL y permisos por motor (6 dialectos). Cambio de producto, no optimización |
| Compresión del CSV | Volumen ridículo: 1 fila (~60 B) por chunk |
| Añadir `filas_afectadas` real (`cursor.rowcount`) | No es fiable con executemany (pyodbc `fast_executemany`, psycopg). Rompería el contrato del CSV |

---

## Orden recomendado y skills

1. `/hotfix` → QW-1 + QW-4 (corrección de datos, sin riesgo).
2. `/hotfix` → M-3 (seguridad).
3. `/refactor` → QW-2 + QW-3 (rendimiento y logs, sin cambio funcional).
4. `/new-feature` → M-1 + M-2 + M-4 (cambian el comportamiento observable). **Decidir antes la opción A/B de M-2.**
5. `/refactor` → L-1 y L-3; L-2 en la siguiente versión mayor.

## Validación posterior

- `bench/bench_audit.py` + medición "tiempo dentro de la auditoría" antes y después. Objetivos en la tabla inicial.
- `bench/repro_audit.py`: R1–R7 deben dar los valores correctos. Convertirlos en tests unitarios.
- `scripts/bench_bulk.py --ops insert --engines postgresql,mysql,mariadb,mssql,oracle` con `chunk_size=500` y `5000`: confirmar la proyección multi-motor del informe.
- `python -m pytest tests/unit/test_audit_subsystem.py tests/unit/bulk/test_audit_threadsafe.py tests/unit/test_audit_excel_export.py` + suite completa.
