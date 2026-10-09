# TRACEABILITY

## Session metadata
- id: 2026-10-09c-hotfix-p1-pendientes
- fecha: 2026-10-09
- rama: develop
- skill: hotfix
- fase: PLAN + IMPLEMENT (RCA + fix) + AUDIT_CODE + VERSION — bloque P1 de `.ai/sessions/2026-10-09b-plan-pendientes/PLAN_AUDIT_PLAN.md`

## Prompt issued
```text
/hotfix

Bug: P1 del plan de pendientes (.ai/sessions/2026-10-09b-plan-pendientes/PLAN_AUDIT_PLAN.md): (a) F4 — el WARNING de TLS async sin verificar se emite en cada conexión nueva (async_creator del AsyncEngine), debe ser uno por pool/Engine; (b) un init_command propio de MariaDB se ignora en async (aiomysql) porque _aiomysql lo excluye siempre: enviarlo si es distinto del por defecto SET NAMES utf8mb4; (c) trust_cert=True no tiene efecto con pymssql y no se avisa: WARNING una vez
Rutas: src/util_bbdd/connection/_aiomysql.py, connection/mariadb/async_connection_mariadb.py, async_pool_connection_mariadb.py, connection/sqlserver/connection_sqlserver.py (pymssql)
Prioridad: P3
Versión: 0.39.2. Validar contra el banco. Commit + versión al cerrar.
```
Plan aprobado por el usuario («si»); decisiones: `init_command` propio sí, `trust_cert` con WARNING.

## Context supplied
- `.ai/sessions/2026-10-09b-plan-pendientes/PLAN_AUDIT_PLAN.md`

## AI output summary
- RCA: (a) `build_aiomysql_connect_kwargs` se llama en cada conexión (el `async_creator` del AsyncEngine abre conexiones nativas) y avisaba siempre; (b) MariaDB pasaba `exclude={"init_command"}` incondicionalmente (B4); (c) `_connect_pymssql` descartaba `trust_cert` sin avisar.
- `connection/_advisory.py::warn_once(logger, key, message)` + `reset_warned` (estado de proceso con lock, como `report_once`); clave `(motivo, host, port)`: una vez por servidor (más estricto que «por pool/Engine», sin cablear estado por el creator). Fixture autouse en `tests/conftest.py` que limpia el estado antes de cada test.
- `mariadb_aiomysql_exclude(driver_kwargs)`: excluye `init_command` solo si es el por defecto (`MariaDBConnectionConfig.init_command`).
- Test-first: `tests/unit/connection/test_p1_pending_fixes.py` (5; fallaban antes del fix).
- `ruff`/`mypy` OK; `pytest` 5402 passed, 497 skipped (`build/logs/hotfix_p1_pending_suite.txt`), también con orden alterado; `tests/integration` 552 passed, 10 skipped; `zensical build --strict` OK.
- Banco (`build/logs/hotfix_p1_pending_bench.txt`): MariaDB `ssl=True` con pool de 2 + 4 conexiones del AsyncEngine → 1 aviso; `init_command="SET time_zone = '+05:00'"` aplicado en async directa y pool; por defecto + `charset="latin1"` → sesión latin1 (sin cambio); SQL Server pymssql `trust_cert=True` con pool de 3 → conecta y 1 aviso.
- Docs: `connection_guide.md` (§ 6 `init_command`, tabla de SQL Server); roadmap sin F4 ni `init_command`; `trust_cert` anotado. Versión 0.39.2.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `connection/_advisory.py`, `_aiomysql.py`, `mariadb/async_connection_mariadb.py`, `mariadb/async_pool_connection_mariadb.py`, `sqlserver/connection_sqlserver.py` | modificados |
| Tests | `tests/unit/connection/test_p1_pending_fixes.py` (nuevo), `tests/conftest.py` (fixture) | |
| Docs | `docs/guides/connection_guide.md`, `docs/roadmap.md` | |
| VERSION | ficheros de versión | 0.39.2 |

## Directrices para Futuras IAs
- **[avisos repetidos]**: para avisos de configuración que se repetirían en cada conexión de un pool o Engine, usar `connection/_advisory.py::warn_once` con una clave que incluya el servidor; los tests parten de estado limpio por el fixture de `tests/conftest.py`.
- **[MariaDB async/init_command]**: el `init_command` por defecto nunca va a aiomysql; uno propio sí (`mariadb_aiomysql_exclude`).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- P2a/P2b (M5, v0.39.3) y siguientes del plan.
- Push y tag `v0.39.2` pendientes.
