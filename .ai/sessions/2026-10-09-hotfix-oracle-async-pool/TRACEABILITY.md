# TRACEABILITY

## Session metadata
- id: 2026-10-09-hotfix-oracle-async-pool
- fecha: 2026-10-09
- rama: develop
- skill: hotfix
- fase: PLAN + IMPLEMENT (RCA + fix) + AUDIT_CODE + VERSION

## Prompt issued
```text
/hotfix

Bug: el pool async de Oracle no funciona contra un servidor real: AsyncOraclePool.create hace `await oracledb.create_pool_async(...)` y en oracledb 4.0.1 create_pool_async es una función normal que devuelve AsyncConnectionPool → TypeError "'AsyncConnectionPool' object can't be awaited" (AsyncDatabaseManager("oracle", use_pool=True).init() falla)
Evidencia: .ai/sessions/2026-10-09-refactor-drivers-b3/TRACEABILITY.md (hallazgo nuevo), build/logs/refactor_drivers_b3_bench.txt; presente desde el commit base 07476e38; tests/unit/test_async_oracle.py lo simula como corrutina
Prioridad: P2 (funcionalidad async Oracle con pool rota; sin pérdida de datos)
Alcance: src/util_bbdd/connection/oracle/async_pool_connection_oracle.py, tests/unit/test_async_oracle.py
Versión: 0.36.1. Validar contra el banco. Commit + versión al cerrar.
```
Origen: el usuario respondió «Adelante» a la propuesta «hotfix de Oracle antes de B1».

## Context supplied
- `.github/prompts/hotfix.prompt.md`
- `.ai/sessions/2026-10-09-refactor-drivers-b3/TRACEABILITY.md`

## AI output summary
- RCA: python-oracledb 4.0.1 — `create_pool_async` no es corrutina (`inspect.iscoroutinefunction` → False; devuelve `AsyncConnectionPool`); `AsyncConnectionPool.release`/`close` sí son corrutinas y `acquire` devuelve un awaitable, que el código ya trataba bien. El doble de test definía `create_pool_async` como `async def`.
- Test-first: `test_async_oracle_pool_with_sync_create_pool_async` (función normal, como el driver real) reproducía el `TypeError`.
- Fix (1 línea): `await maybe_await(create_pool_async(**create_params))`.
- `ruff`/`mypy` OK; `pytest` 5328 passed, 497 skipped (`build/logs/hotfix_oracle_async_pool_suite.txt`); `tests/integration` 552 passed, 10 skipped (`build/logs/hotfix_oracle_async_pool_integration.txt`).
- Banco (`build/logs/hotfix_oracle_async_pool_bench.txt`): `AsyncDatabaseManager("oracle", use_pool=True)` crea el pool, 3 conexiones adquiridas/liberadas (`SELECT USER FROM DUAL` → `BENCH`), metadatos y cierre correctos.
- Versión 0.36.1.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/connection/oracle/async_pool_connection_oracle.py` | 1 línea |
| Test | `tests/unit/test_async_oracle.py` | test nuevo |
| VERSION | `pyproject.toml`, `CHANGELOG.md`, `README.md`, `docs/index.md`, `docs/roadmap.md`, `docs/architecture.md` | 0.36.1 |

## Directrices para Futuras IAs
- **[dobles de test/drivers]**: al simular un driver, copiar si cada función es corrutina o no (`inspect.iscoroutinefunction` sobre el driver real); un `async def` de más en el doble ocultó durante toda la vida del módulo que el pool async de Oracle no se podía crear.
- **[Oracle async]**: con python-oracledb 4.0.1, `create_pool_async` y `AsyncConnectionPool.acquire` no son corrutinas (devuelven pool / awaitable); `release` y `close` sí.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Siguiente bloque: B1 (validación única en `*Config`, async con `ValidationError`), `/refactor`.
- Push y tags `v0.36.0` y `v0.36.1` pendientes.
