# Normalización `execute_query` / `execute_custom_query` (sync vs async), SRP/SOLID y plan PR

## 1) Resumen ejecutivo
- Se propone unificar el contrato de ejecución de consultas para que **sync y async devuelvan el mismo tipo de resultado** y con la misma semántica.
- Decisión principal: usar **listas para resultados múltiples** en ambos caminos (`Rows = list[Row]`) y separar explícitamente el caso de una sola fila (`Row | None`) en métodos distintos (`*_one`) para evitar contratos ambiguos por `fetch_one`.
- Se elimina duplicidad de responsabilidades: hoy la lógica está repartida entre `DatabaseManager`, `AsyncDatabaseManager`, `DatabaseQueryExecutor`, `SyncQueryExecutor`, `AsyncQueryExecutor`.
- Resultado esperado: paridad funcional sync/async, SRP real, mejor trazabilidad de errores (`raise ... from err`), y reducción de bugs por diferencias de drivers (tuple/list/awaitables).

## 2) Estado actual (inspección obligatoria)

### Hallazgos clave en archivos foco
- `src/util_bbdd/async_database_manager.py`
  - `execute_query` y `execute_custom_query` están en el manager (`:115`, `:96`) y delegan a `AsyncQueryExecutor`.
  - Métodos metadata (`get_tables`, `get_columns`, etc.) devuelven `async def ... -> list[Any]`, pero en runtime dependen de lo que devuelva `cursor.fetchall()` del driver async.
- `src/util_bbdd/database_manager.py`
  - `execute_query` y `execute_custom_query` (`:1261`, `:1290`) delegan a `DatabaseQueryExecutor` (clase legacy dentro de `database_queries.py`), no a `SyncQueryExecutor`.
  - Métodos metadata (`get_tables`, `get_views`, etc.) devuelven `list` y además cachean resultados.
- `src/util_bbdd/database_queries.py`
  - Contiene `DatabaseQueries` (catálogo/resolución parcial), pero también `DatabaseQueryExecutor` (`:770`) con ejecución SQL, materialización, fallback por motor, convenience API y batch.
  - Tiene `execute_query` (`:905`) y `execute_custom_query` (`:1851`) duplicando responsabilidad con otros ejecutores.
- `src/util_bbdd/executors/sync_query_executor.py`
  - `execute_query` (`:65`) y `execute_custom_query` (`:148`) con timeout por llamada y wrapping de errores consistente.

### Tabla de estado actual

| Archivo | Método | Responsabilidad actual | Problemas (duplicidad/SRP/bugs) | Propuesta |
|---|---|---|---|---|
| `async_database_manager.py` | `execute_query`, `execute_custom_query` | Orquestar + delegar en executor async | Contrato `Any`; sin normalización explícita list/tuple; sin timeout por llamada | Mantener solo orquestación fina + tipado fuerte (`Rows`, `Row|None`) |
| `database_manager.py` | `execute_query`, `execute_custom_query` | Orquestación, logging y wrap de errores | Duplica capa pública con `DatabaseQueryExecutor`; sync manager no usa `SyncQueryExecutor` | Reencaminar a un único `SyncQueryExecutor` normalizado |
| `database_queries.py` (`DatabaseQueryExecutor`) | `execute_query`, `execute_custom_query` | Ejecuta SQL, valida, fallback por motor, materializa, convenience methods | Clase sobredimensionada (SRP roto), duplica con `SyncQueryExecutor`, mezcla catálogo+ejecución+adaptación por motor | Extraer por componentes: `QueryCatalog`, `QueryService`, `ExecutionAdapter`, `ResultNormalizer` |
| `sync_query_executor.py` | `execute_query`, `execute_custom_query` | Resolver query, ejecutar, timeout, wrap errores | No normaliza salida a contrato único; cursor no se cierra explícitamente | Añadir `ResultNormalizer` y cierre de cursor/recursos consistente |

### Diferencias sync vs async observadas
- Sync (`SyncQueryExecutor`) usa timeout por parámetro (`timeout`).
- Async (`AsyncQueryExecutor`) usa `self.query_timeout` (estado de instancia), no por llamada.
- Async usa `await conn.cursor()` y `await cursor.execute(...)` directamente; si el driver mezcla métodos sync/async puede fallar (falta normalización tipo `maybe_await` en executor).
- `DatabaseManager` sync va por `DatabaseQueryExecutor`; `AsyncDatabaseManager` async va por `AsyncQueryExecutor`: **paridad incompleta de arquitectura**.

## 3) Decisiones clave (ADR-style)

### 3.1 Contrato de retorno: list vs tuple
- Se adopta la preferencia solicitada: **lista siempre para resultados múltiples**.
- Contrato final:
  - `Row = tuple[Any, ...]`
  - `Rows = list[Row]`
  - `execute_query_many(...) -> Rows`
  - `execute_query_one(...) -> Row | None`
  - `execute_custom_many(...) -> Rows`
  - `execute_custom_one(...) -> Row | None`
- Cambio deliberado: eliminar `fetch_one: bool` en API pública (breaking) para evitar unión implícita `Row | Rows` y reducir errores de consumo.

### 3.2 Dónde vive cada responsabilidad (SRP)
- `QueryCatalog` (reutilizar `QueryRegistry`): solo carga/expone plantillas SQL.
- `QueryResolver` (ya existe): valida/interpola por motor.
- `QueryExecutor` sync/async: solo ejecuta SQL preparado y devuelve filas crudas.
- `ResultNormalizer` (nuevo): normaliza driver output a `Rows`/`Row|None` y materializa LOBs.
- `DatabaseManager` / `AsyncDatabaseManager`: solo orquestan y exponen API de alto nivel.
- `DatabaseQueries`: reducir a wrappers de nombres (o retirarlo de ejecución).

### 3.3 Paridad sync/async
- APIs pareadas obligatorias:
  - Managers: mismos métodos y misma semántica (con `await` en async).
  - Executors: mismo set (`execute_*_many`, `execute_*_one`, timeout por llamada).
- Compartir solo código puro:
  - Validación/resolución de query.
  - Normalización de resultados.
  - Construcción de errores de dominio.
- No mezclar runtime sync/async; solo compartir helpers puros.

### 3.4 Manejo de errores y logging
- Reusar jerarquía existente en `database_exceptions.py` como base (`DatabaseError`, `QueryError`, `QueryTimeoutError`, etc.).
- Regla única:
  - Re-lanzar de dominio sin envolver.
  - Al envolver error de infraestructura: `raise DomainError(...) from err`.
- Logging:
  - Incluir `query_name`, `db_type`, `elapsed_ms`, `row_count`.
  - No loggear credenciales ni SQL con datos sensibles interpolados.

### 3.5 Limpieza de dependencias
- `pytest-asyncio`, `ruff`, `black` ya están en `pyproject.toml` (extra `dev`): no hace falta añadirlas.
- Limpiar imports no usados y rutas públicas rotas:
  - `src/util_bbdd/__init__.py` importa `async_database_query_executor` pero el archivo está eliminado (estado actual roto).

## 4) Prompt con cambios a realizar por motor (obligatorio)

### SQL Server
- Estado actual: plantillas con `{database}`, `{tabla}`, `{esquema}`; consultas metadata extensas en `sql_queries.json`.
- Decisión: mantener `Row=tuple`, normalizar siempre salida a `Rows`.
- Cambios:
  - Validación de schema/db en validador específico.
  - `ResultNormalizer` único (sin branch específico salvo decode puntual).
  - Timeout homogéneo por llamada en sync/async.
- Riesgos/bugs:
  - SQL interpolado con `.format` puede inyectar identificadores no sanitizados.
- Tests:
  - contrato `Rows`, `raise ... from`, timeout, custom parametrizada.

### MariaDB
- Estado actual: fallback especial HEX en `DatabaseQueryExecutor` para columnas/rutinas.
- Decisión: conservar fallback pero encapsularlo en adaptador de motor (no en ejecutor genérico).
- Cambios:
  - mover lógica `_get_mariadb_columns_with_hex_fallback` y similares a componente dedicado.
  - normalizar resultado final como `Rows`.
- Riesgos/bugs:
  - duplicación de fallback entre rutas legacy.
  - interpolación de strings en SQL custom.
- Tests:
  - fallback HEX, contrato `Rows`, wrapping de errores, timeout.

### Oracle
- Estado actual: consultas con `esquema`; soporte de rutinas empaquetadas en ruta legacy.
- Decisión: mantener semántica Oracle (owner/schema), mover particularidades a adaptador Oracle.
- Cambios:
  - validación de identificadores Oracle y límites de longitud.
  - normalización de DDL/LOB en un punto único.
- Riesgos/bugs:
  - múltiples rutas de DDL (normal/fallback) mezcladas en clase genérica.
- Tests:
  - packaged routines, `execute_*_one`, error wrapping, timeout.

### HSQLDB
- Estado actual: validación básica, reglas de nombre de tabla, varias consultas de metadata.
- Decisión: sin reglas extra si no aportan valor; mantener minimalismo.
- Cambios:
  - normalización de retorno y timeout homogéneo.
- Riesgos/bugs:
  - validación de `table` vs `tabla` no totalmente coherente.
- Tests:
  - contrato `Rows`, validación mínima y errores de dominio.

### PostgreSQL
- Estado actual: usa placeholders `{database}` para schema; consulta `create_view` con `{esquema}.{tabla}`.
- Decisión: mantener schema-context actual pero tipar y normalizar salida de forma uniforme.
- Cambios:
  - alinear validator (`database`/`schema`) con placeholders reales.
  - timeout por llamada en async también.
- Riesgos/bugs:
  - escape global de `%` en async executor puede alterar SQL no-MariaDB.
- Tests:
  - contrato `Rows`, timeout, manejo de placeholders/schemas.

### SQLite
- Estado actual: `PRAGMA` y consultas sin schema real; algunas queries retornan vacío deliberado.
- Decisión: normalización estándar sin paths específicos salvo tipos vacíos.
- Cambios:
  - garantizar `Rows` incluso en respuestas vacías de pragmas.
- Riesgos/bugs:
  - `execute_custom_query` sin validación puede ejecutar SQL arbitrario.
- Tests:
  - retorno vacío consistente, timeout async/sync, error wrapping.

## 5) Plan de acción en formato PRs (obligatorio)

### PR 1 — Inventario + base de exceptions + contrato de retorno
Checklist:
- [ ] `src/util_bbdd/result_types.py` (nuevo): `Row`, `Rows`, `RowOrNone`
- [ ] `src/util_bbdd/database_exceptions.py`: consolidar aliases/errores de query
- [ ] `tests/unit/test_contract_return_types.py`
- [ ] Revisar/encapsular uso de `maybe_await` en capa executor async

Criterios de aceptación:
- [ ] `pytest -q` pasa
- [ ] contrato de retorno documentado en docstrings y typing

### PR 2 — Extraer `ResultNormalizer` y eliminar diferencias list/tuple
Checklist:
- [ ] `src/util_bbdd/result_normalizer.py` (nuevo)
- [ ] `src/util_bbdd/executors/sync_query_executor.py` usa normalizer
- [ ] `src/util_bbdd/executors/async_query_executor.py` usa normalizer
- [ ] `tests/unit/test_result_normalizer.py`
- [ ] `tests/unit/test_async_sync_parity_results.py`

Criterios:
- [ ] sync y async devuelven mismo tipo y estructura

### PR 3 — Unificar responsabilidades de `execute_query` / `execute_custom_query`
Checklist:
- [ ] API pública nueva: `execute_query_many/one`, `execute_custom_many/one`
- [ ] `src/util_bbdd/database_manager.py` simplificado a orquestación
- [ ] `src/util_bbdd/async_database_manager.py` equivalente async
- [ ] `src/util_bbdd/database_queries.py` reducir SRP (catálogo/wrappers) o eliminar `DatabaseQueryExecutor`
- [ ] `tests/unit/test_execute_query_contract.py`
- [ ] `tests/unit/test_execute_custom_query_contract.py`

Criterios:
- [ ] no hay duplicación de la misma responsabilidad en múltiples clases
- [ ] métodos sync/async tienen misma semántica

### PR 4 — Paridad funcional completa + validaciones por motor
Checklist:
- [ ] `src/util_bbdd/validators/` alinear validación por placeholders reales
- [ ] `src/util_bbdd/executors/motor_adapters/` (nuevo, si aplica) para MariaDB/Oracle especiales
- [ ] `tests/unit/test_validations_by_motor.py`
- [ ] `tests/unit/test_error_wrapping_raise_from.py`

Criterios:
- [ ] validación coherente y testeada por motor
- [ ] errores envueltos con `raise ... from err`

### PR 5 — Limpieza final (deps, PEP8, hidden bugs)
Checklist:
- [ ] eliminar imports no usados
- [ ] resolver export roto en `src/util_bbdd/__init__.py` (`async_database_query_executor` no existe)
- [ ] revisar fugas de cursor/conexión y awaits condicionales
- [ ] ejecutar `ruff`/formato ya configurados en repo
- [ ] `tests/unit/test_timeout_behavior.py`

Criterios:
- [ ] `pytest -q` pasa
- [ ] codebase más simple y coherente

## 6) Posibles bugs/errores ocultos (lista obligatoria)
- `DatabaseManager` usa `DatabaseQueryExecutor` legacy mientras existe `SyncQueryExecutor`: paridad arquitectónica rota.
- `AsyncQueryExecutor` hace `await conn.cursor()` y `await cursor.execute(...)` sin normalizar awaitable/no-awaitable.
- Escape global `resolved.final_sql.replace("%", "%%")` en async puede romper SQL no-MariaDB.
- Interpolación `.format(**params)` en `QueryResolver` mete valores directamente en SQL; riesgo de SQL injection si se pasa input no confiable.
- `execute_custom_query` no tiene política mínima de seguridad (bloqueo/allowlist/advertencias).
- Posibles fugas de cursor en ejecutores sync/async (no cierre explícito homogéneo).
- Inconsistencia pública actual: `src/util_bbdd/__init__.py` exporta `AsyncDatabaseQueryExecutor` desde módulo inexistente (import roto).
- Capturas amplias `except Exception` con fallback silencioso en algunas rutas (`temp_tablespaces`, etc.) pueden ocultar fallos reales.

## 7) Tests (requisitos mínimos)
- Añadir unit tests sin DB real:
  - `tests/unit/test_contract_return_types.py`: `Rows` en sync/async.
  - `tests/unit/test_async_sync_api_parity.py`: introspección de métodos públicos pareados.
  - `tests/unit/test_timeout_behavior.py`: timeout sync por deadline y async por `asyncio.timeout`.
  - `tests/unit/test_error_wrapping_raise_from.py`: preservar `__cause__`.
  - `tests/unit/test_custom_query_safety.py`: advertencia/validación de SQL custom.
  - `tests/unit/test_validations_by_motor.py`: SQLServer, MariaDB, Oracle, HSQLDB, PostgreSQL, SQLite.
- Ajustar tests existentes:
  - `tests/unit/test_async_database_manager.py` contiene referencias legacy (`AsyncDatabaseQueryExecutor`) incompatibles con estado actual.

## 8) Impacto en la rama + incompatibilidades
- Qué hace hoy la rama:
  - Ya introdujo `QueryRegistry`, `QueryResolver`, `SyncQueryExecutor`, `AsyncQueryExecutor`.
  - Mantiene simultáneamente el camino legacy `DatabaseQueryExecutor` en `database_queries.py`.
- ¿Cumple el objetivo actual?
  - Parcialmente: hay mejora, pero no hay normalización completa ni SRP estricto.

### Incompatibilidades propuestas (sin backward compatibility)
- Renombrar/eliminar:
  - `execute_query(..., fetch_one=...)` -> `execute_query_many` / `execute_query_one`.
  - `execute_custom_query(..., fetch_one=...)` -> `execute_custom_many` / `execute_custom_one`.
- Import paths:
  - retirar alias/exports legacy (`AsyncDatabaseQueryExecutor`, `DatabaseQueryExecutor` público).
- Tipos:
  - resultados múltiples siempre `Rows`.
  - resultado unitario `Row | None`.
- `maybe_await`:
  - encapsulado dentro de executor async; no depender de él desde código consumidor.

## 9) Seguridad, rendimiento, dependencias, migraciones

### Seguridad
- Reglas para `execute_custom_*`:
  - exigir parámetros enlazados (sin concatenación manual para datos).
  - opcional: bloquear sentencias peligrosas fuera de una allowlist configurable.
  - sanitizar logging (no secretos, no SQL con datos sensibles en claro).

### Rendimiento
- `list` vs `tuple`:
  - coste de `list(...)` existe, pero compensa por contrato uniforme para consumidores.
  - evitar doble copia centralizando normalización en `ResultNormalizer` (un único punto).
- Mantener posibilidad futura de streaming (`iter_rows`) sin romper contrato principal.

### Dependencias
- No añadir dependencias nuevas: `pytest-asyncio`, `ruff`, `black` ya existen en extras `dev`.
- Limpieza:
  - eliminar imports no usados.
  - corregir exports públicos rotos.

### Migración (pasos mínimos para consumidores)
- Cambiar llamadas:
  - `execute_query(..., fetch_one=False)` -> `execute_query_many(...)`
  - `execute_query(..., fetch_one=True)` -> `execute_query_one(...)`
  - análogo para `execute_custom_*`.
- Actualizar imports a clases/paths nuevos de executor.
- Revisar código que esperaba `tuple` en colecciones async; ahora recibirá `list[tuple]`.
- Ejecutar suite de tests de contrato sync/async tras migración.

