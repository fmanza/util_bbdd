# TRACEABILITY

## Session metadata
- id: 2026-10-08c-fix-drivers-p1
- fecha: 2026-10-08
- rama: develop
- skill: (flujo estándar) PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
- fase: IMPLEMENT de los P1 de la FASE 1 de `drivers-connections-audit` + VERSION (v0.35.6)

## Prompt issued
```text
IMPLMENT Los problemas de prioridad 1 de FASE 1
```
(P1 listados en `.ai/sessions/2026-10-08-drivers-connections-audit-fase1/TRACEABILITY.md`: Q1, Y3, M3/Y2, M1, P1, O1.)

## Context supplied
- Informe de FASE 1 y sesión `2026-10-08b-hotfix-drivers-p0` (v0.35.5)
- Fuente de PyMySQL (`Connection.__init__`, `_create_ssl_ctx`), firma de `pymssql.connect` 2.3.13 y de `aiomysql.connect`
- Banco `util_bbdd_bench_*` (MySQL 8, SQL Server, MariaDB 11.4, PostgreSQL, Oracle)

## AI output summary
- Test-first: 17 tests nuevos fallaban antes del fix (más 4 de SQL Server y 3 de `Encrypt` añadidos al validar contra el banco).
- Q1: `_connect_pymssql` traduce `encryption`; verificación fail-closed con `sys.dm_exec_connections` para `mandatory`. Validación real: el wheel de pymssql para Windows (FreeTDS 1.4.27) acepta `require` y **no cifra** (`encrypt_option=FALSE`); `CONNECTIONPROPERTY('encrypt_option')` no existe (NULL) → descartado.
- Bug nuevo al validar Q1: cadena ODBC `Server={host},puerto` (CNX-02, v0.11.0) rechazada por el Driver Manager (`01S00`) → pyodbc/aioodbc no conectaban. Fix `Server={host,puerto}`. ODBC Driver 18 rechaza `Encrypt=off` → `yes`/`no` (`SQLServerConnection.odbc_encrypt`). Resultado real: `mandatory` → `encrypt_option=TRUE` en pyodbc y aioodbc.
- Y3: `pop_mysql_ssl_options` + `build_ssl_context` (semántica de PyMySQL); aiomysql recibe `ssl=SSLContext`. Bug sync encontrado leyendo PyMySQL: `ssl_verify_*` sueltos hacían perder CA/cert → ahora dentro del dict. Validación real: TLS sync OK; async OK con `SelectorEventLoop`; con `ProactorEventLoop` (Windows) falla también aiomysql directo → limitación documentada.
- Y2: `_driver_root` desenvuelve `_ConnectionFairy`; M3: `CharsetStateDetector.build_diagnosis`, `adiagnose`, `select_strategy`, `inject_convert`; `AsyncManagerCatalogExecutor._charset_safe_sql` (aiomysql, diagnóstico una vez).
- M8 (fallback por `UnicodeDecodeError`) descartado: tras un error de decodificación en mitad del result set, PyMySQL puede quedar desincronizado y el reintento en la misma conexión no es seguro.
- M1: `init_command` por defecto `SET NAMES {charset}`; `charset` validado con `[A-Za-z0-9_]+`.
- P1: JSON (drivers `psycopg`/`asyncpg`, instalación), extra `postgresql` en `pyproject.toml`, `connection_guide.md`, `drivers.md`, `functional/managers_sync.md`.
- O1: ya resuelto en v0.35.5; test añadido (Engine Oracle con solo `dsn`).
- Regla #1 de arquitectura: `connection/sqlserver/connection_sqlserver.py` añadido a `EXCEPTIONS` (estado de cifrado de la sesión, no diccionario de datos).
- `ruff`, `mypy` OK; `pytest` 5231 passed, 497 skipped (`build/logs/fix_drivers_p1_suite.txt`); `tests/integration` 552 passed, 10 skipped (`build/logs/fix_drivers_p1_integration.txt`).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| TLS MySQL | `src/util_bbdd/connection/mysql/connection_mysql.py`, `async_connection_mysql.py` | completado |
| SQL Server | `src/util_bbdd/connection/sqlserver/connection_sqlserver.py`, `async_connection_sqlserver.py` | completado |
| Charset | `src/util_bbdd/metadata/_charset_detection.py`, `_adaptive_executor.py`, `src/util_bbdd/managers/_catalog_executor.py` | completado |
| M1 | `src/util_bbdd/connection/config.py`, `data/database_types.json` | completado |
| P1 | `data/database_types.json`, `pyproject.toml`, `docs/guides/connection_guide.md`, `docs/guides/drivers.md`, `docs/functional/managers_sync.md` | completado |
| Tests | 5 ficheros nuevos + `test_mysql_driver_connection.py`, `test_engine_factory_credentials.py`, `test_architecture_metadata_rules.py` | completado |
| VERSION | `CHANGELOG.md` [0.35.6] + campos de versión | completado |

## Directrices para Futuras IAs
- **[SQL Server/pymssql]**: el wheel de pymssql 2.3.13 para Windows (FreeTDS 1.4.27) acepta `encryption="require"` y no cifra; para TLS real usar pyodbc/aioodbc. `encryption="mandatory"` con pymssql falla en cerrado si `sys.dm_exec_connections` dice `FALSE`.
- **[SQL Server/verificación]**: `CONNECTIONPROPERTY('encrypt_option')` devuelve NULL (no es propiedad válida); el estado de cifrado está en `sys.dm_exec_connections.encrypt_option` (requiere `VIEW SERVER STATE`).
- **[SQL Server/ODBC]**: en la cadena ODBC el puerto va dentro de las llaves (`Server={host,puerto}`) y `Encrypt` debe ser `yes`/`no` para valer en Driver 17 y 18.
- **[MySQL/TLS]**: con PyMySQL nunca pasar `ssl_verify_*` como kwargs junto a un dict `ssl`: si son verdaderos, PyMySQL rehace `ssl` desde `ssl_ca` (vacío). Fuente única: `pop_mysql_ssl_options` / `build_ssl_context`.
- **[aiomysql/Windows]**: TLS con aiomysql falla con `ProactorEventLoop` (default en Windows), también sin la librería; funciona con `WindowsSelectorEventLoopPolicy`.
- **[charset/async]**: el diagnóstico de charset es reutilizable: `CharsetStateDetector.build_diagnosis` (sync) y `adiagnose` (async) comparten consultas (`_VARIABLES_SQL`, …) y reglas; `select_strategy`/`inject_convert` en `metadata/_adaptive_executor.py`.
- **[arquitectura]**: SQL sobre estado de sesión/servidor (`sys.dm_exec_*`, `PRAGMA` de sesión) fuera de `metadata/` se registra en `EXCEPTIONS` de `tests/unit/test_architecture_metadata_rules.py` con su motivo.
- **[M8]**: no añadir fallback por `UnicodeDecodeError` en la misma conexión PyMySQL: tras el error el protocolo puede quedar desincronizado.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- M8 (fallback por `UnicodeDecodeError`) descartado por riesgo; si se retoma, abrir conexión nueva para el reintento.
- `trust_cert` sin equivalente en pymssql (documentado).
- P2 de FASE 1 (S2/S3 repr con contraseña, M2 `encoding_errors="replace"`, M5–M7, P2–P6, Q2–Q3, L1, H1–H2, G1–G2, O2) y FASE 2 de la skill.
- Commit propuesto, no ejecutado.
