# TRACEABILITY

## Session metadata
- id: 2026-10-09-refactor-drivers-b4
- fecha: 2026-10-09
- rama: develop
- skill: refactor
- fase: FASE 4 de `drivers-connections-audit`, bloque B4 (mapeo aiomysql único): PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```text
/refactor

Objeto: drivers-connections-audit FASE 4 — bloque B4 (mapeo aiomysql único)
Alcance: unificar AsyncMariaDBConnection._map_connect_kwargs, AsyncMariaDBPool._split_pool_kwargs + filtro por firma y build_aiomysql_connect_kwargs (MySQL) en una sola función para conexión y pool de MariaDB y MySQL
Evidencia: .ai/sessions/2026-10-09-drivers-connections-audit-fase2/audit_phase_2a.md (D10)
Versión: 0.35.11 (sin cambio de comportamiento). Validar contra el banco. Commit + versión al cerrar.
```
Aprobación de IMPLEMENT: «si».

## Context supplied
- `.github/prompts/refactor.prompt.md`
- `.ai/sessions/2026-10-09-drivers-connections-audit-fase2/audit_phase_2a.md` (D10)

## AI output summary
- AUDIT_PLAN: la config de MariaDB siempre lleva `init_command="SET NAMES utf8mb4"`; aiomysql lo acepta pero los dos caminos async de MariaDB lo descartaban. Pasarlo pisaría `charset` en async → se excluye explícitamente (`MARIADB_AIOMYSQL_EXCLUDE`).
- Nuevo `connection/_aiomysql.py::build_aiomysql_connect_kwargs(driver_kwargs, connect, *, exclude=())`; con `connect(**kwargs)` (dobles de test) usa `AIOMYSQL_CONNECT_PARAMS` (firma real de aiomysql 0.3.2) en vez de descartarlo todo.
- MariaDB: `_map_connect_kwargs` delega; `_split_pool_kwargs` eliminado (`minsize`/`maxsize` en `create()`, como MySQL). MySQL: reexporta la función desde `async_connection_mysql`.
- Equivalencia: script que intercepta `aiomysql.connect`/`create_pool` (autospec) en los 4 caminos × 3 variantes × `found_rows`: 54 llamadas idénticas a v0.35.10 con aiomysql real; con el doble de test, la conexión MariaDB idéntica (pool MariaDB y MySQL ahora reciben las claves en vez de ninguna).
- `ruff`/`mypy` OK (331 ficheros); `pytest` 5279 passed, 497 skipped (`build/logs/refactor_drivers_b4_suite.txt`).
- Banco (async real, `SelectorEventLoop`): MariaDB 11.4.13 y MySQL 8.4.11, directa y pool, con y sin `charset="latin1"`: la sesión respeta el charset y el AsyncEngine conecta (`build/logs/refactor_drivers_b4_bench_async.txt`). `tests/integration`: 552 passed, 10 skipped (`build/logs/refactor_drivers_b4_integration.txt`).
- Versión 0.35.11 en `pyproject.toml`, `CHANGELOG.md`, `README.md`, `docs/index.md`, `docs/roadmap.md`, pie de `docs/architecture.md` (331 ficheros).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/connection/_aiomysql.py` | creado |
| IMPLEMENT | `connection/mariadb/async_connection_mariadb.py`, `async_pool_connection_mariadb.py`, `connection/mysql/async_connection_mysql.py` | modificados |
| VERSION | `pyproject.toml`, `CHANGELOG.md`, `README.md`, `docs/index.md`, `docs/roadmap.md`, `docs/architecture.md` | 0.35.11 |

## Directrices para Futuras IAs
- **[aiomysql]**: punto canónico de la traducción config → `aiomysql.connect`: `connection/_aiomysql.py`. B2 (TLS MariaDB) debe reutilizarlo: los `ssl_*` ya se convierten en `ssl=SSLContext` ahí.
- **[MariaDB async/init_command]**: MariaDB async nunca envía `init_command` (ni el por defecto ni uno del usuario); `charset` es lo que gobierna la sesión en aiomysql. Un `init_command` personalizado se ignora en async: deuda previa, no introducida aquí.
- **[tests/dobles]**: filtrar por `inspect.signature` con un doble `connect(*args, **kwargs)` descarta todas las claves; la función común usa la lista real de aiomysql en ese caso.
- **[banco/async Windows]**: para probar aiomysql en Windows usar `asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Fin de la serie 0.35.x (B6, B5, B4). Siguiente: B3 (pools) en 0.36.0, `/refactor`.
- Push y tags `v0.35.9`, `v0.35.10`, `v0.35.11` pendientes.
