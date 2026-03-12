# Migracion Async de Motores BBDD en `util_bbdd`

## 1. Resumen ejecutivo
Se propone migrar la capa de acceso a datos de `util_bbdd` a un modelo **solo async** (sin compatibilidad hacia atras), manteniendo la arquitectura conceptual actual: conectores por motor en `connection/`, factoria de seleccion y resolucion de tipo `direct/pool`, y validacion centralizada de `conn_params`.

Cambios principales:
- Reemplazo de interfaces sync (`get_connection`, `close_connection`, `close`) por contratos async (`acquire`, `release`, `aclose`, `__aenter__`, `__aexit__`).
- Reemplazo de `DatabaseManager` y `DatabaseQueryExecutor` por versiones async-first.
- Unificacion de errores y timeouts async.
- Migracion por fases: una fase por motor.

Descartes:
- **HSQLDB async nativo**: descartado por ausencia de driver async real (depende de JDBC/JayDeBeApi, bloqueante).
- **Doble pooling**: descartado por diseno (si el driver trae pool async, se usa ese).

Beneficios esperados:
- Mejor throughput en cargas IO-bound.
- Menor latencia p95/p99 en escenarios concurrentes.
- Mejor control de backpressure, cancelacion y timeouts.
- Mejor uso de recursos frente a estrategia sync con hilos no controlados.

## 2. Estado actual (inferido del repo)
### Organizacion actual
- Conectores: `src/util_bbdd/connection/**`
- Factoria de conexion directa: `src/util_bbdd/connection/connect_factory.py`
- Factoria de pool: `src/util_bbdd/factory/pool_factory.py`
- Contrato de pool sync: `src/util_bbdd/connection/pool_protocol.py`
- Orquestacion principal: `src/util_bbdd/database_manager.py`
- Executor de consultas: `src/util_bbdd/database_queries.py` (`DatabaseQueryExecutor`)
- Validacion/normalizacion de parametros: `src/util_bbdd/connection/connection_params_manager.py`, `src/util_bbdd/connection/conn_params_builder.py`

### Puntos de extension actuales
- `ConnectFactory.create_connection(db_type, conn_params, db_validator=None, sql_server_driver='pymssql')`
- `PoolFactory.create_pool(db_type, conn_params)`
- `ConnectionPoolProtocol`:
  - `get_connection()`
  - `close_connection(connection)`
  - `close()`
- `DatabaseManager`:
  - `__init__(db_type, conn_params, queries_file=None, use_pool=True)`
  - `_connect()`, `_init_pool()`, `get_connection()`, `close_connection()`, `close()`
- `DatabaseQueryExecutor`:
  - `execute_query(...)`
  - `execute_custom_query(...)`
  - Adquisicion/liberacion de recursos sync

### Como se arma DSN/config y direct vs pool
- `ConnectionParamsManager.prepare_and_validate()` centraliza normalizacion, construccion y validacion de `conn_params`.
- `sanitize_for_connection()` y `sanitize_for_pool()` filtran parametros por motor.
- `DatabaseManager` decide `pool` o `direct`:
  - Si `use_pool` y motor soporta pool (`_supports_pool()`), llama `_init_pool()` y valida con una conexion de prueba.
  - Si no, usa `_connect()` (conexion unica).

### Supuestos explicitados
- Python objetivo minimo recomendado: 3.11.
- No hay uso actual de `asyncio` en `src/util_bbdd/**`.
- Se permite agregar dependencias por motor.

## 3. Decisiones de arquitectura (con justificacion)
### Decision A: API objetivo solo async
- Se elimina API sync del core de acceso a datos.
- Nuevas firmas `async def` en manager, executor y conectores.
- Justificacion: evitar mezcla confusa sync/async y simplificar contratos.

### Decision B: Nuevas abstracciones base
- Crear:
  - `AsyncConnectionProtocol`
  - `AsyncPoolProtocol`
  - `AsyncConnectionFactory`
  - `AsyncPoolFactory`
  - `AsyncDatabaseManager`
  - `AsyncDatabaseQueryExecutor`
- Justificacion: romper API sin arrastrar deuda tecnica de compatibilidad.

### Decision C: Contrato uniforme direct/pool
- Contrato propuesto:
  - `async connect()` para direct
  - `async acquire()` / `async release(conn)` / `async aclose()` para pool
  - `async with manager.connection()` para obtener/liberar recurso
- Justificacion: simplifica ejecucion y trazabilidad.

### Decision D: Errores normalizados
- Mantener jerarquia actual (`DatabaseConnectionError`, `DatabaseOperationError`, etc.) con mensajes consistentes async.
- Propagar excepciones con `raise ... from err`.

### Decision E: Telemetria minima
- Logging estructurado por operacion: `db_type`, `mode=direct|pool`, `query_name`, `elapsed_ms`, `timeout`.
- Sin instrumentacion invasiva en fase inicial.

### Decision F: Evitar pooling doble
- Si driver ofrece pool async nativo: usarlo.
- Si no ofrece: wrapper propio con `asyncio.Queue` o alternativa justificada.

## 4. Matriz por motor: enfoque recomendado
| Motor | Async nativo (driver) | Pool recomendado | Alternativa | Decision (refactor/nuevo) | Riesgos | Estado |
|---|---|---|---|---|---|---|
| PostgreSQL | `asyncpg` (preferente) o `psycopg.AsyncConnection` | `asyncpg.create_pool` | `psycopg` async pool | **Nuevas clases** (`AsyncPostgreSQL*`) | diferencias de placeholders y tipos | Implementar |
| MariaDB | `asyncmy` (preferente) o `aiomysql` | pool del driver | `run_in_executor` solo transitorio | **Nuevas clases** (`AsyncMariaDB*`) | diferencias MySQL/MariaDB, collation | Implementar |
| Oracle | `oracledb` async thin (si version soporta) | `oracledb.create_pool` async | threadpool controlado si no hay async estable en entorno | **Nuevas clases** (`AsyncOracle*`) | thin/thick mode, DSN complejos | Implementar |
| SQLServer | sin async nativo puro (DB-API), usar `aioodbc` | pool `aioodbc` | threadpool para `pyodbc` | **Nuevas clases** (`AsyncSQLServer*`) | ODBC en Windows/Linux, tuning timeout | Implementar |
| SQLite | `aiosqlite` | sin pool real (1 conn + semaphore) | `run_in_executor` con `sqlite3` | **Nuevas clases** (`AsyncSQLite*`) | lock de escritura, WAL | Implementar (sin pool real) |
| HSQL | no async nativo (JDBC via JayDeBeApi) | N/A | wrapper con threadpool (coste alto) | **Descartar en v2 async** | dependencia JVM, latencia, complejidad | Descartar |

## 5. Plan de migracion por fases (una fase = un motor)
### Fase 0 - Preparacion transversal
Objetivo:
- Introducir infraestructura async comun sin motor especifico.

Archivos a cambiar:
- `src/util_bbdd/connection/async_protocols.py` (nuevo)
- `src/util_bbdd/connection/connect_factory.py` (reemplazo a factory async)
- `src/util_bbdd/factory/pool_factory.py` (reemplazo a factory async)
- `src/util_bbdd/async_database_manager.py` (nuevo)
- `src/util_bbdd/async_database_query_executor.py` (nuevo)
- `src/util_bbdd/connection/connection_params_manager.py` (ajuste para async options)
- `src/util_bbdd/__init__.py` (exports async)

Tests:
- `tests/test_async_contracts.py`
- `tests/test_async_factory_selection.py`
- `tests/test_async_manager_lifecycle.py`

Criterios de aceptacion:
- API async compila y se importa.
- Factoria async selecciona clases por motor.
- Ciclo `acquire/release/aclose` validado con mocks.

### Fase 1 - PostgreSQL
Objetivo:
- Implementar primer motor async end-to-end por viabilidad alta.

Archivos a cambiar:
- `src/util_bbdd/connection/postgresql/async_connection_postgresql.py` (nuevo)
- `src/util_bbdd/connection/postgresql/async_pool_connection_postgresql.py` (nuevo)
- `src/util_bbdd/connection/connect_factory.py`
- `src/util_bbdd/factory/pool_factory.py`

Tests:
- `tests/connection/postgresql/test_async_postgresql_connection.py`
- `tests/connection/postgresql/test_async_postgresql_pool.py`
- `tests/test_async_db_manager_postgresql.py`

Criterios de aceptacion:
- `async with` + `execute/fetch` funcional en mocks.
- Timeout y cancelacion cubiertos.
- Sin doble pooling.

### Fase 2 - SQLite
Objetivo:
- Incorporar motor local para pruebas deterministas CI.

Archivos a cambiar:
- `src/util_bbdd/connection/sqlite/async_connection_sqlite.py` (nuevo)
- `src/util_bbdd/connection/sqlite/async_pool_connection_sqlite.py` (nuevo, wrapper 1-conn)
- `src/util_bbdd/connection/connect_factory.py`
- `src/util_bbdd/factory/pool_factory.py`

Tests:
- `tests/connection/sqlite/test_async_sqlite_connection.py`
- `tests/connection/sqlite/test_async_sqlite_transaction.py`

Criterios de aceptacion:
- Soporte `:memory:` estable.
- Escritura serializada sin corrupcion.

### Fase 3 - MariaDB
Objetivo:
- Migrar MariaDB a async nativo del ecosistema MySQL-compatible.

Archivos a cambiar:
- `src/util_bbdd/connection/mariadb/async_connection_mariadb.py` (nuevo)
- `src/util_bbdd/connection/mariadb/async_pool_connection_mariadb.py` (nuevo)
- `src/util_bbdd/connection/connect_factory.py`
- `src/util_bbdd/factory/pool_factory.py`

Tests:
- `tests/connection/mariadb/test_async_mariadb_connection.py`
- `tests/connection/mariadb/test_async_mariadb_pool.py`

Criterios de aceptacion:
- Parametros `charset`, timeouts y pool_size aplicados.
- Operaciones concurrentes sin bloqueo global.

### Fase 4 - Oracle
Objetivo:
- Implementar Oracle async (thin mode preferente).

Archivos a cambiar:
- `src/util_bbdd/connection/oracle/async_connection_oracle.py` (nuevo)
- `src/util_bbdd/connection/oracle/async_pool_connection_oracle.py` (nuevo)
- `src/util_bbdd/connection/connect_factory.py`
- `src/util_bbdd/factory/pool_factory.py`

Tests:
- `tests/connection/oracle/test_async_oracle_connection.py`
- `tests/connection/oracle/test_async_oracle_pool.py`

Criterios de aceptacion:
- Resolucion correcta de DSN (`dsn/service_name/sid`).
- Manejo de errores de cliente Oracle con wrapping consistente.

### Fase 5 - SQLServer
Objetivo:
- Añadir SQL Server async mediante ODBC asíncrono.

Archivos a cambiar:
- `src/util_bbdd/connection/sqlserver/async_connection_sqlserver.py` (nuevo)
- `src/util_bbdd/connection/sqlserver/async_pool_connection_sqlserver.py` (nuevo)
- `src/util_bbdd/connection/connect_factory.py`
- `src/util_bbdd/factory/pool_factory.py`

Tests:
- `tests/connection/sqlserver/test_async_sqlserver_connection.py`
- `tests/connection/sqlserver/test_async_sqlserver_pool.py`

Criterios de aceptacion:
- Compatibilidad Windows/Linux con DSN/driver_name.
- Timeouts de login y query controlados.

### Fase 6 - HSQL (decision final)
Objetivo:
- Formalizar descarte en API async v2.

Archivos a cambiar:
- `src/util_bbdd/connection/connect_factory.py` (marcar no soportado)
- `src/util_bbdd/connection/hsqldb/*` (solo notas/deprecacion si aplica)
- `README.md` y `CHANGELOG.md`

Tests:
- `tests/connection/hsqldb/test_async_hsqldb_not_supported.py`

Criterios de aceptacion:
- Error explicito y documentado al solicitar HSQL async.

## 6. Prompt de implementacion por motor (acciones concretas)
### PostgreSQL - prompt accionable
1. Crear `AsyncPostgreSQLConnection` en `src/util_bbdd/connection/postgresql/async_connection_postgresql.py`.
2. Implementar `async def connect(conn_params) -> AsyncConnection`.
3. Crear `AsyncPostgreSQLPool` en `.../async_pool_connection_postgresql.py` con:
   - `async acquire()`
   - `async release(conn)`
   - `async aclose()`
4. Registrar en `src/util_bbdd/connection/connect_factory.py` y `src/util_bbdd/factory/pool_factory.py`.
5. Definir decision direct/pool en `AsyncDatabaseManager`.
6. Implementar timeouts por query y timeout de acquire.
7. Agregar tests unitarios con mocks del driver async.
8. Consideraciones Windows/Linux:
  - Windows: validar compatibilidad de event loop por defecto con driver.
  - Linux: validar limites de file descriptors en alta concurrencia.
9. Done:
   - `pytest -q` verde
   - cobertura de errores de conexion y timeout
   - uso minimo:

```python
async with AsyncDatabaseManager(db_type="postgresql", conn_params=cfg, use_pool=True) as db:
    rows = await db.execute_query("listar_tablas")
```

### MariaDB - prompt accionable
1. Crear `AsyncMariaDBConnection` y `AsyncMariaDBPool` en `src/util_bbdd/connection/mariadb/`.
2. En pool, mapear `pool_size`, `pool_timeout`, `max_overflow` segun soporte del driver.
3. Ajustar sanitizacion de params en `connection_params_manager.py` para flags async (`connect_timeout`, `read_timeout`).
4. Registrar en `src/util_bbdd/connection/connect_factory.py` y `src/util_bbdd/factory/pool_factory.py`.
5. Tests con mocks del cliente async y fallos de red.
6. Consideraciones Windows/Linux:
  - Windows: verificar DNS/IPv6 en resolucion localhost.
  - Linux: validar TLS/certificados en imagenes slim de contenedor.
7. Done:
   - concurrencia basica con `asyncio.gather`
   - cierre limpio con `await aclose()`

### Oracle - prompt accionable
1. Crear `AsyncOracleConnection` y `AsyncOraclePool` en `src/util_bbdd/connection/oracle/`.
2. Resolver DSN como en sync (`dsn > service_name > sid > database`).
3. Definir claramente thin mode para async; si no disponible en entorno, lanzar error guiado.
4. Registrar en `src/util_bbdd/connection/connect_factory.py` y `src/util_bbdd/factory/pool_factory.py`.
5. Tests de DSN y wrapping de errores.
6. Consideraciones Windows/Linux:
  - Windows: compatibilidad con Oracle Instant Client path.
  - Linux: variables de entorno (`LD_LIBRARY_PATH`) si se usa thick mode.
7. Done:
   - operaciones async de consulta
   - manejo de `DatabaseConnectionError` consistente

### SQLServer - prompt accionable
1. Crear `AsyncSQLServerConnection` y `AsyncSQLServerPool` en `src/util_bbdd/connection/sqlserver/`.
2. Implementar conexion con `aioodbc` y DSN construido desde params.
3. Incluir opciones `driver_name`, `login_timeout`, `encryption`, `trust_cert`.
4. Registrar en `src/util_bbdd/connection/connect_factory.py` y `src/util_bbdd/factory/pool_factory.py`.
5. Agregar retries cortos opcionales en handshake (max 2).
6. Consideraciones Windows/Linux:
  - Windows: validar nombres de driver ODBC instalados.
  - Linux: dependencia de unixODBC y driver msodbcsql.
7. Done:
   - test de timeout
   - test de pool exhaustion/backpressure

### SQLite - prompt accionable
1. Crear `AsyncSQLiteConnection` y `AsyncSQLitePool` en `src/util_bbdd/connection/sqlite/`.
2. Para pool, implementar estrategia de conexion unica + `asyncio.Semaphore(1)`.
3. Activar PRAGMA recomendado (`foreign_keys=ON`, evaluar WAL en archivo).
4. Registrar en `src/util_bbdd/connection/connect_factory.py` y `src/util_bbdd/factory/pool_factory.py`.
5. Tests usando `:memory:` sin servicios externos.
6. Consideraciones Windows/Linux:
  - Windows: rutas con backslash y bloqueo de archivo.
  - Linux: permisos de escritura en volúmenes montados.
7. Done:
   - consistencia en transacciones
   - serializacion de escrituras validada

### HSQL - prompt accionable
1. No implementar clases async HSQL en v2.
2. En `src/util_bbdd/connection/connect_factory.py` y `src/util_bbdd/factory/pool_factory.py`, devolver error explicito:
   - `DatabaseNotSupportedError("hsqldb async no soportado")`.
3. Documentar alternativa (servicio adaptador o ejecucion batch fuera de API async).
4. Done:
   - test de rechazo explicito
   - documentacion actualizada

## 7. Estrategia de pruebas y CI
### Unit tests (sin BD externa)
- Mock de cliente async por motor.
- Fake pool para validar acquire/release/aclose.
- Tests de timeouts, cancelacion y wrapping de excepciones.

### Integracion opcional
- Solo bajo marker `integration`.
- No ejecutar por defecto en CI si requiere servicios externos.

### Comandos sugeridos CI
- `pytest -q`
- `pytest -q -m "not integration"`
- `pytest -q -m integration` (pipeline separado)

## 8. Riesgos, trade-offs y mitigaciones
- Drivers con madurez desigual:
  - Mitigacion: fase piloto PostgreSQL y matriz de capacidades por driver.
- Semantica de transacciones async:
  - Mitigacion: contrato unico de `transaction()` en manager.
- Pool exhaustion y backpressure:
  - Mitigacion: limites estrictos + timeout + errores claros.
- Diferencias de dialecto SQL y placeholders:
  - Mitigacion: capa de queries ya separada por `db_type`.
- Observabilidad limitada:
  - Mitigacion: logging minimo estructurado en cada operacion.

## 9. Checklist final
- [ ] API async consistente en manager/factory/connection/pool.
- [ ] Un solo mecanismo de pooling por motor.
- [ ] Cierre de recursos con `await aclose()` y context managers async.
- [ ] Timeouts/cancelacion definidos.
- [ ] Tests unitarios verdes.
- [ ] Integracion opcional aislada.
- [ ] Imports/dependencias actualizados por motor.
- [x] HSQL async descartado y documentado.

## Prompt final para implementador
Implementa la arquitectura async v2 sin compatibilidad hacia atras siguiendo las fases descritas (Fase 0 a Fase 6), con una PR por fase y un motor por fase. En cada PR:
1. Añade clases async nuevas por motor (no refactor parcial de clases sync).
2. Registra el motor en factorias async.
3. Asegura manejo de errores con `raise ... from err`.
4. Agrega tests unitarios de contrato, timeout y errores.
5. No introduzcas dependencia de servicios externos en tests por defecto.
6. Actualiza `README.md` y `CHANGELOG.md` con decisiones y estado de soporte.

## 10. Backlog ejecutable por PR (orden recomendado)
### PR-00 Infraestructura async base
Objetivo:
- Establecer contratos, manager y factorias async sin implementar motores completos.

Checklist tecnico:
- [ ] Crear `src/util_bbdd/connection/async_protocols.py`.
- [ ] Crear `src/util_bbdd/async_database_manager.py`.
- [ ] Crear `src/util_bbdd/async_database_query_executor.py`.
- [ ] Adaptar `src/util_bbdd/connection/connect_factory.py` para ruteo async.
- [ ] Adaptar `src/util_bbdd/factory/pool_factory.py` para ruteo async.
- [ ] Exportar API async en `src/util_bbdd/__init__.py`.
- [ ] Añadir tests de contrato/factory/manager (`tests/test_async_contracts.py`, `tests/test_async_factory_selection.py`, `tests/test_async_manager_lifecycle.py`).

DoD:
- [ ] `pytest -q` verde.
- [ ] No hay referencias nuevas a APIs sync en el manager async.

### PR-01 PostgreSQL async
Objetivo:
- Primer motor productivo async y referencia de arquitectura.

Checklist tecnico:
- [ ] Crear `src/util_bbdd/connection/postgresql/async_connection_postgresql.py`.
- [ ] Crear `src/util_bbdd/connection/postgresql/async_pool_connection_postgresql.py`.
- [ ] Registrar motor en `src/util_bbdd/connection/connect_factory.py`.
- [ ] Registrar pool en `src/util_bbdd/factory/pool_factory.py`.
- [ ] Tests con mocks (`tests/connection/postgresql/test_async_postgresql_connection.py`, `tests/connection/postgresql/test_async_postgresql_pool.py`, `tests/test_async_db_manager_postgresql.py`).

DoD:
- [ ] `async with AsyncDatabaseManager(...)` funcional.
- [ ] Timeout de acquire y timeout de query cubiertos.

### PR-02 SQLite async
Objetivo:
- Motor local para pruebas deterministas y pipeline sin servicios externos.

Checklist tecnico:
- [ ] Crear `src/util_bbdd/connection/sqlite/async_connection_sqlite.py`.
- [ ] Crear `src/util_bbdd/connection/sqlite/async_pool_connection_sqlite.py` (conexion unica + semaphore).
- [ ] Registrar en factories.
- [ ] Tests (`tests/connection/sqlite/test_async_sqlite_connection.py`, `tests/connection/sqlite/test_async_sqlite_transaction.py`).

DoD:
- [ ] Soporte `:memory:` estable.
- [ ] Escritura serializada sin race conditions.

### PR-03 MariaDB async
Objetivo:
- Soporte async para MariaDB con pool del driver.

Checklist tecnico:
- [ ] Crear `src/util_bbdd/connection/mariadb/async_connection_mariadb.py`.
- [ ] Crear `src/util_bbdd/connection/mariadb/async_pool_connection_mariadb.py`.
- [ ] Registrar en factories.
- [ ] Ajustar sanitizacion async en `src/util_bbdd/connection/connection_params_manager.py`.
- [ ] Tests (`tests/connection/mariadb/test_async_mariadb_connection.py`, `tests/connection/mariadb/test_async_mariadb_pool.py`).

DoD:
- [ ] Soporte de `charset`, `pool_size`, `connect_timeout`.
- [ ] Prueba de concurrencia basica con `asyncio.gather`.

### PR-04 Oracle async
Objetivo:
- Soporte Oracle async con reglas de DSN y errores normalizados.

Checklist tecnico:
- [ ] Crear `src/util_bbdd/connection/oracle/async_connection_oracle.py`.
- [ ] Crear `src/util_bbdd/connection/oracle/async_pool_connection_oracle.py`.
- [ ] Registrar en factories.
- [ ] Tests (`tests/connection/oracle/test_async_oracle_connection.py`, `tests/connection/oracle/test_async_oracle_pool.py`).

DoD:
- [ ] Resolucion `dsn > service_name > sid > database`.
- [ ] Wrapping consistente de errores con `raise ... from err`.

### PR-05 SQLServer async
Objetivo:
- Soporte SQL Server async sobre ODBC.

Checklist tecnico:
- [ ] Crear `src/util_bbdd/connection/sqlserver/async_connection_sqlserver.py`.
- [ ] Crear `src/util_bbdd/connection/sqlserver/async_pool_connection_sqlserver.py`.
- [ ] Registrar en factories.
- [ ] Soportar `driver_name`, `login_timeout`, `encryption`, `trust_cert`.
- [ ] Tests (`tests/connection/sqlserver/test_async_sqlserver_connection.py`, `tests/connection/sqlserver/test_async_sqlserver_pool.py`).

DoD:
- [ ] Backpressure y pool exhaustion cubiertos.
- [ ] Compatibilidad minima validada en Windows y Linux (unit tests/mocks).

### PR-06 HSQL decision explicita
Objetivo:
- Formalizar no soporte async para HSQL en v2.

Checklist tecnico:
- [x] En factories, devolver error explicito para `hsqldb` async no soportado.
- [x] Test de rechazo agregado en `tests/test_async_factory_selection.py`.
- [ ] Actualizar `README.md` y `CHANGELOG.md`.

DoD:
- [ ] Mensaje de error claro y documentado.

## 11. Comandos de trabajo por PR
- Validacion rapida: `pytest -q`
- Solo unitarios: `pytest -q -m "not integration"`
- Coverage focalizado: `pytest tests/connection -q`

## 12. Criterio de merge global
- [ ] Cada PR es autocontenido y mergeable.
- [ ] No rompe la API async definida en PR-00.
- [ ] Mantiene consistencia de excepciones y logging.
- [ ] Incluye pruebas y notas de cambio.
