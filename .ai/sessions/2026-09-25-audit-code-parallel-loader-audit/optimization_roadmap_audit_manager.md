# Roadmap: auditoría integrada en `ParallelBulkLoader`

- Origen: `audit_report_audit_manager_20260925.md` (misma carpeta), hallazgos **PL-1 a PL-10**
- Fecha: 2026-09-25 · Rama: `develop` (`52549e9`)
- Continúa el roadmap anterior: `.ai/sessions/2026-09-25-audit-code-audit-manager/optimization_roadmap_audit_manager.md`. Ahí quedaron hechos QW-1…QW-4, M-1…M-4, L-1 y L-2.

> **Resumen.** En modo atómico (el de por defecto) la auditoría ocupa **0,08 %–0,22 %** de una carga paralela de 1M
> filas: no hay nada que optimizar. El único coste medible aparece con `commit_every_n_chunks` bajo y chunks del lector
> pequeños (**+8 % a +9 %** con N=2 y **+1 %** con N=10 en SQLite; PL-9 → M-5). El resto del roadmap trata de la
> **fidelidad de la traza** y de un defecto del loader con SQL Server. **No se proponen** logging async, hilo escritor ni
> handle persistente (ver § Descartado).

---

## Fase 1: correcciones triviales (MEDIA, BAJA e INFO), semana 1

| ID | Mejora | Hallazgo | Esfuerzo | Riesgo | Tests |
|---|---|---|---|---|---|
| **QW-1** | `_resolve_table` crea la `BulkCrud` con `enable_fast_executemany=self._enable_fast_executemany` | PL-3 | 15 min | Nulo | Engine `mssql+pyodbc` sin conexión, `reflect_table` parcheado: `dialect.fast_executemany` no cambia con `False` |
| **QW-2** | Validar `audit_csv_path` en `__init__` (crear `AuditManager(audit_csv_path)` una vez, o `parent.mkdir`) y fallar antes del pool | PL-4 | 30 min | Bajo: el error sale en el constructor y no en `load()`. `AuditConfigError` ya es `ValueError`, así que encaja con el `Raises: ValueError` del constructor | Ruta con un fichero como directorio padre: `__init__` lanza `AuditConfigError`; no se ejecuta ningún hoist |
| **QW-3** | Añadir `AuditError` a `_EXPECTED_ERRORS` y usar `_partition_error()` en la rama de reintentos agotados | PL-7, PL-8 | 15 min | Nulo (cambia solo el texto del log y de `partition_errors`) | Strict + CSV bloqueado: WARNING sin traza. Reintentos agotados: el mensaje lleva el tipo si no es un error esperado |

## Fase 2: fidelidad de la traza y coste con commits periódicos (MEDIA y BAJA), semanas 2 y 3

### M-1: no reintentar tras un COMMIT fallido con la auditoría ya escrita (PL-2)

- **Problema**: con `audit_strict=True` la auditoría de la sesión se escribe **antes** del COMMIT. Si el COMMIT falla con `OperationalError`, el loader reintenta y la traza queda duplicada con `error=None` (R2: BD 40, CSV 80).
- **Cambio**:
  1. `BulkPersistenceManager` guarda cuántos registros escribió `flush_audit_before_commit()` en la sesión actual (`_written_before_commit`) y lo pone a cero después de un commit correcto.
  2. En `BulkCrud.bulk_session`, si la salida del bloque lanza con `_written_before_commit > 0`: un `logger.error` que lista los registros escritos sin commit, y el contador se acumula en una propiedad nueva, `BulkCrud.audit_uncommitted_records`.
  3. En `ParallelBulkLoader._load_partition`, rama retriable: si `crud.audit_uncommitted_records > 0`, **no se reintenta**. Se devuelve `PartitionResult(error=...)` con un texto que dice que el CSV contiene registros de un commit fallido.
- **Alternativa más barata** (1 h): rechazar `audit_strict=True` con `max_retries > 0` en `__init__`, como se hace ya con `commit_every_n_chunks`. **No se recomienda**: quita los reintentos también ante los errores transitorios antes del COMMIT (deadlocks, timeouts), que son la mayoría y que strict ya gestiona bien.
- **Esfuerzo**: 3 h con tests · **Riesgo**: bajo (propiedad nueva; cambia solo el caso que hoy duplica).
- **Tests**: listener `commit` que falla una vez → strict: 1 intento, error en `partition_errors`, ERROR en el log y el contador vale el número de chunks. Fail-open: sin cambios (reintenta; CSV = BD).

### M-2: filas confirmadas por commits periódicos que no constan en el CSV (PL-1)

- **Problema**: con `commit_every_n_chunks`, la operación que tiene parte de sus lotes confirmados cuando otra operación posterior falla se descarta entera del CSV. El infraconteo es una limitación **aceptada y cubierta por test** (`test_audit_deferred_session.py::test_commit_in_the_middle_of_an_operation_flushes_the_previous_one`). Lo que falla es la señal: el aviso dice "sin confirmarlos" y el loader no expone el hueco (R1: BD 30, `PartitionResult.rows` 30, CSV 20, aviso de 20 filas descartadas).
- **Cambio mínimo** (2 h):
  1. En `bulk_session` (rama `commit_every_n_chunks`), al salir con excepción: `unaudited = executor.rows_committed − filas auditadas en la sesión`. Si es > 0, el WARNING lo dice ("N filas confirmadas por commits periódicos no constan en el CSV; ver `rows_committed`"), y el aviso de descarte deja de afirmar que ninguna se confirmó.
  2. Exponerlo como `BulkCrud.unaudited_committed_rows` y llevarlo a `PartitionResult` / `ParallelLoadResult`.
- **Cambio completo** (opcional, 4–6 h, ver L-1): partir la fila de auditoría en cada commit periódico.
- **Riesgo**: bajo · **Tests**: el escenario de R1 → `unaudited_committed_rows == 10`, mensaje exacto; sin fallo → 0.

### M-3: conciliación sin leer el CSV (PL-6)

- **Cambio**: `BulkPersistenceManager.audited_rows` (suma de `rowcount` escrita con éxito), `BulkCrud.audited_rows`, `PartitionResult.audited_rows` y `ParallelLoadResult.audited_rows`. Invariante documentado: con auditoría activa y sin fallos, `audited_rows == total_rows`. En otro caso la diferencia se explica con `audit_failures` y `unaudited_committed_rows`.
- **Esfuerzo**: 2 h (junto con M-2, 3 h en total) · **Riesgo**: nulo (campos nuevos con valor por defecto, al final de los dataclasses).
- **Tests**: carga OK → igualdad; fail-open con CSV bloqueado → `audited_rows == 0` y `audit_failures == n_chunks`.

### M-4: aviso "Auditoría deshabilitada" una vez por carga, no una vez por partición (PL-5)

- **Opciones** (decide el mantenedor):
  - (a) `AuditManager`: un flag de módulo para avisar **una vez por proceso**. Es simple, pero una segunda `BulkCrud` sin auditoría en otra parte de la aplicación ya no avisaría.
  - (b) **Recomendada**: parámetro interno `warn_if_disabled: bool = True` en `AuditManager`/`BulkCrud` (keyword, al final). El loader lo pasa a `False` a sus workers y emite él un único INFO por `load()`. Lo mismo en `dump._make_worker_crud`.
- **Esfuerzo**: 1 h · **Riesgo**: nulo en (b).
- **Tests**: 8 particiones sin auditoría → 0 WARNING de los workers y 1 INFO del loader.

### M-5: agrupar la escritura de lo ya confirmado con `commit_every_n_chunks` (PL-9)

- **Problema**: si el commit periódico cae en el último lote de una operación, `register_operation` la ve fuera de transacción y escribe **en el momento**. Además, el commit escribe las operaciones anteriores por separado. Con operaciones de 1 lote (chunk del lector ≤ `chunk_size`, el caso habitual con `read_sql(chunksize=…)`) salen **2 aperturas del CSV por commit**; con N=2, una por operación. Medido: 2000 aperturas y +8 % a +9 % E2E en 1M filas con N=2; 400 aperturas y +1,1 % con N=10.
- **Cambio**: separar en `BulkPersistenceManager` lo **pendiente** (`_pending`, aún sin confirmar) de lo **confirmado** (`_confirmed`):
  - en el hook de commit, `_pending` pasa a `_confirmed` sin escribir;
  - en `register_operation` fuera de transacción, el registro va a `_confirmed`;
  - `_confirmed` se escribe con una sola apertura cuando llega a un umbral (p.ej. 64 registros o 1 s desde la última escritura), al cerrar la sesión **con o sin error** y antes de lanzar;
  - en strict no cambia nada: se escribe antes de cada commit, como hoy.
- **Impacto estimado**: N=2 → de 2000 a ~32 aperturas (−98 %); el % en escritura baja de ~9 % a ≈ 0,2 %, como en el modo atómico.
- **Trade-off**: si el proceso muere (`kill -9`, corte de luz), se pierden hasta 64 registros ya confirmados en BD. Hoy se pierde como mucho la operación en curso. El umbral acota esa pérdida y el tiempo que tarda en verse la traza.
- **Esfuerzo**: 3 h con tests · **Riesgo**: bajo; el formato del CSV no cambia.
- **Tests**: N=2 con 40 operaciones → ≤ 2 aperturas y 40 filas; fallo tras el commit k → las operaciones confirmadas antes de k están en el CSV (sin regresión de R1); strict → orden sin cambios.

## Fase 3: opcional (nice-to-have), semana 4 o después

| ID | Mejora | Hallazgo | Esfuerzo | Riesgo |
|---|---|---|---|---|
| L-1 | Partir la fila de auditoría en cada commit periódico: el hook de commit escribe un registro parcial con las filas ya confirmadas de la operación en curso. Así el CSV coincide con la BD también con `commit_every_n_chunks` | PL-1 | 4–6 h | **Cambia la granularidad del CSV** (una operación puede ocupar 2 o más filas). Documentar en `COMPATIBILITY.md` |
| L-2 | Columna de correlación (`carga_id` / `particion`) en el CSV | PL-6 | 3 h + migración de lectores | **Cambia el contrato del CSV** (8 columnas). Solo si se pide conciliar por partición a partir del CSV. M-3 cubre el caso habitual sin tocarlo |

## Descartado (con motivo)

| Propuesta | Motivo |
|---|---|
| Logging async (`QueueHandler`/`QueueListener`) o hilo escritor | En modo atómico la escritura ocupa 0,08 %–0,22 % de la carga (1 apertura por partición). El caso caro (`commit_every_n_chunks` bajo) se arregla agrupando en el mismo hilo (M-5), sin un hilo extra que pueda perder filas si el proceso cae ni cola que dimensionar |
| Handle persistente por worker | En Windows bloquea el fichero a otras herramientas y complica la rotación, para ahorrar ~1 ms por partición |
| Buffer compartido entre workers | El lock por ruta ya serializa sin contención medible (4 workers: ~1 ms por escritura) |
| Tabla de auditoría en la BD destino | Fuera del alcance de la librería: DDL y permisos distintos en 6 motores. Lo mismo concluyó el roadmap anterior |
| Compresión | Una fila de ~60 B por chunk: no hay volumen que comprimir |

## Orden recomendado

1. QW-1 (defecto real en SQL Server, trivial).
2. QW-2 y QW-3.
3. M-1 (la única vía por la que la traza puede **sobrecontar** filas hoy).
4. M-2 + M-3 juntos (comparten la contabilidad de filas auditadas).
5. M-5 (rendimiento; conviene hacerlo después de M-2, porque toca el mismo punto de `BulkPersistenceManager`).
6. M-4.
7. L-1 / L-2 solo si hay un caso de uso de conciliación por partición.

## Métricas de éxito

- Los reproductores R1–R5 (`bench/repro_loader_audit.py`) convertidos en tests unitarios y en verde.
- R2 strict: CSV ≤ BD en todos los caminos (nunca más filas en el CSV que en la BD).
- R1: `total_rows == audited_rows + unaudited_committed_rows` (con `audit_failures == 0`).
- `bench/bench_loader_audit.py`: en modo atómico el % en escritura CSV sigue ≤ 0,25 % en 1M filas tras M-1…M-3; con `commit_every_n_chunks=2` baja de ~9 % a ≤ 0,5 % tras M-5.
- Relanzar el banco en PostgreSQL y MariaDB, que no se midieron (ver informe), para confirmar la proyección.
- `ruff`, `mypy`, `pytest tests/unit` y `mkdocs build --strict` limpios. Entrada en `CHANGELOG.md` para QW-1, QW-2 y M-1…M-5.

## Rollback

Cada ID es un commit independiente: `git revert <sha>`. M-3 y M-4 solo añaden campos y parámetros con valor por defecto, así que su reversión no afecta a los llamadores que no los usen.
