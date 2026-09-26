# TRACEABILITY

## Session metadata
- id: 2026-09-26p-feature-dump-write-batch-size
- fecha: 2026-09-26
- rama: develop (base `59b83ae`)
- skill: new-feature (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: Q5 / paso 2.1 del roadmap `2026-09-25b-performance-audit-dump-delta` (PF-05); medición previa en `2026-09-26o-fase2-medicion`

## Prompt issued
```
Ejecutar Fase 2
```
Decisión del usuario sobre Q5 (preguntada con los datos): **campo nuevo `DumpConfig.write_batch_size`** (frente a hacer
`chunk_size` automático por motor o solo documentar).

## Medición previa (`../2026-09-26o-fase2-medicion/`, `chunk20k` frente a `baseline`, código tras Q1–Q4)
PostgreSQL −31 % (escritura 11,1 → 7,0 s), SQL Server **+81 %**, Oracle +2 %, MySQL/MariaDB/Connector/SQLite neutros.
Un único `chunk_size` no sirve para todos los motores.

## PLAN / AUDIT_PLAN (veredicto GO)
- `DumpConfig.write_batch_size: int | None = None` (validación ≥ 1 en `__post_init__`).
  - `None`: 20 000 con destino PostgreSQL, **salvo con `commit_every_n_chunks`** (cuenta lotes de escritura; subir el lote cambiaría cada cuántas filas se confirma); `chunk_size` en el resto.
  - Entero: ese lote en todos los motores.
- La lectura sigue por `chunk_size` (el cursor de servidor de Q2 no cambia); `_rebatch` agrupa los chunks leídos hasta completar el lote (en el hilo lector del solape de Q3) y en los lectores de rangos. `BulkCrud`/`ParallelBulkLoader` reciben `chunk_size = write_batch_size`.
- Riesgos: +1 lote en memoria; coste de `pd.concat` (medido).

## IMPLEMENT
- `dump/_models.py`: campo, validación y docstrings (`chunk_size` ya no menciona `pd.read_sql`, obsoleto desde PD-05).
- `dump/orchestrator.py`: `_PG_DEFAULT_WRITE_BATCH`, `_rebatch`, `_resolve_write_batch_size`; uso en `_load_whole_table`, `_load_in_pk_ranges` y `_make_worker_crud`.
- `docs/api/dump.md`: filas `chunk_size` y `write_batch_size`.
- `CHANGELOG.md`: *Added* (campo) y *Changed* (rendimiento PostgreSQL).

## Validación
- **Tests** (`tests/unit/dump/test_write_batch.py`, 17): validación; resolución (PostgreSQL 20 000, `chunk_size` mayor se respeta, con `commit_every_n_chunks` → `chunk_size`, otros motores → `chunk_size`, valor explícito gana); `_rebatch` (agrupa, orden, resto, índice reiniciado, chunk grande sin `concat`, vacío); E2E SQLite con `write_batch_size=350` y `chunk_size=100`: 1000 filas, suma correcta.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy` limpio; `pytest tests/unit`: **4587 passed**.
- **A/B intercalado** (`large`; `ab_antes/`, `ab_despues/`):

| Motor / variante | Sin Q5 | Con Q5 | RSS pico |
|---|---|---|---|
| PostgreSQL `baseline` | 16,6 · 15,5 s | **12,6 · 12,4 s (−22 %)**, escritura 11,4 → 7,2 s | 171 → 190 MB |
| PostgreSQL `ranges4` | 12,5 · 12,1 s | 12,2 · 12,3 s (sin cambio: lo limita la lectura en paralelo) | 186 → 234 MB |
| SQL Server / MariaDB Connector | — | 69,7 s / 30,5 s (mismo código: lote = `chunk_size`) | — |
| SQLite (desde PG) | 36,5 · 20,3 s | 38,8 · 20,6 · 20,1 s | 176 MB |

  - La ganancia en PostgreSQL (−22 %) es algo menor que con `chunk20k` (−31 %) porque se lee por 5 000 y se concatena; a cambio, la lectura no cambia.
  - SQLite: la primera medición salió lenta en **las dos** versiones (36,5 s sin Q5, 38,8 s con Q5) y las siguientes, 20 s en ambas (`sqlite_antes/`, `sqlite_despues/`): efecto del entorno en la primera escritura tras una pausa, no de Q5 (con destino SQLite el lote no cambia).
  - Todas las mediciones verificadas (datos, identidad, PK sync).

## AUDIT_CODE
- **Compatibilidad**: campo aditivo; quien no lo use solo nota el cambio con destino PostgreSQL (más rápido, +20 MB). Con `commit_every_n_chunks`, sin cambio.
- **Edge cases**: `write_batch_size < chunk_size` → el ejecutor de `bulk` trocea cada chunk (ya lo hacía); chunk mayor que el lote → sin `concat`; tabla vacía → sin lotes.
- **Auditoría de `bulk`**: un registro por lote de escritura (menos registros con lotes mayores).
- **Tipado**: `int | None`; `_rebatch` sobre `Iterator[pd.DataFrame]`.

## VERSION
- Commit: `feat(dump): write_batch_size, lote de escritura separado del de lectura (Q5)`
- Impacto en API pública: campo nuevo en `DumpConfig` (opcional).
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump]**: `chunk_size` es el tamaño de lectura; el de escritura lo decide `_resolve_write_batch_size`. No subas el lote en SQL Server (+81 % con 20 000).
- **[bench]**: descarta o repite la primera medición tras una pausa (SQLite, MySQL/MariaDB): sale lenta con cualquier versión del código.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Fase 2: 2.3 (aviso `_warn_chunk_size` solo con columnas LOB/JSON) y Q6 (guía de `manage_indexes`).
