# TRACEABILITY

## Session metadata
- id: 2026-10-09-refactor-drivers-b3
- fecha: 2026-10-09
- rama: develop
- skill: refactor
- fase: FASE 4 de `drivers-connections-audit`, bloque B3 (pools): PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```text
/refactor

Objeto: drivers-connections-audit FASE 4 — bloque B3 (pools)
Alcance: mixin de cierre para los pools sync (__del__/close_connection, 72 %/54 % de similitud); close_timeout como campo de *PoolConfig en vez de parse_close_timeout(conn_params.get("close_timeout", 10)) en 13 sitios; política única de pool del Engine (sync y async leen pool_size/max_overflow/pool_timeout/pool_recycle de conn_params, pool_recycle 3600); documentar doble pool y semántica de pool_size por motor (Q5, Q6)
Evidencia: .ai/sessions/2026-10-09-drivers-connections-audit-fase2/audit_phase_2a.md (D4, D5, D6), decision_matrix_phase_2.md § 6
Versión: 0.36.0 (cambia el número de conexiones del Engine sync: BC3). Validar contra el banco. Commit + versión al cerrar.
```
Antes: push de `develop` y tags `v0.35.9`–`v0.35.11` (pedido por el usuario). Aprobación de IMPLEMENT: «si».

## Context supplied
- `.github/prompts/refactor.prompt.md`
- `.ai/sessions/2026-10-09-drivers-connections-audit-fase2/` (D4–D6, Q5, Q6)

## AI output summary
- `SyncPoolCloseMixin` en `connection/close.py` (`__del__` con guarda + plantilla `close_connection` con `_forget_connection`/`_return_to_pool`). MariaDB, MySQL, PostgreSQL: ambos; Oracle: solo `close_connection` (conserva `__del__` de shutdown); SQL Server: plantilla con los dos enganches + `__del__`; SQLite: solo `__del__`. −98/+16 líneas en los pools.
- `close_timeout: float | None = 10` en las 6 `*PoolConfig` (`_close_timeout` con `parse_close_timeout`; fuera de `to_driver_kwargs`). 11 pools lo leen de la config; MariaDB y SQLite sync fijan el valor por defecto y lo sustituyen al validar la config; SQLite async calcula la config antes de conectar. `sync_mgr.py:103` se mantiene (timeout del manager, sin `PoolConfig`).
- `factory/_pool_policy.py` (`engine_pool_kwargs`, `ENGINE_POOL_DEFAULTS` 5/10/30/3600; SQLite → `{}`) usado por las dos factories; `AsyncSQLAlchemyEngineFactory.create_engine` con `pool_*: int | None = None`; `AsyncDatabaseManager.get_sqlalchemy_engine` ya no pasa `pool_*`.
- Tests: `tests/unit/connection/test_pools_b3.py` (48); los 2 de política de Engine fallan con el código anterior. 1 test del manager async actualizado (ya no recibe `pool_*`).
- `ruff`/`mypy` OK (332 ficheros); `pytest` 5327 passed, 497 skipped (`build/logs/refactor_drivers_b3_suite.txt`); `tests/integration` 552 passed, 10 skipped (`build/logs/refactor_drivers_b3_integration.txt`); `zensical build --strict` OK.
- Banco (`build/logs/refactor_drivers_b3_bench.txt`): sync en MariaDB, MySQL, PostgreSQL, Oracle y SQL Server con `pool_size=3`, `close_timeout=2` → pool nativo con `close_timeout=2.0`, Engine `size=3`, `recycle=3600`, cierre correcto; async en MariaDB, MySQL y PostgreSQL igual.
- **Hallazgo nuevo (previo, no corregido)**: `AsyncOraclePool.create` hace `await oracledb.create_pool_async(...)`, pero en oracledb 4.0.1 es una función normal que devuelve el pool → `TypeError: 'AsyncConnectionPool' object can't be awaited`; el pool async de Oracle no funciona contra un servidor real. Presente desde el commit base `07476e38`; los tests unitarios lo simulan como corrutina. Pendiente de `/hotfix`.
- Docs: `docs/guides/connection_guide.md` § 7. Versión 0.36.0 en `pyproject.toml`, `CHANGELOG.md` (sección «Cambios que pueden afectarte»), `README.md`, `docs/index.md`, `docs/roadmap.md`, pie de `docs/architecture.md` (332 ficheros).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/connection/close.py`, `config.py`, 6 `pool_connection_*.py`, 6 `async_pool_connection_*.py` | modificados |
| IMPLEMENT | `src/util_bbdd/factory/_pool_policy.py` | creado |
| IMPLEMENT | `src/util_bbdd/factory/*_engine_factory.py`, `managers/async_mgr.py` | modificados |
| Tests | `tests/unit/connection/test_pools_b3.py` (nuevo), `tests/unit/test_async_database_manager.py` | |
| Docs | `docs/guides/connection_guide.md` § 7 | |
| VERSION | ficheros de versión | 0.36.0 |

## Directrices para Futuras IAs
- **[pools/cierre]**: punto canónico del cierre de pools sync: `SyncPoolCloseMixin` en `connection/close.py`; un pool nuevo define `_return_to_pool` (y `_forget_connection` si lleva registro de prestadas).
- **[pools/close_timeout]**: se lee de `<Motor>PoolConfig.close_timeout`, nunca de `conn_params` directamente; no va en `to_driver_kwargs` (MariaDB pasa esos kwargs a `mariadb.ConnectionPool`).
- **[factory/pool]**: política de pool de los Engine en `factory/_pool_policy.py`; el Engine tiene pool propio (no reutiliza el nativo). SQLite no admite `max_overflow` (`SingletonThreadPool`).
- **[Oracle async]**: oracledb 4.x `create_pool_async` no es corrutina; los tests unitarios de `test_async_oracle.py` lo simulan con `AsyncMock` y por eso no detectaban el fallo. Validar los pools async contra el banco.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- `/hotfix` del pool async de Oracle (`await` sobre `create_pool_async`).
- Siguiente bloque: B1 (validación única en `*Config`, async con `ValidationError`), `/refactor`, 0.36.x.
- Push y tag `v0.36.0` pendientes.
