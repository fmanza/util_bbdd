# TRACEABILITY

## Session metadata
- id: 2026-09-24-refactor-p09-update-columns
- fecha: 2026-09-24
- rama: develop
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
Mejoras menores de la auditoría: P-06, P-07, P-08, P-09, P-10 y P-13, más el comportamiento de SQLAlchemy que figura en "Known issues" del CHANGELOG.
```
(Tras el cierre de `v0.12.0`. Primer bloque del orden propuesto: P-09 + la parte rápida de P-07.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-07, P-09) y `02_BASELINE_MOTORES_REALES.md`
- `src/util_bbdd/bulk/crud.py` (`__prepare_update_operation`, `__run_bulk_pipeline`, `bulk_insert_from_chunks`), `_support/validation.py` (`build_update_plan`, `normalize_dataframe_columns`)

## AI output summary
- **P-09**: `__prepare_update_operation` convierte `df[pk_cols + update_cols]` en lugar del DataFrame completo. Las columnas que no están en la tabla no se usaban ni en el UPDATE, ni en el staging, ni en el SQL generado.
- **P-07 (parcial)**: `df.copy()` → `df.copy(deep=False)` en `__run_bulk_pipeline` y `bulk_insert_from_chunks`. El DataFrame de trabajo solo se renombra (`df.columns = ...`), que no se propaga a una copia superficial con Copy-on-Write (pandas 3). El resto de P-07 (preparar y ejecutar por bloques) queda para su propio refactor.
- **Medición** (`scratchpad/p09_bench.py`, 100K filas, mejor de 5):
  - preparación del UPDATE con 3 columnas útiles + 7 sobrantes: 0,295 s → 0,096 s (3,1×);
  - pico de memoria de la copia: 14,4 MB → ~0 MB.
- **Tests**: `tests/unit/bulk/test_update_columns.py` (3):
  - solo se convierten PK + columnas actualizables (falla sin el cambio);
  - el SQL generado ignora las columnas sobrantes y se ejecuta;
  - el DataFrame del llamador no cambia tras INSERT, UPDATE y `bulk_insert_from_chunks` con renombrado a minúsculas.
- **Validación**:
  - `ruff check src tests` y `mypy src tests/unit/test_protocol_conformance.py` limpios;
  - suite 4561 passed / 68 skipped;
  - integración 6 motores 52 passed / 20 skipped, igual que antes.
- **Hallazgos nuevos** (previos a este cambio, reproducidos en SQLite y registrados en `02_BASELINE_MOTORES_REALES.md`):
  - **P-25**: una columna real llamada `pk_<PK>` recibe el valor de la PK en el UPDATE (corrupción silenciosa).
  - **P-26**: `bulk_delete_from_df` abre su propia transacción dentro de `bulk_session` (`database is locked` en SQLite).

## AUDIT_CODE
- Regresiones potenciales:
  - con columnas duplicadas tras normalizar el case, `df[lista]` devuelve las duplicadas como antes;
  - las columnas sobrantes con tipos que la normalización no admite ya no provocan error (antes sí): cambio benigno.
- Contratos públicos: sin cambios de firma ni de resultado.
- Cobertura: preservada; 3 tests nuevos.
- Tipado: sin cambios.

## Directrices para Futuras IAs
- **[bulk/UPDATE]**: el alias del WHERE (`pk_<col>`) comparte espacio de nombres con las columnas de la tabla (P-25). Al tocar `build_update_plan`, elegir un alias que no pueda colisionar.
- **[pandas]**: con Copy-on-Write basta `copy(deep=False)` cuando solo se renombran columnas; si algún paso llega a asignar valores en el DataFrame de trabajo, sigue siendo seguro (CoW copia al escribir).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- Siguientes del bloque: P-13, P-10, P-06 + observación de SQLAlchemy, P-07 (bloques), P-08; nuevos P-25 y P-26.
