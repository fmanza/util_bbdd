# TRACEABILITY

## Session metadata
- id: 2026-10-08e-fix-drivers-p2b
- fecha: 2026-10-08
- rama: develop
- skill: (flujo estándar) PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
- fase: IMPLEMENT del resto de P2 de la FASE 1 de `drivers-connections-audit` + bug de `close()` + VERSION (v0.35.8)

## Prompt issued
```text
Bug de close(): SyncDatabaseManager.close() lanza DatabaseOperationError si el ejecutor de consultas no está inicializado.
Problemas de prioridad 2 de FASE 1 aún abiertos: M5–M7, P2–P6, Q2–Q3, L1, H1–H2, G2, O2.
```

## Context supplied
- Sesiones `2026-10-08-drivers-connections-audit-fase1` … `2026-10-08d-fix-drivers-p2`
- `git log -S` del bloque pegado en `close()` (commit `9ae9a46a`, v0.6.6)
- Firmas reales: `jaydebeapi.connect(jclassname, url, driver_args, jars, libs)`, `oracledb.makedsn` (sin `protocol`), asyncpg (`sslmode` como cadena), `psycopg_pool.PoolTimeout`

## AI output summary
- `close()`: el cuerpo de `_verify_sync_executor_initialized` (sin llamadas) quedó dentro de `close()` en `9ae9a46a`; eliminado. Reproducido antes del fix.
- G2: `PoolFactory.SUPPORTED_POOL_TYPES`; `_init_pool` solo usa conexión única si el motor no tiene pool; los errores del pool se propagan.
- M5: sin re-diagnóstico de charset tras `SystemError`. Decisión de alcance: se mantienen las 8 consultas del diagnóstico (una vez por ejecutor; combinarlas obligaba a reescribir 12 tests de mocks secuenciales para ahorrar 4 viajes una sola vez).
- M6: fallo del `init_command` manual → conexión devuelta y error. M7: `MariaDBPoolConfig.pool_recycle` (no va a `mariadb.ConnectionPool`) → `aiomysql.create_pool(pool_recycle=…)`; JSON actualizado.
- P2/P3: asyncpg recibe `sslmode` en cadena y `connect_timeout` como `timeout` (conexión y pool). P4: `schema` validado con `[A-Za-z0-9_$]+(,…)*`. P5: corchetes IPv6 en la URI del pool. P6: `PoolTimeout` → `PoolTimeoutError`.
- Q2: reserva del hueco con lock y conexión fuera; hueco liberado si falla; `PoolTimeoutError`. Q3: ya resuelto en v0.35.6.
- L1: `cached_statements` en el pool SQLite. H1: firma de `jaydebeapi.connect` corregida (bug grave: la conexión nativa no podía funcionar) + `connection_properties` + URL sin `password=` en log. H2: `create_engine("hsqldb")` → `ConnectionError` claro; builder roto eliminado (como SVC-04 en async).
- O2: `connection/oracle/_dsn.py::build_oracle_dsn` (sustituye 4 copias) con `protocol` `tcp`/`tcps`; `encoding` aceptado e ignorado.
- Test-first: 30 tests fallaban antes del fix. `ruff`, `mypy` OK; `pytest` 5281 passed, 497 skipped (`build/logs/fix_drivers_p2b_suite.txt`); `tests/integration` 552 passed, 10 skipped (`build/logs/fix_drivers_p2b_integration.txt`); `zensical build --strict` OK.
- Banco: asyncpg `prefer` conecta y `require` falla (servidor sin TLS; antes `prefer` → `True` fallaba); pool PG agotado → `DatabaseOperationError ← PoolTimeoutError ← PoolTimeout`; Oracle TCP. HSQLDB validado después (2026-10-09) con `hsqldb-2.7.4.jar` y `jdbc:hsqldb:mem:` (sin servidor): v0.35.8 conecta y aplica `connection_properties` (`SELECT 1 FROM DUAL` con `sql.syntax_ora=true`); v0.35.7 fallaba con `Class org.hsqldb.jdbc.JDBCDriver is not found` (el jar llegaba como `libs`).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| close()/G2 | `src/util_bbdd/managers/sync_mgr.py`, `src/util_bbdd/factory/pool_factory.py` | completado |
| M5–M7 | `src/util_bbdd/managers/_catalog_executor.py`, `connection/mariadb/pool_connection_mariadb.py`, `connection/mariadb/async_pool_connection_mariadb.py`, `connection/config.py` | completado |
| P2–P6 | `connection/postgresql/async_connection_postgresql.py`, `async_pool_connection_postgresql.py`, `pool_connection_postgresql.py`, `connection/config.py` | completado |
| Q2 | `connection/sqlserver/pool_connection_sqlserver.py` | completado |
| L1/H1/H2 | `connection/sqlite/pool_connection_sqlite.py`, `connection/hsqldb/connection_hsqldb.py`, `factory/sqlalchemy_engine_factory.py` | completado |
| O2 | `connection/oracle/_dsn.py` (nuevo) + 4 consumidores, `connection/config.py`, `data/database_types.json` | completado |
| Docs | `docs/guides/connection_guide.md` | completado |
| VERSION | `CHANGELOG.md` [0.35.8] + campos de versión | completado |

## Directrices para Futuras IAs
- **[HSQLDB]**: `jaydebeapi.connect(jclassname, url, driver_args, jars)`; `driver_args` es un dict de propiedades JDBC (`user`, `password`, …). Antes de v0.35.8 la llamada estaba mal y la conexión nativa no podía funcionar. Validación sin servidor: `jdbc:hsqldb:mem:<nombre>` + jar de HSQLDB + `JAVA_HOME` apuntando a un JDK (JPype necesita `jvm.dll`).
- **[Oracle/DSN]**: única fuente del DSN: `connection/oracle/_dsn.py::build_oracle_dsn` (dsn > service_name > sid > database; `protocol=tcps` reescribe el `PROTOCOL` del descriptor de `makedsn`).
- **[asyncpg]**: `ssl` acepta el `sslmode` de libpq como cadena; no convertirlo a booleano. `timeout` es el connect timeout.
- **[pools]**: los pools de MySQL, PostgreSQL y SQL Server lanzan `PoolTimeoutError` al agotarse; `PoolFactory.SUPPORTED_POOL_TYPES` es la lista de motores con pool.
- **[managers/close]**: `close()` no debe lanzar por estado parcial; cualquier verificación del ejecutor va en `_get_sync_query_executor`.
- **[git]**: los bloques "huérfanos" en métodos (código tras el final lógico) suelen venir de merges/inserciones; `git log -S'<texto>'` localiza el commit.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- M5: diagnóstico de 8 consultas (una vez por ejecutor) sin combinar. Mitigado en v0.38.0: `catalog_charset_mode="native"|"convert"` evita el diagnóstico; con `auto` sigue igual (deuda en `docs/roadmap.md`).
- ~~FASE 2 de la skill `drivers-connections-audit`~~: hecha el 2026-10-09 junto con las FASES 3–6 (`.ai/sessions/2026-10-09-*`; auditoría cerrada, ADR-005).
- ~~Commit propuesto, no ejecutado; push y tag `v0.35.8` pendientes~~: commit `310cf30a`, push y tag `v0.35.8` hechos.
- H1: validado el 2026-10-09 con HSQLDB en memoria (ver «AI output summary»); queda sin probar contra un servidor HSQLDB en red.
