# TRACEABILITY

## Session metadata
- id: 2026-10-08b-hotfix-drivers-p0
- fecha: 2026-10-08
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (RCA + fix, test-first) + AUDIT_CODE + VERSION (v0.35.5)

## Prompt issued
```text
/hotfix
Bug: P0 de FASE 1 de drivers-connections-audit (S1, B1, B2, S4, T1)
Evidencia: .claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md § Resultado de FASE 1; .ai/sessions/2026-10-08-drivers-connections-audit-fase1/TRACEABILITY.md
Alcance: src/util_bbdd/factory/**, src/util_bbdd/_drivers/**, src/util_bbdd/connection/**, src/util_bbdd/data/database_types.json, src/util_bbdd/metadata/_charset_detection.py, src/util_bbdd/metadata/_adaptive_executor.py, tests/unit/**
```

## Context supplied
- `.github/prompts/hotfix.prompt.md`, `.github/agents/hotfix-responder.agent.md`
- Hallazgos de `.ai/sessions/2026-10-08-drivers-connections-audit-fase1/TRACEABILITY.md`
- Historial git de `_charset_detection.py`, `_adaptive_executor.py` y `test_charset_detection.py` (commits 81ff2210, 3f9f7ebe, 2cda9b89)
- Decisión del usuario (T1): servidor latin1 con sesión y BD en utf8mb4 → `UTF8MB4_CLEAN`

## AI output summary
- RCA S1: URLs con f-string en 8 builders (`factory/sqlalchemy_engine_factory.py`, `factory/async_sqlalchemy_engine_factory.py`). Fix: `_render_url` con `URL.create` (Oracle con `database=""` para conservar el formato `…:1521/?service_name=X`).
- RCA S4: `create_engine(conn_str, pool_pre_ping, echo)` sin `connect_args`. Fix: `creator` / `async_creator` sobre `ConnectionFactory` en mariadb/mysql/oracle/postgresql/sqlserver; Oracle con `dsn`/`sid` construye URL sin `service_name`.
- AUDIT_CODE propio detectó una regresión del fix S4: con `creator` SQLAlchemy no ejecuta `dialect.create_connect_args`, que añade `CLIENT.FOUND_ROWS` en MySQL/MariaDB/aiomysql. Fix: parámetro `found_rows` (por defecto `False`) en `ConnectionFactory.create_connection`, `MariaDBConnection.connect`, `MySQLConnection.connect` y sus versiones async; los Engine lo activan. `client_flag` sigue fuera de la lista blanca.
- RCA B1: `database_types.json` desalineado con `*Config`. Fix: 7 × `close_timeout`, `pool_name`, `options`, `target_session_attrs`, `database` y `oracle_thick_mode` (round-trip del JSON idéntico: solo inserciones). `builder.py` acepta Oracle con `database`.
- RCA B2: `OracleConnectionConfig.to_driver_kwargs` omitía `oracle_thick_mode`; pool con `init_oracle_client` directo. Fix: emitir la clave; pool con `init_oracle_thick_mode` (+ error si thick sin `oracle_client_path`).
- RCA T1: v0.35.4 cambió `_determine_state` (servidor ≠ utf8mb4 → MIXED) y `_inject_convert` (sin alias) sin tocar tests. Fix: quitar la regla del servidor (decisión del usuario); 2 tests del alias alineados con el código.
- Tests test-first: 34 fallaban antes del fix; ahora pasan. Validación real: `UPDATE` sin cambios → `rowcount = 1` en MySQL y MariaDB (sync y async) con Engine de la factory; sesión utf8mb4.
- `ruff format`/`ruff check`/`mypy` OK; `pytest` 5201 passed, 497 skipped (`build/logs/hotfix_drivers_p0_suite.txt`); `tests/integration` 551 passed, 10 skipped, 1 failed preexistente (`build/logs/hotfix_drivers_p0_integration.txt`); `python -m build` OK.
- VERSION: 0.35.5 en `pyproject.toml`, `README.md`, `docs/index.md`, `docs/roadmap.md`, pie de `docs/architecture.md`; diagrama regenerado (329 ficheros; etiqueta ×15 → ×17 por los imports `factory/` → `connection/`).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Fix S1/S4 | `src/util_bbdd/factory/sqlalchemy_engine_factory.py`, `src/util_bbdd/factory/async_sqlalchemy_engine_factory.py` | completado |
| `found_rows` | `src/util_bbdd/connection/factory.py`, `connection/mariadb/connection_mariadb.py`, `connection/mariadb/async_connection_mariadb.py`, `connection/mysql/connection_mysql.py`, `connection/mysql/async_connection_mysql.py` | completado |
| Fix B1 | `src/util_bbdd/data/database_types.json`, `src/util_bbdd/connection/builder.py` | completado |
| Fix B2 | `src/util_bbdd/connection/config.py`, `src/util_bbdd/connection/oracle/pool_connection_oracle.py` | completado |
| Fix T1 | `src/util_bbdd/metadata/_charset_detection.py`, `tests/unit/metadata/test_charset_detection.py` | completado |
| Tests | `tests/unit/test_engine_factory_credentials.py`, `tests/unit/connection/test_conn_params_whitelist.py`, `tests/unit/connection/test_oracle_thick_mode.py` | nuevos |
| VERSION | `CHANGELOG.md` [0.35.5] + campos de versión | completado |

## Directrices para Futuras IAs
- **[factory/creator]**: los Engine de `SQLAlchemyEngineFactory`/`AsyncSQLAlchemyEngineFactory` conectan con `ConnectionFactory` (`creator`/`async_creator`) en mariadb, mysql, oracle, postgresql y sqlserver: la URL solo elige dialecto. Cambios de TLS/charset se hacen en `connection/<motor>/` y valen para managers y Engine a la vez.
- **[SQLAlchemy/creator]**: con `creator` SQLAlchemy no llama a `dialect.create_connect_args`; lo que el dialecto añade al conectar (p. ej. `CLIENT.FOUND_ROWS` en MySQL/MariaDB) hay que replicarlo a mano (`found_rows`). Revisar `create_connect_args` del dialecto antes de añadir otro motor al `creator`.
- **[conn_params/lista blanca]**: `tests/unit/connection/test_conn_params_whitelist.py::test_json_whitelist_covers_every_config_field` falla si se añade un campo a `*Config` sin añadirlo a `data/database_types.json`.
- **[database_types.json]**: se puede reescribir con `json.dumps(data, indent=2, ensure_ascii=False) + "\n"` sin ruido (round-trip byte a byte idéntico); leer con `encoding="utf-8"`.
- **[charset]**: semántica vigente (decisión del usuario 2026-10-08): sesión y BD en utf8mb4 → `UTF8MB4_CLEAN` aunque `character_set_server` sea latin1; `_inject_convert` no añade alias `AS campo`.
- **[banco]**: el contenedor `util_bbdd_bench_mariadb` (recreado ~2026-10-06) tiene `MARIADB_PASSWORD` distinta del resto; sustituirla en `UTIL_BBDD_*_MARIADB_URL` tras `source scripts/bench_env.example.sh`.
- **[integración]**: `test_snapshot_golden.py::test_snapshot_matches_golden_and_migrate[oracle]` falla en v0.35.4 y v0.35.5 (13 consultas frente a 12 declaradas): preexistente, no ligado a este hotfix.
- **[mariadb 1.1.14]**: el driver rechaza `encoding_errors` en `connect()`; el reintento de `MariaDBConnection.connect` lo quita y emite un WARNING por conexión nueva (ahora también en los Engine).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Fallo preexistente de caracterización Oracle (`test_snapshot_golden.py[oracle]`).
- `zensical build --strict`: 3 anclas rotas preexistentes (ver sesión `2026-10-08-drivers-connections-audit-fase1`).
- WARNING por conexión cuando mariadb rechaza `encoding_errors` (ruido de log; candidato a cachear el rechazo).
- P1 de FASE 1 sin tratar: Q1 (pymssql descarta `encryption`), Y3 (aiomysql descarta `ssl_*`), M3/Y2 (charset adaptativo en async y con pool MySQL), M1, P1, O1 parcial.
- Commit propuesto, no ejecutado.
