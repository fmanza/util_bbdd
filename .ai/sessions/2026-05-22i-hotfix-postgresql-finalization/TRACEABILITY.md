# TRACEABILITY

## Session metadata
- id: 2026-05-22i-hotfix-postgresql-finalization
- fecha: 2026-05-22
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
> Error en producción (Python 3.14):
> `PythonFinalizationError: cannot join thread at interpreter shutdown`
> al cerrar el pool PostgreSQL durante el apagado del intérprete.
> Traceback apunta a `psycopg_pool/_acompat.py:152 → t.join(timeout)` llamado
> desde `pool_connection_postgresql.py:182 → close_method(timeout=close_timeout)`.

## Context supplied
- `src/util_bbdd/connection/postgresql/pool_connection_postgresql.py` — `PoolConnection.close()` y `_close_with_optional_timeout`
- `src/util_bbdd/connection/close.py` — `run_close_operation_sync` con guarda `sys.is_finalizing()` existente
- `src/util_bbdd/managers/_manager_lifecycle.py` — `close_resources()` (captura y loguea `PoolConnectionError`)
- `tests/unit/test_finalization_safety.py` — suite de finalization existente
- `tests/unit/test_sync_close_strict.py` — test `test_postgresql_pool_force_close_on_timeout` existente

## AI output summary
- **RCA identificado**: `run_close_operation_sync` en `close.py` detecta `sys.is_finalizing()=True` y ejecuta `action()` directamente sin crear thread propio (correcto). Sin embargo, `action()` invoca `pool_ref.close(timeout=…)` de psycopg_pool, que internamente hace `t.join(timeout)` sobre sus workers internos → `PythonFinalizationError`. La excepción (subclase `RuntimeError→Exception`) es capturada por el bloque `except Exception` de `PoolConnection.close()` y re-lanzada como `PoolConnectionError`, que el lifecycle manager registra como ERROR.
- **Fix aplicado** en `pool_connection_postgresql.py`:
  - `import sys` añadido (línea 4).
  - Early return `if sys.is_finalizing(): return` al inicio de `_close_with_optional_timeout`, antes de llamar a `pool_ref.close()`. El pool se abandona sin limpiar; el OS libera los recursos al terminar el proceso.
- **Tests añadidos** en `tests/unit/test_finalization_safety.py` — clase `TestPostgresqlPoolFinalizationSafety`:
  - `test_pool_close_skips_psycopg_close_during_finalization`: verifica que `pool_ref.close()` NO se llama cuando `sys.is_finalizing()=True`; `pool.pool` queda `None`.
  - `test_pool_close_calls_psycopg_close_in_normal_mode`: regresión — verifica que `pool_ref.close()` SÍ se llama en modo normal.
- **Resultados**: 8/8 tests en `test_finalization_safety.py` ✓; 0 regresiones.

## Artefactos generados

| Artefacto    | Ruta                                                                                        | Estado     |
|--------------|---------------------------------------------------------------------------------------------|------------|
| FIX          | `src/util_bbdd/connection/postgresql/pool_connection_postgresql.py`                         | completado |
| TESTS        | `tests/unit/test_finalization_safety.py`                                                    | completado |
| TRACEABILITY | `.ai/sessions/2026-05-22i-hotfix-postgresql-finalization/TRACEABILITY.md`                   | completado |

## Directrices para Futuras IAs

- **[connection/postgresql/finalization]**: La guarda `sys.is_finalizing()` en `run_close_operation_sync` (`close.py`) impide que *nosotros* creemos threads durante el shutdown, pero NO protege contra los threads internos de `psycopg_pool`. La guarda complementaria en `_close_with_optional_timeout` es necesaria y debe mantenerse. No eliminarla.
- **[connection/close/finalization]**: El patrón correcto para pools con threading interno (psycopg_pool, etc.) es: comprobar `sys.is_finalizing()` ANTES de llamar al método `close()` de la librería de terceros, y retornar sin error si Python está finalizando.
- **[tests/finalization]**: Los tests de `TestPostgresqlPoolFinalizationSafety` en `test_finalization_safety.py` usan `_TrackingPool` (clase inline sin `HAS_PSYCOPG_POOL`) para evitar dependencia de driver en test unitario. Mantener este patrón en tests de finalization.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. Fix mínimo (2 líneas de producción), 0 deuda residual.
