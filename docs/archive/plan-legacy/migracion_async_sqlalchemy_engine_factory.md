# Migracion AsyncIO de SQLAlchemyEngineFactory

## 1. Objetivo
Implementar una factoria async-first para `src/util_bbdd/factory/sqlalchemy_engine_factory.py` que soporte:
- Conexiones directas.
- Conexiones con pool.
- Ruta por motor con errores claros.

Restriccion:
- Sin compatibilidad hacia atras.

## 2. Decisiones tomadas

### 2.1 Refactorizacion vs clases nuevas
Decision: clases nuevas async para este modulo.

Implementacion propuesta:
- Nueva clase `AsyncSQLAlchemyEngineFactory`.
- API principal: `async def create_engine(...) -> AsyncEngine`.

Justificacion:
- Evita mezclar paths sync y async en una misma clase.
- Reduce regresiones al tener contratos explicitos.
- Simplifica tests y mantenimiento.

### 2.2 Soporte direct y pool
Decision: exponer ambos modos desde la API async.

- `use_pool=True`: pool async de SQLAlchemy.
- `use_pool=False`: `NullPool` para conexion directa.

### 2.3 Motores
- PostgreSQL: soportado (`postgresql+asyncpg`).
- SQLite: soportado (`sqlite+aiosqlite`).
- MariaDB: soportado (`mysql+aiomysql`).
- Oracle: soportado (`oracle+oracledb`, validando entorno).
- SQL Server: soportado condicional (`mssql+aioodbc`).
- HSQLDB: no soportado async, error explicito.

### 2.4 Errores y seguridad
- Mantener `DatabaseValidationError` y `DatabaseConnectionError`.
- Encadenar excepciones con `raise ... from err`.
- No loggear credenciales en claro.

## 3. Hallazgos del estado actual
En el modulo actual se detectan puntos a corregir en la version async:
- Uso de API sync (`sqlalchemy.create_engine`).
- Health-check sync (`SELECT 1` sin `await`).
- Password enmascarada usada en connection string real en algunos motores (rompe conexion).

## 4. Diseno tecnico objetivo

### 4.1 Firma sugerida
```python
@staticmethod
async def create_engine(
    db_type: str,
    conn_params: dict[str, Any],
    database: str | None = None,
    use_pool: bool = True,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_timeout: int = 30,
    pool_recycle: int = 1800,
    sql_server_driver: str = "aioodbc",
) -> AsyncEngine:
    ...
```

### 4.2 Flujo interno
1. Normalizar `db_type`.
2. Construir URL async por motor.
3. Construir `engine_kwargs`:
   - `echo=False`, `pool_pre_ping=True`.
   - Si `use_pool=False`: `poolclass=NullPool`.
   - Si `use_pool=True`: aplicar `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle` donde aplique.
4. Crear engine con `create_async_engine`.
5. Validar conexion:
```python
async with engine.connect() as conn:
    await conn.execute(text("SELECT 1"))
```
6. Retornar `AsyncEngine`.

## 5. Plan de migracion

### PR-00 Base async de la factoria
- Estado: completado.
- Crear `AsyncSQLAlchemyEngineFactory`.
- Cambiar imports a `sqlalchemy.ext.asyncio`.
- Implementar `create_engine` async.
- Soportar `use_pool` y `NullPool`.
- Health-check async.

DoD:
- Se crea `AsyncEngine` en modo direct/pool.

### PR-01 PostgreSQL y SQLite
- Estado: completado.
- PostgreSQL: builder `postgresql+asyncpg://...`.
- SQLite: builder `sqlite+aiosqlite://...`.
- Tests unitarios de URL, validaciones y health-check mockeado.

DoD:
- Ambos motores en verde.

### PR-02 MariaDB
- Estado: completado.
- Builder `mysql+aiomysql://...`.
- Validacion de password y parametros.
- Tests direct/pool.

DoD:
- MariaDB en verde.

### PR-03 Oracle
- Estado: completado.
- Builder `oracle+oracledb://...` con `service_name`.
- Validaciones de parametros.
- Tests de errores y URL.

DoD:
- Oracle en verde.

### PR-04 SQL Server
- Estado: completado.
- Builder `mssql+aioodbc://...`.
- Validar dependencias/dialecto.
- Tests para dependencia faltante y URL.

DoD:
- SQL Server en verde con manejo de error claro.

### PR-05 HSQLDB no soportado
- Rechazo explicito para async.
- Test dedicado de rechazo.

DoD:
- Mensaje de error claro: `hsqldb async no soportado`.

### PR-06 Cierre
- Actualizar README y CHANGELOG.
- Ejecutar suite completa.

DoD:
- Documentacion alineada con soporte real.

## 6. Prompt maestro de implementacion
Implementa migracion async-first en `src/util_bbdd/factory/sqlalchemy_engine_factory.py` sin compatibilidad hacia atras.

Requisitos:
1. Reemplazar flujo sync por `create_async_engine`.
2. Exponer API async unica para crear engine.
3. Soportar `use_pool=True` y `use_pool=False`.
4. Implementar builders por motor:
   - PostgreSQL: `postgresql+asyncpg`
   - SQLite: `sqlite+aiosqlite`
   - MariaDB: `mysql+aiomysql`
   - Oracle: `oracle+oracledb`
   - SQL Server: `mssql+aioodbc`
   - HSQLDB: no soportado
5. Hacer health-check async `SELECT 1`.
6. No usar password enmascarada en URL real.
7. Manejar errores con `raise ... from err`.
8. Agregar tests unitarios con mocks, sin DB real.
9. Mantener estilo y tipado del proyecto.

## 7. Prompts por motor

### PostgreSQL
- Usar URL `postgresql+asyncpg://user:password@host:port/database`.
- Si falta password: `DatabaseValidationError`.
- Tests: URL, validacion, health-check mockeado.

### SQLite
- Usar `sqlite+aiosqlite:///:memory:` o `sqlite+aiosqlite:///{path}`.
- Tests: memoria, path relativo/absoluto, direct sin pool.

### MariaDB
- Usar `mysql+aiomysql://user:password@host:port/database`.
- Tests: validaciones + pool params.

### Oracle
- Usar `oracle+oracledb://user:password@host:port/?service_name=...`.
- Tests: fallback de `service_name` y validaciones.

### SQL Server
- Usar `mssql+aioodbc://...`.
- Fail-fast si falta dependencia async.
- Tests: URL y errores.

### HSQLDB
- No implementar async.
- Lanzar error explicito al solicitar `hsqldb`.

## 8. Archivos de test sugeridos
- `tests/test_async_sqlalchemy_engine_factory.py`

Casos minimos:
- Creacion de `AsyncEngine` por motor soportado (mock).
- `use_pool=False` usa `NullPool`.
- Error por parametros faltantes.
- Rechazo de `hsqldb`.
- Verificacion de health-check async.
- Logs sin credenciales.

## 9. Riesgos y mitigaciones
- Compatibilidad de dialectos async por version.
  - Mitigacion: fijar minimos en `pyproject.toml`.
- SQL Server async dependiente de stack ODBC.
  - Mitigacion: validacion temprana y mensaje de instalacion.
- Fugas de conexion.
  - Mitigacion: tests de cierre y uso de context managers async.

## 10. Criterios de aceptacion
- API sync removida o fuera de uso en este modulo.
- Soporte direct/pool funcional en async.
- Motores soportados cubiertos con tests.
- HSQLDB async rechazado explicitamente.
- README/CHANGELOG actualizados con matriz final.
