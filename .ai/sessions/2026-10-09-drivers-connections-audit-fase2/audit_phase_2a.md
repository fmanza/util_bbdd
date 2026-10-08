# FASE 2A — Deuda restante tras FASE 1 (drivers-connections-audit)

Fecha: 2026-10-09 · Código auditado: `develop` @ `310cf30a` (v0.35.8) · Modo: solo lectura

Baseline: `python -m pytest` → 5281 passed, 497 skipped (`build/logs/drivers_audit_fase2_baseline.txt`).
Duplicidad medida con `difflib.SequenceMatcher` sobre líneas no vacías (`build/logs/drivers_audit_fase2_duplicidad.txt`).

## Resumen

- P0: 0 (los 5 de FASE 1 están cerrados en v0.35.5).
- P1: 2 nuevos (D1 TLS MariaDB, D2 validación async).
- P2: 4 (D3–D6). P3: 6 (D7–D12).

## P1

### D1 — MariaDB no tiene TLS configurable en ningún camino (confirmado en el código)

- `MariaDBConnectionConfig` (`connection/config.py:59-75`) no tiene campos `ssl_*`; `database_types.json` tampoco los
  acepta en `mariadb`; el mapeo async (`connection/mariadb/async_connection_mariadb.py:26-36`) los filtra por lista blanca.
- MySQL (`ssl_*`), PostgreSQL (`sslmode`), Oracle (`protocol=tcps`) y SQL Server (`encryption`) sí lo tienen.
- Un usuario de MariaDB no puede pedir TLS ni por manager ni por Engine (el Engine conecta con el `creator` nativo).
- Hipótesis por verificar contra el banco: MariaDB Connector/Python 1.1.14 admite `ssl_ca`, `ssl_cert`, `ssl_key`,
  `ssl_verify_cert` y `ssl` en `connect()` y `ConnectionPool()` (directriz de la sesión 2026-10-08d: verificar el
  parámetro contra el driver real antes de añadirlo).

### D2 — `AsyncDatabaseManager` no valida `conn_params` (reproducido)

- `managers/async_mgr.py:57-63` solo ejecuta `validate_db_type`; no llama a `ConnectionParamsManager.prepare_and_validate`
  ni a `DriverValidator.check_driver_availability`, que el sync sí ejecuta (`managers/_manager_lifecycle_sync.py:50-63`).
- Reproducción: `{"database": ":memory:", "tipo_erroneo": 1}` → sync lanza `ValidationError`; async inicializa sin error
  (la clave se descarta en silencio en `sanitize_for_connection`).
- Efecto colateral: el async no recibe los defaults del builder (PostgreSQL `schema="public"`, SQL Server `schema="dbo"`,
  HSQLDB `schema="PUBLIC"`), que `managers/_metadata_context.py:43-49` usa para el contexto de metadatos.

## P2

### D3 — Defaults divergentes entre JSON, builder y `*Config` (medido)

| Motor | Clave | JSON | builder | `*Config` | Efecto |
|---|---|---|---|---|---|
| mysql | `charset` | `utf8mb4` | — | `None` | documental (PyMySQL ≥ 1.0 usa utf8mb4 por defecto) |
| postgresql | `schema` | `public` | `public` | `None` | manager sync fija `search_path=public`; `ConnectionFactory` directo y manager async no |
| postgresql | `sslmode` | `prefer` | — | `None` | documental (libpq y asyncpg usan `prefer`) |
| sqlite | `timeout` | `5` | `5` | `5.0` | ninguno |

Claves aceptadas sin campo en `*Config`: `close_timeout` (7 motores) y `schema` (sqlserver, hsqldb). Se consumen fuera
de la config (ver D4).

### D4 — `close_timeout` se parsea fuera de la config en 13 sitios

`parse_close_timeout(conn_params.get("close_timeout", 10))` aparece en los 6 pools sync, 5 pools async y
`managers/sync_mgr.py:103`. Ninguna `*PoolConfig` lo modela, así que su validación depende de cada llamador.

### D5 — Política de pool del Engine divergente (sync vs async vs nativo)

| Camino | `pool_size`/`max_overflow`/`pool_timeout` | `pool_recycle` |
|---|---|---|
| Engine sync (`factory/sqlalchemy_engine_factory.py:123-133`) | ignora `conn_params` (defaults SQLAlchemy 5/10/30) | 3600 solo mariadb/mysql |
| Engine async (`managers/async_mgr.py:488-498`) | lee `conn_params` | 1800 por defecto, todos |
| Pools nativos (`*PoolConfig`) | `conn_params` | 3600 (mysql, mariadb async) |

Además hay **doble pool**: el `creator` del Engine abre conexiones nuevas con `ConnectionFactory`, no del pool nativo.
Un manager con `use_pool=True` que entrega su Engine a bulk/dump puede mantener `pool_size` nativas + hasta 15 del Engine.

### D6 — Semántica de `pool_size` distinta por motor

| Motor | Qué significa `pool_size` |
|---|---|
| MariaDB | tamaño fijo de `mariadb.ConnectionPool` |
| MySQL | base de `QueuePool` + `max_overflow` (10) |
| Oracle | máximo de un pool 1..`pool_size` (`increment=1`) |
| PostgreSQL | `min_size = max_size = pool_size`: abre todas al crear |
| SQL Server | crea `pool_size` conexiones al iniciar + `max_overflow` |
| SQLite | ignorado (siempre 1) |

## P3

- **D7 — Código muerto**: `managers/_manager_lifecycle_async.py` (`AsyncLifecycleManager`, 124 líneas) sigue en el árbol
  tras MGR-02 sin ningún uso en `src/`; su `initialize_pool` se traga los errores del pool (lo contrario de G2).
- **D8 — `CharsetStateDetector._translate_sql`** (`metadata/_charset_detection.py:129-155`): ningún llamador pasa
  parámetros (todas las consultas de diagnóstico son literales); la rama `format` ordena los argumentos por nombre y no
  por posición (bug latente). Solo lo usan tests. Duplica `_paramstyle.to_driver`.
- **D9 — `mode` de charset no configurable**: `select_strategy(mode)` y `AdaptiveCatalogExecutor(mode=...)` admiten
  `native`/`convert`, pero `managers/_catalog_executor.py:229` siempre usa `auto`. No hay forma de forzarlo.
- **D10 — Mapeo a aiomysql en 3 implementaciones**: lista blanca estática (`AsyncMariaDBConnection._map_connect_kwargs`),
  `_split_pool_kwargs` + filtro por firma (`AsyncMariaDBPool`) y `build_aiomysql_connect_kwargs` (MySQL, con TLS).
  Conexión directa y pool de MariaDB aceptan conjuntos distintos.
- **D11 — Exportaciones incoherentes**: `connection/__init__.py` exporta las configs de 6 motores pero no
  `MySQLConnectionConfig`/`MySQLPoolConfig`.
- **D12 — Pendientes heredados**: M5 (8 consultas de diagnóstico, decisión de no combinarlas), H1 (HSQLDB sin validar
  contra servidor real), `trust_cert` sin equivalente en pymssql.

## Duplicidad medida en v0.35.8

| Aspecto | n | LoC | Similitud media | Máx. | Cambio frente a FASE 1 |
|---|---|---|---|---|---|
| Pools sync completos | 6 | 1.072 | 32 % | 43 % | = |
| Pools sync · `__del__` | 6 | 47 | 72 % | 100 % | = |
| Pools sync · `close_connection` | 6 | 87 | 54 % | 93 % | = |
| Pools sync · `close` | 6 | 225 | 39 % | 51 % | = |
| Pools sync · `get_connection` | 6 | 134 | 30 % | 45 % | nuevo |
| Pools async completos | 6 | 546 | 33 % | 61 % | nuevo |
| Pools async · `close` | 5 | 157 | 42 % | 81 % | nuevo |
| Conexiones sync / async | 7 / 6 | 554 / 365 | 28 % / 32 % | 41 % / 43 % | = |
| Engine factory sync vs async | 2 | 336 / 398 | 42 % | — | = (43 %) |
| · `_render_url` | 2 | 24 / 21 | 89 % | — | |
| · `_get_test_query` | 2 | 12 / 12 | 92 % | — | |
| · `_sanitize_conn_str` | 2 | 16 / 12 | 79 % | — | |
| · `_build_*_connection_string` (6) | 2 | 159 / 197 | 52–72 % | — | |
| DSN Oracle | — | — | — | — | **cerrado** (`oracle/_dsn.py`, v0.35.8) |

Lectura: lo duplicado de verdad son `__del__`/`close_connection` de los pools sync (~134 LoC), los helpers de URL de
las dos factories (~52 LoC casi idénticas) y el mapeo aiomysql. El cuerpo de pools y conexiones envuelve drivers
distintos (≤ 33 % de media): no es duplicidad extraíble.
