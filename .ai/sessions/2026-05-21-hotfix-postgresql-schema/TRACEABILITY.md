# TRACEABILITY

## Session metadata
- id: 2026-05-21-hotfix-postgresql-schema
- fecha: 2026-05-21
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Al conectar con PostgreSQL en `src/util_bbdd/migrate`, no recoge el `database` y `schema`.
Config TOML de referencia: `[conexion.postgresql]` con `database = "testdb"`, `schema = "ventas_test"`,
`pool_size = 5`, `pool_timeout = 30`, `max_idle = 300`.

## Context supplied
- `src/util_bbdd/connection/config.py` — `PostgreSQLConnectionConfig`, `PostgreSQLPoolConfig`
- `src/util_bbdd/connection/postgresql/pool_connection_postgresql.py` — `PoolConnection.__create_pool()`
- `src/util_bbdd/connection/params.py` — `ConnectionParamsManager`
- `src/util_bbdd/connection/builder.py` — `_build_postgresql_params()`
- `src/util_bbdd/connection/postgresql/async_pool_connection_postgresql.py` — revisión adicional
- `src/util_bbdd/connection/postgresql/async_connection_postgresql.py` — revisión adicional

## AI output summary
- PLAN: Causa raíz identificada — `PostgreSQLConnectionConfig` carece de campo `schema`; `from_params()` lo ignora; `to_driver_kwargs()` no lo propaga; `__create_pool()` nunca lo aplica como `options=-c search_path=...`. `database` sí funciona (incluido en conninfo URL).
- AUDIT_PLAN: GO — 2 ficheros afectados; riesgo de SQL injection mínimo (TOML controlado por operador); conflicto con `options` explícito descartado.
- IMPLEMENT: Añadido `schema: str | None = None` a `PostgreSQLConnectionConfig`; leído en `from_params()` via `_opt_str`; propagado en `to_driver_kwargs()` como `"schema"`.
- IMPLEMENT: En `__create_pool()`, si `schema` presente, se codifica vía `urllib.parse.quote` y se añade como `?options=-c%20search_path%3D...` al conninfo URL (evita error mypy con `**kwargs` en `ConnectionPool`).
- mypy: 0 errores en archivos modificados (2 errores preexistentes en `migrate/extractors/sqlserver.py`; fuera de scope).
- ruff check: All checks passed.
- pytest: 3083 passed, 1 skipped, 0 failed.
- AUDIT_CODE: Sin regresiones. Deuda técnica identificada: async pool (asyncpg) no aplica `schema`; misma causa raíz, fix requiere `server_settings={"search_path": ...}`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix config | `src/util_bbdd/connection/config.py` | completado |
| Fix pool sync | `src/util_bbdd/connection/postgresql/pool_connection_postgresql.py` | completado |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Deuda técnica: `async_pool_connection_postgresql.py` y `async_connection_postgresql.py` ignoran `schema` (asyncpg usa `server_settings`). No bloqueante para el caso reportado (pool sync).
