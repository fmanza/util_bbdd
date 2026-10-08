# TRACEABILITY

## Session metadata
- id: 2026-10-08d-fix-drivers-p2
- fecha: 2026-10-08
- rama: develop
- skill: (flujo estándar) PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
- fase: IMPLEMENT de los P2 seleccionados de la FASE 1 de `drivers-connections-audit` + VERSION (v0.35.7)

## Prompt issued
```text
Los problemas de prioridad 2 de FASE 1:
S2/S3: la contraseña aparece en el repr de las configuraciones.
M2: encoding_errors="replace" corrompe datos sin avisar.
G1: get_sqlalchemy_engine() crea un Engine nuevo en cada llamada.
```

## Context supplied
- Sesiones `2026-10-08-drivers-connections-audit-fase1`, `2026-10-08b-hotfix-drivers-p0`, `2026-10-08c-fix-drivers-p1`
- Driver real MariaDB Connector/Python 1.1.14 (última publicada, `pip index versions mariadb`) contra el banco MariaDB 11.4

## AI output summary
- Verificación previa de M2: `mariadb.connect` y `mariadb.ConnectionPool` (1.1.14) rechazan `encoding_errors` **y** `charset` (`TypeError`) → `encoding_errors` nunca se aplicó; la premisa «corrompe datos» era falsa. Problema real: red de seguridad inexistente documentada + 2 intentos fallidos y 2 WARNING por conexión nueva.
- Regresión de v0.35.6 (M1) encontrada al verificar: el conector solo admite sesiones utf8mb4 (`SET NAMES latin1` → `ProgrammingError: Character set 'latin1' is not supported`), así que `init_command` por defecto `SET NAMES <charset>` impedía conectar con `charset="latin1"`. Revertido a `SET NAMES utf8mb4`.
- M2: `encoding_errors: str | None = None`; si llega, se valida, `FutureWarning` y no se envía. `charset` se mantiene en la config (lo usa aiomysql) y lo quitan `MariaDBConnection.connect` y `PoolConnection` antes del driver; `_OPTIONAL_*_PARAMS` = `{"init_command"}`.
- S3: `password: str = field(repr=False)` en las 6 configs con contraseña (pools incluidos por anidación). S2 ya corregido en v0.35.5.
- G1: `_sqlalchemy_engine` cacheado en `SyncDatabaseManager` y `AsyncDatabaseManager`; `close()` hace `dispose`.
- Tests test-first: 18 fallaban antes del fix. Retirados 3 tests que simulaban que el driver aceptaba `charset`/`encoding_errors` (fijaban la premisa falsa).
- `ruff`, `mypy` OK; `pytest` 5246 passed, 497 skipped (`build/logs/fix_drivers_p2_suite.txt`); `tests/integration` 552 passed, 10 skipped, 0 avisos de parámetro rechazado (`build/logs/fix_drivers_p2_integration.txt`); `zensical build --strict` OK.
- Banco: `charset="latin1"` conecta (sync y pool) y lee `'ñandú €'` con sesión utf8mb4 por conexión nativa y por Engine; el Engine se reutiliza.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| M1/M2/S3 | `src/util_bbdd/connection/config.py` | completado |
| Conector MariaDB | `src/util_bbdd/connection/mariadb/connection_mariadb.py`, `pool_connection_mariadb.py` | completado |
| G1 | `src/util_bbdd/managers/sync_mgr.py`, `src/util_bbdd/managers/async_mgr.py` | completado |
| Datos y docs | `data/database_types.json`, `docs/guides/connection_guide.md`, `docs/api/connection_factory.md`, `docs/guides/troubleshooting.md`, `docs/guides/mariadb_v0.35.0_charset_handling.md` | completado |
| Tests | `tests/unit/connection/test_config_repr_secrets.py`, `tests/unit/test_manager_sqlalchemy_engine_cache.py`, `tests/unit/connection/mariadb/test_mariadb_charset_init_command.py`, `tests/unit/connection/mariadb/test_mariadb_driver_connection.py` | completado |
| VERSION | `CHANGELOG.md` [0.35.7] + campos de versión | completado |

## Directrices para Futuras IAs
- **[MariaDB Connector/Python]**: 1.1.14 (la última) solo trabaja en utf8mb4 y **no admite** `charset` ni `encoding_errors` en `connect()` ni en `ConnectionPool()`; `init_command` sí. Nunca derivar el `SET NAMES` del sync de `charset`. `charset` solo lo consume aiomysql (async).
- **[verificación de premisas]**: antes de «arreglar» un parámetro de driver, comprobar contra el driver real que lo acepta: el reintento defensivo (`_OPTIONAL_*_PARAMS`) puede ocultar durante versiones que un parámetro nunca se aplica.
- **[regresión v0.35.6]**: el cambio M1 de v0.35.6 se validó solo con tests unitarios; los cambios en parámetros de conexión necesitan una conexión real al banco (MariaDB con `charset` no por defecto incluido).
- **[managers/Engine]**: `get_sqlalchemy_engine()` devuelve el mismo Engine hasta `close()`; quien lo use no debe hacerle `dispose` esperando uno nuevo (se recrea al cerrar el manager).
- **[configs/secretos]**: los campos con secretos de las `*Config` llevan `field(repr=False)`; mantenerlo al añadir campos sensibles.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Bug previo detectado (no corregido): `SyncDatabaseManager.close()` termina con un bloque pegado (`sync_mgr.py`, tras `close_resources`) que lanza `DatabaseOperationError` si `sync_query_executor` no está inicializado.
- Resto de P2 de FASE 1 (M5–M7, P2–P6, Q2–Q3, L1, H1–H2, G2, O2) y FASE 2 de la skill.
- Commit propuesto, no ejecutado; push y tag `v0.35.7` pendientes.
