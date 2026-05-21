# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `src/util_bbdd/executors/sync_query_executor.py`
- `tests/unit/test_sync_executor_contract.py`
- Stack trace completo de producción (`pruebas_util/src/main.py`)

## Estado actual observado
- Tests previos al inicio: suite completa verde (>2900 tests)
- Lint / mypy: errores pre-existentes en `sqlserver.py` y `bulk/crud.py` (no relacionados)
- Bug activo en producción: crash al llamar `execute_custom_many` sobre MariaDB con datos
  de charset no-UTF-8 (campo `column_type` en `INFORMATION_SCHEMA.COLUMNS`)

## Estado Git relevante
- Rama activa: develop
- Commits previos de esta sesión (hotfixes 1-3 ya commiteados):
  - `9f33cd1` fix(executors): detect mariadb fetchrows SystemError as decode error
  - `54d7321` fix(executors): use fetchone loop in binary cursor fallback to avoid fetchrows
  - `f7c21ee` fix(executors): set conn.character_set='binary' in retry to bypass C-ext encoding bug
- Cambios sin commitear al inicio de la 4.ª iteración: fix en `_retry_fetch_with_binary_cursor`
  reemplazando property setter por `SET NAMES 'binary'` SQL + ajuste de 5 tests

## Clasificación metodológica
- Tipo principal: hotfix (P1 — crash en producción)
- Estado real de alcance: acotado (1 método, 1 archivo fuente)
- Consecuencia: fix mínimo acotado, sin refactorización

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes:
- Ninguna; causa raíz identificada antes de iniciar la 4.ª iteración
