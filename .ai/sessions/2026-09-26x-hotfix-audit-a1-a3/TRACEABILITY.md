# TRACEABILITY

## Session metadata
- id: 2026-09-26x-hotfix-audit-a1-a3
- fecha: 2026-09-26
- rama: develop (base `5284cf5`)
- skill: hotfix
- origen: hallazgos A1 (MEDIA), A2 y A3 (BAJA) y test T1 del audit-code `2026-09-26w-audit-code-dump-bulk-v016`

## RCA
- **A1**: en `DumpOrchestrator._load_whole_table`, si `bulk_insert_from_chunks` falla, el `for` que consumía el generador no lo cierra; el `with cfg.source_engine.connect()` devolvía la conexión al pool mientras la variable local `renamed` mantenía vivo el generador de `_prefetch` (y su hilo lector) hasta que la función retornaba.
- **A2**: `ParallelBulkLoader._run_attempt` y `_load_with_maintenance` pasaban `reader()` sin cerrarlo; al fallar la escritura, la conexión de origen del lector seguía ocupada hasta la recolección.
- **A3**: `bulk.normalize._normalize_values` con `strip_strings=False` comparaba `type(value) is str`; un `numpy.str_` (subclase) pasaba por `normalize_sql_literal` y se recortaba.

## FIX (mínimo)
- `dump/orchestrator.py`: `finally` dentro del `with` que cierra el generador de chunks (`close()` si existe); para `_prefetch` eso hace `stop` + `join` del lector antes de devolver la conexión.
- `bulk/_execution/parallel_loader.py`: `_closing_iterable(iterable)` (context manager que cierra el iterable si es un generador), usado en `_run_attempt` y `_load_with_maintenance`.
- `bulk/normalize.py`: `isinstance(value, str)` en la rama `strip_strings=False`, devolviendo `str(value)`.
- `CHANGELOG.md` (`[Unreleased]` → *Fixed*); seguimiento anotado en el informe del audit-code.

## Validación
- **Tests** (`tests/unit/dump/test_failure_paths.py`, 5): T1 (la conexión de lectura se devuelve con 0 hilos lectores vivos cuando falla la escritura), `_closing_iterable` (cierra ante error; acepta iterables normales), `ParallelBulkLoader` cierra el lector al fallar la escritura, `numpy.str_` con `strip_strings=False`. **Cada uno falla sin su arreglo** (comprobado revirtiendo solo el fichero correspondiente).
- **PostgreSQL real** (`audit_prefetch_close.py`, escritura que falla por `VARCHAR(2)`): devoluciones al pool con el hilo lector vivo **1 de 7 → 0 de 7**.
- **Calidad**: `ruff` y `mypy` limpios. Con las URLs del banco: **5260 passed**; sin URLs: **5067 passed, 193 skipped**.
- Incidencia: al comprobar A2 se revirtió por error el fichero entero con `git checkout`; se restauró desde la copia hecha antes de la edición temporal (verificado: 3 apariciones de `_closing_iterable`, sin restos de la edición temporal).

## AUDIT_CODE
- **Camino de éxito**: cerrar un generador ya agotado no hace nada; sin cambio de comportamiento ni de rendimiento.
- **Camino de error**: el cierre espera, como mucho, a que termine el `fetchmany` en curso del lector (un chunk).
- **Compatibilidad**: sin cambios de API.

## VERSION
- Commit: `fix(dump,bulk): cerrar los lectores antes de devolver la conexión si falla la escritura (audit A1–A3)`
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump/bulk]**: todo generador que retenga una conexión o un hilo debe cerrarse explícitamente en el camino de error (`finally`/`closing`); un `for` interrumpido por una excepción no lo cierra.
- **[herramientas]**: para revertir una edición temporal, restaura desde una copia del fichero; `git checkout <fichero>` vuelve a HEAD y descarta también los cambios buenos sin commit.

## Veredicto final
Veredicto: CLOSED
