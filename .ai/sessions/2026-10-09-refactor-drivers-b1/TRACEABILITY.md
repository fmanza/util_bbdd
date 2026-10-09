# TRACEABILITY

## Session metadata
- id: 2026-10-09-refactor-drivers-b1
- fecha: 2026-10-09
- rama: develop
- skill: refactor
- fase: FASE 4 de `drivers-connections-audit`, bloque B1 (validación única de `conn_params`): PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```text
/refactor

Objeto: drivers-connections-audit FASE 4 — bloque B1 (validación única de conn_params)
Alcance: *Config como fuente única de claves y defaults (lista blanca = campos de config + pool + extras declarados; builder reducido a requeridos y alias; JSON documental verificado por test de claves y defaults); defaults de schema (PostgreSQL public, SQL Server dbo, HSQLDB PUBLIC) movidos del builder a *Config y válidos en sync, async y ConnectionFactory (Q3); AsyncDatabaseManager valida conn_params como el sync y lanza ValidationError directo (Q2)
Evidencia: .ai/sessions/2026-10-09-drivers-connections-audit-fase2/audit_phase_2a.md (D2, D3), decision_matrix_phase_2.md § 6 (Q2, Q3)
Versión: 0.37.0 (BC1 y BC2). Validar contra el banco. Commit + versión al cerrar.
```
Aprobación de IMPLEMENT: «si».

## Context supplied
- `.github/prompts/refactor.prompt.md`
- `.ai/sessions/2026-10-09-drivers-connections-audit-fase2/` (D2, D3, Q2, Q3)

## AI output summary
- AUDIT_PLAN: R1 (inyectar defaults del builder en async metería `sql_server_driver="pymssql"` y rompería el AsyncEngine de SQL Server) → `inject_defaults=False` en async; R2 (`DriverValidator` comprueba drivers sync) → no se ejecuta en async; R3 verificado en el banco antes de tocar nada: el async PostgreSQL sin `schema` leía metadatos del schema `bench` (nombre de la BD) con `search_path="$user", public`.
- `PostgreSQLConnectionConfig.schema="public"`; `SQLServerConnectionConfig.schema="dbo"` y `HSQLDBConnectionConfig.schema="PUBLIC"` (no van al driver).
- `ConnectionParamsManager.allowed_keys` (campos de config + pool + `close_timeout` + `encoding` Oracle) sustituye a la lista del JSON en `prepare_and_validate`; mismo conjunto de claves que el JSON en los 7 motores; mismo mensaje de error.
- `build_conn_params` lee defaults con `_default(Config, campo)`: salida idéntica en 37 casos (incluidos errores).
- `AsyncDatabaseManager.__init__`: `prepare_and_validate(..., inject_defaults=False)` → `ValidationError`.
- `_metadata_context`: sin `schema`, default de la config (`_DEFAULT_SCHEMA`), no el nombre de la BD.
- JSON: sin default en MySQL `charset` y PostgreSQL `sslmode`.
- Tests: `tests/unit/test_async_conn_params_validation.py` (17; 9 fallan con v0.36.1) y 3 tests nuevos en `test_conn_params_whitelist.py` (claves JSON = `allowed_keys`, defaults JSON = config —falla con el JSON anterior en mysql y postgresql—, clave desconocida rechazada). 38 tests existentes construían `AsyncDatabaseManager` con `conn_params` incompletos o con claves que PostgreSQL no admite: completados (no se relajó la validación). `test_postgresql_async_server_settings` ahora espera `search_path=public` (BC2a).
- `ruff`/`mypy` OK (332 ficheros); `pytest` 5366 passed, 497 skipped (`build/logs/refactor_drivers_b1_suite.txt`); `tests/integration` 552 passed, 10 skipped (`build/logs/refactor_drivers_b1_integration.txt`); `zensical build --strict` OK.
- Banco (`build/logs/refactor_drivers_b1_bench.txt`): PostgreSQL sync y async `search_path=public`, contexto `public`; async en los 5 motores rechaza una clave inventada, inicializa, conecta el AsyncEngine (SQL Server con aioodbc + ODBC Driver 18) y lee metadatos (`bench`, `bench`, `public`, `BENCH`, `dbo`).
- Docs: `docs/functional/managers_async.md` (reglas de negocio). Versión 0.37.0 con «Cambios que pueden afectarte» y migración.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/connection/config.py`, `builder.py`, `params.py` | modificados |
| IMPLEMENT | `src/util_bbdd/managers/async_mgr.py`, `_metadata_context.py` | modificados |
| Datos | `src/util_bbdd/data/database_types.json` | 2 defaults retirados |
| Tests | `tests/unit/test_async_conn_params_validation.py` (nuevo), `test_conn_params_whitelist.py`, 5 ficheros de tests async actualizados | |
| Docs | `docs/functional/managers_async.md` | |
| VERSION | ficheros de versión | 0.37.0 |

## Directrices para Futuras IAs
- **[conn_params/fuente única]**: claves aceptadas y defaults salen de las configs (`ConnectionParamsManager.allowed_keys`, `_CONFIG_CLASSES`, `_EXTRA_KEYS` en `connection/params.py`). Un parámetro nuevo = campo en la config + entrada en `database_types.json` (los tests de `test_conn_params_whitelist.py` fallan si difieren claves o defaults).
- **[managers/async]**: el async valida con `inject_defaults=False`; nunca inyectar en async los defaults del builder (`sql_server_driver="pymssql"` rompe el AsyncEngine de SQL Server).
- **[metadata/contexto]**: sin `schema`, el contexto de metadatos es el default de la config (`public`/`dbo`/`PUBLIC`), no el nombre de la BD.
- **[tests/async]**: construir `AsyncDatabaseManager` en tests con `conn_params` completos y válidos para el motor (p. ej. PostgreSQL no admite `max_overflow` ni `pool_recycle`).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Siguientes bloques: CS (`catalog_charset_mode`) y B2 (TLS MariaDB), `/new-feature`.
- Push y tags `v0.36.0`, `v0.36.1`, `v0.37.0` pendientes.
