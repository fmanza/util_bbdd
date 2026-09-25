# TRACEABILITY

## Session metadata
- id: 2026-09-26g-refactor-dump-oracle-arraysize
- fecha: 2026-09-26
- rama: develop (base `099fed0`)
- skill: refactor (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION); mejora de rendimiento sin cambio funcional
- origen: Q1 / paso 1.1 del roadmap `2026-09-25b-performance-audit-dump-delta` (PF-01 de la auditoría `2026-09-25-performance-audit-dump`)

## Prompt issued
```
/refactor Q1: arraysize = chunk_size en las lecturas de dump desde Oracle. oracledb lee con arraysize=100 si el engine
no lo fija. Sin cambios de API ni de resultado, sin tocar el engine del usuario; medir A/B intercalado (Oracle large ×2);
no empeorar otros motores.
```

## PLAN / AUDIT_PLAN
- SQLAlchemy 2.0.50 solo admite `arraysize` a nivel de engine (`create_engine(arraysize=…)` → `dialect.arraysize`); no hay opción por sentencia.
- Mecanismo elegido: listener `before_cursor_execute` registrado en el **`Connection`** que abre `dump` para la lectura (SQLAlchemy admite eventos por conexión), solo mientras se crea el cursor, y retirado en `finally`. Solo **sube** `arraysize` (y `prefetchrows`) a `chunk_size`; si el engine ya pide más, no lo toca.
- Verificado en Oracle 23 Free antes de implementar: valores por defecto del cursor `(arraysize=100, prefetchrows=2)`; lectura de 2M filas 11,7 → 2,5 s; tras retirar el listener, el engine no lo conserva (`event.contains` = False) y otra conexión vuelve a 100.
- Riesgos: ninguno en resultados (mismas filas); memoria: una ida y vuelta de `chunk_size` filas, lo mismo que un chunk.

## IMPLEMENT
- `dump/orchestrator.py`: `_execute_read(conn, sql, chunk_size, params)` (nuevo), usado por `_read_chunks`. En dialectos distintos de Oracle es `conn.execute(text(sql), params)` sin más.
- Punto único: cubre la carga de tabla entera y los lectores de `_load_in_pk_ranges`.

## Validación
- **Tests** (`tests/unit/dump/test_dump_fidelity.py::TestOracleArraysize`, 3): listener en la conexión y retirado tras ejecutar; sube 100 → 5000 (y `prefetchrows`) y no baja un valor mayor; se retira aunque falle la ejecución; otros dialectos no registran nada.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src` limpio; `pytest tests/unit`: **4539 passed**.
- **Oracle real, A/B intercalado** (`large`, 3,5M filas; `ab_antes/`, `ab_despues/`):

| | Total | `read` | `write` | RSS pico | Verificación |
|---|---|---|---|---|---|
| Sin Q1 | 63,0 · 54,1 s | 26,5 · 22,2 s | 30,7 · 26,9 s | 170 MB | 2/2 |
| Con Q1 | **47,8 · 34,9 s** | **8,9 · 5,4 s** | 32,2 · 24,9 s | 171 MB | 2/2 |

  Media 58,6 → 41,4 s (**−29 %**), igual que en la auditoría (−29 %, mediana de 3). La auditoría previa marcaba 67,0 → 47,7 s; la línea base actual ya es menor por PD-05 (lectura exacta más rápida).
- **Otros motores**: el código solo cambia con dialecto Oracle (test `test_other_dialects_do_not_register_listener`); no se re-midieron.
- **`ranges4` + Q1 en Oracle** (1 repetición): 32,9 s y datos verificados; ya no empeora frente a `arraysize` solo, como pasaba en el prototipo de la auditoría. La **sonda de identidad falla**: ver hallazgo PD-11.

## Hallazgo nuevo: PD-11 (fuera del alcance de este refactor)
- Con `parallel_pk_ranges > 1` y `max_parallel_tables = 1`, las tablas cargadas por rangos pasan por `ParallelBulkLoader` (sus propias `BulkCrud`) y la `BulkCrud` principal no las refleja; `_sync_pk_sequences` no encuentra nada (`pk_sync = []`) y en Oracle/PostgreSQL el siguiente INSERT sin PK choca (`ORA-00001`). La ruta `max_parallel_tables > 1` sí llama a `_reflect_loaded_tables`; la secuencial con rangos no. Preexistente; se corrige en su propio hotfix.

## AUDIT_CODE
- **API pública**: sin cambios.
- **Engine del usuario**: intacto (listener por conexión, retirado en `finally`; verificado en Oracle real).
- **`arraysize` del usuario**: si ya es mayor que `chunk_size`, se respeta (test).
- **Drivers**: `prefetchrows` solo si el cursor lo tiene (`hasattr`), por compatibilidad con cx_Oracle antiguos.
- **Concurrencia**: cada lector de rangos abre su propia conexión; el listener es de esa conexión.

## VERSION
- Commit: `refactor(dump): leer de Oracle con arraysize = chunk_size (Q1)`
- Changelog: `[Unreleased]` → *Changed* (rendimiento).
- Impacto en API pública: ninguno.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump/oracle]**: el `arraysize` de lectura se fija por conexión en `_execute_read`; no hace falta `create_engine(arraysize=…)`. No lo cambies a nivel de engine: afectaría al resto de la aplicación del usuario.
- **[bench]**: la variante `arraysize` del banco fija el `arraysize` del engine de origen; tras Q1 debería dar lo mismo que `baseline` en Oracle.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- PD-11 (PK sync con `parallel_pk_ranges` en la ruta secuencial).
- Fase 1: Q2 (`stream_results`), Q3 (solape lectura/escritura), Q4 (guía de `parallel_pk_ranges`).
