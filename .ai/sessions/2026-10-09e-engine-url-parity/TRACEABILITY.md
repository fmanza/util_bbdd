# TRACEABILITY

## Session metadata
- id: 2026-10-09e-engine-url-parity
- fecha: 2026-10-09
- rama: develop
- skill: refactor (cambio de API justificado)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION — bloque P3 (F5) de `.ai/sessions/2026-10-09b-plan-pendientes/PLAN_AUDIT_PLAN.md`

## Prompt issued
```text
antes el push y los tags de v0.39.2 y v0.39.3, luego P3 con la excepción de Oracle
```
Plan P3 presentado en la conversación: unificar con la semántica async (decisión del usuario) salvo Oracle `service_name=""`, donde se adopta la sync (usar `database` como alias), aprobado.

## Context supplied
- `.ai/sessions/2026-10-09b-plan-pendientes/PLAN_AUDIT_PLAN.md`; `factory/_url.py` (B5)

## AI output summary
- Push de `develop` y tags `v0.39.2`, `v0.39.3`.
- `factory/_url.py::server_url(db_type, drivername, conn_params, database)` con `_SERVER_DEFAULTS` y `_text`; los 10 `_build_*_connection_string` (5 sync, 5 async) pasan a envoltorios con su driver (−269 líneas netas). SQL Server async conserva la comprobación de `aioodbc` después de construir la URL (mismo orden de errores).
- Comparación con HEAD (módulos antiguos cargados en paralelo, `build/logs/refactor_p3_compare.txt`): 43 200 casos, 6 696 diferencias, todas en 7 reglas: `port=None` (antes `TypeError`) 5 142; sync `host`/`user=None` 954; sync SQL Server sin BD 288; sync `database=None` 168; async MySQL `user=""` 72; Oracle `service_name=""` 54; async Oracle `database=None` 18. Sin diferencias sin clasificar. Dos no previstas en el plan (`port=None`, MySQL `user=""`) comunicadas y documentadas.
- Tests: `tests/unit/test_engine_url_parity.py` (15; 10 fallan con v0.39.3), incluida la paridad sync/async sobre una rejilla de entradas límite por motor.
- `ruff`/`mypy` OK; `pytest` 5422 passed, 497 skipped (`build/logs/refactor_p3_suite.txt`); `tests/integration` 552 passed, 10 skipped; banco: Engine sync y async de los 5 motores conectan (`build/logs/refactor_p3_bench.txt`); `zensical build --strict` OK.
- Docs: roadmap sin F5; ADR-005 (deuda); CHANGELOG 0.40.0 con «Cambios que pueden afectarte».

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/factory/_url.py`, `sqlalchemy_engine_factory.py`, `async_sqlalchemy_engine_factory.py` | modificados |
| Tests | `tests/unit/test_engine_url_parity.py` | nuevo |
| Docs | `docs/roadmap.md`, `docs/adr/ADR-005-conexiones-multimotor.md` | |
| VERSION | ficheros de versión | 0.40.0 |

## Directrices para Futuras IAs
- **[factory/URL]**: la URL de los motores de servidor sale de `factory/_url.py::server_url`; las factories solo eligen el driver. `test_engine_url_parity.py` falla si sync y async vuelven a divergir.
- **[técnica/comparación]**: en un refactor con cambios de comportamiento acotados, comparar antiguo/nuevo sobre un producto cartesiano y clasificar cada diferencia por regla; no cerrar con diferencias «sin clasificar».

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- P4 (F3: `ssl_verify_identity` con CA propia; puerta P4.0 primero) y P5 (HSQLDB en red).
- Push y tag `v0.40.0` pendientes.
