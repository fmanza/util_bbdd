# TRACEABILITY

## Session metadata
- id: 2026-09-26h-hotfix-dump-pk-sync-ranges
- fecha: 2026-09-26
- rama: develop (base `17e1081`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-11 (ALTA, nuevo), detectado al medir Q1 en `2026-09-26g-refactor-dump-oracle-arraysize` (variante `ranges4` en Oracle)

## Prompt issued
```
/hotfix PD-11: con parallel_pk_ranges > 1 y max_parallel_tables = 1, las tablas cargadas por rangos (ParallelBulkLoader,
con sus propias BulkCrud) no se reflejan en la BulkCrud principal; _sync_pk_sequences no encuentra nada y en
Oracle/PostgreSQL el siguiente INSERT sin PK choca. Criterios: ranges4 en Oracle y PostgreSQL: pk_sync 3×synced e
identidad OK; test.
```

## RCA
- La Fase 5a (`_sync_pk_sequences`) solo sincroniza las tablas que están en `crud._table_cache` de la `BulkCrud` principal de `run()`.
- En la ruta secuencial, la carga de tabla entera usa esa `crud` (la tabla queda en su caché). La carga por rangos de PK (`_load_in_pk_ranges` → `ParallelBulkLoader`) usa una `BulkCrud` por partición, y la principal nunca refleja la tabla.
- `run()` solo llamaba a `_reflect_loaded_tables` en la rama `max_parallel_tables > 1`. Con `parallel_pk_ranges > 1` y una tabla a la vez, `pk_sync_results` salía `None`.
- **Evidencia**: banco Oracle `large`, `ranges4`: `pk_sync = []` y sonda de identidad `ORA-00001 … DUMP_DST.CUSTOMERS (CUSTOMER_ID)`. Mismo mecanismo que PD-02, en otra ruta.

## FIX (mínimo)
- `dump/orchestrator.py::run`: `_reflect_loaded_tables(crud, table_results, src_to_dst)` pasa a ejecutarse tras las dos ramas (paralela y secuencial). Es idempotente: las tablas ya reflejadas por la carga de tabla entera salen de la caché sin ir a la BD.
- `CHANGELOG.md` (`[Unreleased]` → *Fixed*).

## Validación
- **Test**: `TestDumpOrchestratorRun::test_sequential_path_reflects_loaded_tables_for_pk_sync` (la ruta secuencial refleja las tablas cargadas). Falla sin el arreglo.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src` limpio; `pytest tests/unit`: **4540 passed**.
- **Servidores reales** (`large`, `results/`):

| Motor | Variante | Antes | Después |
|---|---|---|---|
| Oracle | `ranges4` | `pk_sync = []`, identidad `ORA-00001` | 3 × `synced`, identidad OK, datos verificados (34,7 s) |
| PostgreSQL | `ranges4` | (mismo mecanismo) | 3 × `synced`, identidad OK, datos verificados (12,3 s) |
| PostgreSQL | `baseline` | 3 × `synced` | 3 × `synced` (16,4 s; sin cambio) |

## AUDIT_CODE
- **Ruta de tabla entera**: las tablas ya están en la caché; `_reflect_loaded_tables` no consulta la BD para ellas.
- **Tablas `skipped` / `missing_target`**: `_reflect_loaded_tables` solo refleja las de estado `success`/`error`, como antes en la ruta paralela.
- **Coste**: una reflexión por tabla cargada por rangos (milisegundos, sin seguir FKs desde PD-08).
- **Compatibilidad**: sin cambios de API; `pk_sync_results` deja de ser `None` con `parallel_pk_ranges > 1`.

## VERSION
- Commit: `fix(dump): sincronizar las PK de las tablas cargadas por rangos (PD-11)`
- Changelog: una entrada en `[Unreleased]` → *Fixed*.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump]**: cualquier ruta de carga nueva que no use la `BulkCrud` principal debe dejar sus tablas en `table_results` para que `_reflect_loaded_tables` las refleje antes de la Fase 5a.
- **[bench]**: las variantes con paralelismo (`ranges*`, `max_parallel_tables`) deben revisar también la sonda de identidad, no solo el tiempo.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Fase 1: Q2 (`stream_results`), Q3 (solape lectura/escritura), Q4 (guía de `parallel_pk_ranges`).
