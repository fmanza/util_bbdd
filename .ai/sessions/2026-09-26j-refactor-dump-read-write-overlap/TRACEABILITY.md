# TRACEABILITY

## Session metadata
- id: 2026-09-26j-refactor-dump-read-write-overlap
- fecha: 2026-09-26
- rama: develop (base `55699d0`)
- skill: refactor (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION); mejora de rendimiento sin cambio funcional
- origen: Q3 / paso 1.3 del roadmap `2026-09-25b-performance-audit-dump-delta` (PF-03 de la auditoría `2026-09-25-performance-audit-dump`)

## Prompt issued
```
/refactor Q3: solapar lectura y escritura en la carga de tabla entera de dump (hilo lector con cola acotada de 2
chunks). Sin cambios de API ni de resultado; propagar errores del lector; cerrar el hilo si falla la escritura sin dejar
la conexión de lectura en uso por otro hilo; decidir por motor de origen con medición (Oracle tras Q1; SQLite no);
A/B intercalado en los 6 motores.
```

## PLAN / AUDIT_PLAN
- `_prefetch(items, depth=2)` (generador de módulo): un hilo `dump-prefetch` consume el iterador de chunks (fetch + DataFrame + renombrado) y los deja en una `queue.Queue(maxsize=2)`; el hilo principal escribe.
- Correctitud:
  - orden: un solo lector y cola FIFO → mismo orden;
  - error del lector: se guarda y se relanza en el consumidor tras los elementos previos (el `except` de `_load_whole_table` lo trata como hoy);
  - fallo al escribir: `bulk_insert_from_chunks` deja de iterar y el generador se cierra; el `finally` activa `stop` y hace `join()` **sin timeout**, así la conexión de lectura no se cierra mientras el lector la usa;
  - memoria: +2 chunks.
- Una conexión, un hilo a la vez: el lector usa la de lectura; el principal solo la cierra tras el `join`. La transacción de escritura, la auditoría y el `BulkCrud` siguen en el hilo principal.
- Motores de origen (`_PREFETCH_SOURCE_DIALECTS`): PostgreSQL, MySQL, MariaDB, SQL Server, Oracle. SQLite como origen no: su conexión no admite otro hilo (`check_same_thread`).
- Solo en la carga de tabla entera; los rangos de PK ya leen en paralelo.

## IMPLEMENT
- `dump/orchestrator.py`: `_prefetch` (nuevo, genérico PEP 695), constantes `_PREFETCH_SOURCE_DIALECTS` y `_PREFETCH_DEPTH`; `_load_whole_table` envuelve el iterador renombrado si el origen está en la lista.
- `scripts/bench_dump.py`: se retiran el prototipo `prefetch()` y la copia de `_load_whole_table` que instalaba (tras Q3 habría medido código antiguo), la variante `prefetch` y la opción en `combo`, `stream_c20k` (antes `stream_c20k_prefetch`) y `arraysize_prefetch`.
- Guías (`docs/PERFORMANCE_AUDIT_GUIDE.md`, `.claude/performance-audit-guide.md`): tabla de variantes al día; `stream` y `arraysize` equivalen ya a `baseline`.

## Validación
- **Tests** (`tests/unit/dump/test_prefetch.py`, nuevo, 8): orden y completitud; origen vacío; error del lector tras los elementos previos; el consumidor que se detiene (`close()`, lo que pasa al fallar la escritura) termina el hilo y no lee más allá del búfer (≤ 5 elementos de 1000); excepción del consumidor → hilo terminado; `_load_whole_table` lo usa con origen PostgreSQL/Oracle y no con SQLite. Ningún hilo `dump-prefetch` vivo tras cada test.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src` limpio; `pytest tests/unit`: **4552 passed**; `mkdocs build --strict` sin errores.
- **A/B intercalado** (`large`, 3,5M filas, 2 repeticiones por lado; `ab_antes/`, `ab_despues/`):

| Motor | Sin Q3 | Con Q3 | Δ media | RSS pico | Verificación + identidad |
|---|---|---|---|---|---|
| PostgreSQL | 17,5 · 17,1 s | 14,7 · 14,8 s | **−15 %** | 168 → 170 MB | 2/2 |
| MySQL | 54,5 · 53,4 s | 37,6 · 38,4 s | **−29 %** | 159 → 162 MB | 2/2 |
| MariaDB | 50,7 · 49,4 s | 37,5 · 37,6 s | **−25 %** | 160 → 162 MB | 2/2 |
| SQL Server | 79,7 · 65,8 s | 63,7 · 56,5 s | **−17 %** (−14 % con la mejor de cada lado) | 161 → 166 MB | 2/2 |
| Oracle | 35,6 · 38,9 s | 34,4 · 37,4 s | −3 % | 170 → 174 MB | 2/2 |
| SQLite (origen PG) | 21,0 · 21,4 s | 19,7 · 19,8 s | −7 % | 172 → 175 MB | 2/2 |

- **Oracle**: se mantiene activo. Tras Q1 su lectura ya es corta (5–9 s) y el solape apenas aporta, pero no empeora (el prototipo empeoraba antes de Q1).
- **PostgreSQL**: el +1 s de Q2 (cursor de servidor) queda más que compensado: 16,0 s (antes de Q2) → 14,75 s.

## AUDIT_CODE
- **API pública**: sin cambios. **Resultados**: mismas filas (verificación y sonda de identidad en las 12 mediciones «después»).
- **Hilos**: el lector es `daemon`, pero siempre se espera con `join()`; ningún test deja hilos vivos.
- **Bloqueo**: el `join()` sin timeout espera, como mucho, a que termine el `fetchmany` en curso (un chunk); un origen colgado ya colgaba la lectura antes.
- **MySQL/MariaDB**: si se abandona la lectura (fallo al escribir), cerrar la conexión drena el cursor de servidor (Q2); solo en el camino de error.
- **Tipado**: `_prefetch[T]` genérico; `renamed` anotado como `Iterator[pd.DataFrame]`.

## VERSION
- Commit: `refactor(dump): solapar la lectura del origen con la escritura (Q3)`
- Changelog: `[Unreleased]` → *Changed* (rendimiento).
- Impacto en API pública: ninguno.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump]**: la carga de tabla entera lee en el hilo `dump-prefetch`. Todo lo que ocurra al iterar los chunks (lectura, construcción del DataFrame, renombrado) corre en ese hilo; la escritura, la transacción y la auditoría, en el principal. No uses la conexión de lectura desde el hilo principal mientras el generador esté vivo.
- **[dump/sqlite]**: SQLite como origen no usa el solape (`check_same_thread`).
- **[bench]**: el solape ya no es una variante del banco; para medir sin él, compara con un commit anterior (A/B con `git stash`).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Fase 1: Q4 (guía por motor de `parallel_pk_ranges` y aviso en MySQL/MariaDB).
