# TRACEABILITY

## Session metadata
- id: 2026-10-10-plan-pendientes-post-1-0
- fecha: 2026-10-10
- rama: develop (base v1.0.0, `158903b6`)
- skill: planificación + `/refactor` (A5) + `/new-feature` (rutas `str`) + `/hotfix` (asyncpg) + docs + `/version-closure`
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (B0–B5 + hotfix) + VERSION (v1.1.0 en local, sin tag ni push)

## Prompt issued
«Sesión nueva: PLAN + AUDIT_PLAN de los pendientes de util_bbdd tras v1.0.0» (texto completo saneado en
`00_REQUEST.md`; origen: `.ai/sessions/2026-10-10-api-1-0-final/NEXT_SESSION_PROMPT.md`). Después: «Sí. IMPLEMENT.
Pregunta lo que necesites».

## Context supplied
- `.ai/CURRENT_STATE.md`, `docs/roadmap.md`
- `.ai/sessions/2026-10-10-api-1-0-final/TRACEABILITY.md`, `02_DOC_REVIEW.md`
- `.ai/sessions/2026-10-10-plan-pendientes-global/PLAN_AUDIT_PLAN.md`, `Q6_PLAN_API_1_0.md`

## AI output summary

PLAN + AUDIT_PLAN (`3d878688`): inventario verificado P1–P7, N1–N2, O1 (evidencias en `build/logs/postv1_*`);
decisiones D1–D6; bloques B0–B7. Decisiones del usuario: D1–D6 según la recomendación; N1 retirar el workflow; las 3
páginas `constraints_*` consolidadas en la guía; el fallo de asyncpg como `/hotfix` dentro de 1.1.0.

| Bloque | Commits | Resultado |
|---|---|---|
| B1 | — | `main` → `158903b6` (v1.0.0) sin checkout (`git fetch . <sha>:main`, solo FF) y push de `main` (autorizado) |
| B0 | `6e089b66`, `f1bb6b6f` | `doc_agents.yml` + `generate_docs.py` retirados; `CURRENT_STATE` (cabecera, filas 0.43–1.0, «Próximos pasos») |
| B2 | `e7cb3676`, `2369e6ed` | Fixture autouse en `tests/conftest.py` que cierra las conexiones DBAPI de los Engines creados por el módulo de test; `closing()` en 3 `sqlite3.connect`; `create_mock_engine`. `--cov`: 340 → 0 `ResourceWarning` (3 tras el primer commit, localizados con `tracemalloc`), 0 `SADeprecationWarning` |
| B3 | `587e7f40` | `_core/validation/paths.py` (`StrPath`, `validate_path`, `validate_optional_path`) en `BulkCrud`, `ParallelBulkLoader`, `AuditManager`, `path_sql` y `DumpConfig`; 19 tests nuevos, 17 rojos contra v1.0.0 (worktree temporal, `build/logs/postv1_b3_red_before.txt`) |
| B4 | `0b0ba205`, `c9bb3598` | `TableMaintenance` (`bulk/_execution/maintenance.py`) y `RejectsCoordinator` (`bulk/_support/rejects.py`); código movido idéntico salvo nombres (`postv1_b4_moved_diff.txt`, `postv1_b4b_moved_diff.txt`); `crud.py` 1943 → 1564 |
| B5 | `e14dd441`, `ac605edc` | 18 páginas + barrido (ver `02_DOC_REVIEW.md`); 2 guías a `docs/guides/`, 3 páginas consolidadas |
| Hotfix | `d369c8e3` | asyncpg en `AsyncQueryExecutor` (`fetch`/`fetchrow`, `%(n)s`/`:n` → `$n`); 7 unitarios (6 rojos con el error de producción) + 4 de integración |
| Hotfix 2 y 3 | `cf7abb78`, `1c83041b` | Tras instalar el usuario el ODBC Driver 18: `ResultNormalizer` convierte en tupla las filas de driver que son secuencias (`pyodbc.Row` no define `__iter__`); el pool async de SQL Server lee la config con `sql_server_driver="pyodbc"`. 10 + 2 unitarios (4 rojos) y 4 de integración (`test_sqlserver_pyodbc_rows.py`) |
| B7 | `da605e0e` + notas | 1.1.0 en `pyproject.toml`, CHANGELOG, README, `docs/index.md`, `docs/roadmap.md`, pie de `docs/architecture.md`, instalación `@v1.1.0`; `CURRENT_STATE`, `SESSIONS_DIGEST` |

Desviaciones del plan: `TableMaintenance` va en `_execution/` y no en `_support/` (usa `SessionScope`/`CommitCadence`;
`_support` no importa de `_execution`). B3 cubrió también `AuditManager` (público en `util_bbdd.bulk`). El hotfix no
estaba en el plan: apareció al ejecutar un ejemplo de B5.

Errores propios corregidos durante la sesión: la primera versión de la fixture de B2 retenía el Engine (rompía
`test_released_engine_leaves_registry`) y después su pool (el pool referencia al Engine por el closure del `creator`);
dos expectativas del test de integración de asyncpg suponían interpolación en el cliente.

Puerta de VERSION: ruff, ruff format, mypy (334 ficheros) limpios; pytest sin banco 5718 passed, 527 skipped
(`postv1_gate_pytest_sin_banco.txt`); con banco + `JAVA_HOME` 6238 passed, 7 skipped (`postv1_gate_pytest_con_banco.txt`).
Tras los hotfix 2 y 3: 5730 passed, 531 skipped sin banco; 6254 passed, 7 skipped con banco (`postv1_hotfix2_pytest_*.txt`);
`zensical build --strict` sin incidencias; `python -m build` → `util_bbdd-1.1.0`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-10-10-plan-pendientes-post-1-0/00_REQUEST.md` | emitido |
| CONTEXT SNAPSHOT | `.ai/sessions/2026-10-10-plan-pendientes-post-1-0/00_CONTEXT_SNAPSHOT.md` | emitido |
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-10-plan-pendientes-post-1-0/PLAN_AUDIT_PLAN.md` | aprobado (D1–D6) |
| Revisión de docs | `.ai/sessions/2026-10-10-plan-pendientes-post-1-0/02_DOC_REVIEW.md` | emitido |
| Logs y sondas | `build/logs/postv1_*` | emitido |

## Directrices para Futuras IAs
- **[bulk]**: `BulkCrud` delega la auditoría en `bulk/_support/persistence.py` (`BulkPersistenceManager`), los rechazos
  en `bulk/_support/rejects.py` (`RejectsWriter`, `Isolator`, `RejectsCoordinator`) y el mantenimiento de tabla en
  `bulk/_execution/maintenance.py` (`TableMaintenance`, una instancia por llamada a `maintenance_scope`). Los tests
  parchean `BulkCrud._table_snapshot` y reasignan `crud.engine`: por eso los colaboradores reciben callables o se crean
  por llamada.
- **[bulk]**: dirección de imports dentro de `bulk`: `_execution` → `_support`, nunca al revés.
- **[rutas]**: los parámetros de ruta públicos se normalizan con `_core.validation.validate_path`/`validate_optional_path`
  (`StrPath` = `str | os.PathLike[str]`). En una `dataclass` (`DumpConfig`), el campo se anota `StrPath`, se normaliza en
  `__post_init__` y quien lo usa vuelve a normalizar (el campo se puede reasignar tras construir).
- **[executors]**: asyncpg no es DB-API; `AsyncQueryExecutor` lo detecta por `type(conn).__module__` (`asyncpg…`, también
  el proxy del pool) y usa `fetch`/`fetchrow`. asyncpg tipa los parámetros en el servidor: `SELECT $1` es `text`. El
  catálogo async (`managers/_catalog_executor.py`) ya lo resolvía con `metadata._paramstyle.to_driver(..., "dollar")`;
  `executors` no puede importar `metadata` (mismo nivel de capas).
- **[tests]**: `tests/conftest.py::_close_test_engine_connections` cierra las conexiones de los Engines que crea el
  módulo de test (envuelve su `create_engine`); un `create_engine` importado dentro de la función no se envuelve. Los
  `ResourceWarning` aparecen en el test que hace `gc.collect()`, no en el que fuga: localizar con `PYTHONTRACEMALLOC=25`
  (no funciona con `python -I`).
- **[docs]**: antes de documentar una cifra de rendimiento, buscar su sesión de medición; las páginas de abril sin fuente
  (`benchmarks.md`) tenían tablas inventadas. Ejecutar los ejemplos tocados contra el banco: así apareció el fallo de
  asyncpg.
- **[git]**: mover `main` a un commit sin cambiar de rama: `git fetch . <sha>:main` (solo fast-forward).
- **[results]**: `pyodbc.Row` (y la de aioodbc) no es `tuple` ni define `__iter__`: se itera por `__getitem__`. Un
  doble de test de una fila de driver debe imitar eso; el primero que escribí tenía `__iter__` y pasaba con el fallo.
- **[shell]**: los heredocs de Bash quitan un nivel de `\`; los scripts con regex o `\|` se escriben con Write.

## Veredicto final
Veredicto: CLOSED (v1.1.0 en local)
Pendientes al cierre:
- Tag `v1.1.0`, push de `develop` y fast-forward de `main`: solo con autorización explícita.
- Nivel 2 de la revisión de docs (~85 páginas) y `docs/examples/migrate_*`.
- `driver_name` por defecto de SQL Server = ODBC Driver 17: con solo el 18 instalado hay que indicarlo (decisión).
- Externos (usuario): PR #18, issue del ORA-03106, `docs-release.yml` de los tags, `integration.yml`, PR de dependabot.
