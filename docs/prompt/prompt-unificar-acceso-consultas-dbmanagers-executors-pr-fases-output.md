# Unificacion de acceso a consultas (sync/async), executors SRP y plan PR por fases

## 1. Resumen ejecutivo
- Problema actual: hay unificacion parcial, pero todavia conviven rutas duplicadas (legacy y nuevas) para resolver/ejecutar consultas en sync y async.
- Objetivo: dejar una arquitectura unica por responsabilidad, con API publica clara, sin backward compatibility, y paridad real sync/async.
- Resultado esperado:
  - Un solo flujo para consultas registradas: `QueryRegistry -> QueryResolver -> SyncQueryExecutor/AsyncQueryExecutor -> DatabaseManager/AsyncDatabaseManager`.
  - API publica final sin `fetch_one` booleano: solo `*_many` y `*_one`.
  - Eliminacion de ejecutores legacy y wrappers legacy.
  - Tests de contrato, timeout y wrapping de errores (`raise ... from err`) sin servicios externos.
  - `README.md` y `CHANGELOG.md` actualizados con breaking changes.

## 2. Estado actual (inspeccion obligatoria)

### 2.1 Como `database_manager.py` obtiene/arma consultas desde `sql_queries.json`
- `DatabaseManager` crea `self.db_queries = DatabaseQueries(...)`.
- `DatabaseQueries` ya integra `QueryRegistry` y `QueryResolver`; `QueryRegistry` carga `src/util_bbdd/data/sql_queries.json`.
- `DatabaseManager.execute_query_many/one` delega a `SyncQueryExecutor`, que resuelve via `resolver.resolve(...)` y ejecuta SQL final.
- Divergencia importante: `DatabaseManager` aun construye y mantiene `DatabaseQueryExecutor` legacy (`self.query_executor`) ademas de `SyncQueryExecutor`.
- Todavia existen wrappers legacy en manager:
  - `execute_query(..., fetch_one=...)`
  - `execute_custom_query(..., fetch_one=...)`

### 2.2 Que hace `async_database_manager.py` hoy y donde diverge del sync
- `AsyncDatabaseManager` inicializa `AsyncQueryExecutor` y usa `QueryResolver` desde el executor.
- Tiene API nueva:
  - `execute_query_many/one`
  - `execute_custom_many/one`
  - `init`, `close`
- Pero mantiene wrappers legacy:
  - `execute_query(..., fetch_one=...)`
  - `execute_custom_query(..., fetch_one=...)`
- Divergencias actuales vs sync:
  - timeout async por estado de instancia (`query_timeout`) en executor, no por llamada.
  - cierre async con `close(mode=...)` y protocolo diferente al sync (`timeout_seconds`, `force`).
  - varias rutas de metadata async aun llaman internamente wrappers legacy con `fetch_one`.

### 2.3 Que informacion consume `database_types.json` y como se expone
- `DatabaseTypeValidator` carga `src/util_bbdd/data/database_types.json`.
- Se expone por API publica de managers:
  - `get_database_type_info/name/description/features/driver_info`
  - `get_required_params`, `get_optional_params`, `get_database_type_examples`, `get_default_port`
- Los validadores por motor (`src/util_bbdd/validators/*.py`) usan reglas por tipo para validar params de query.

### 2.4 Metodos de `database_queries.py` (categorias)
- Basicos:
  - `get_query`, `get_*_query`, `get_storage_inventory_queries`
- Informacion:
  - `get_all_queries`, `get_available_query_names`, `get_query_info`
- Validacion avanzada:
  - `validate_query_for_db_type` y multiples `_validate_*` por motor
- Metadatos:
  - `get_database_metadata`, `get_supported_features`, `get_driver_requirements`, `get_connection_examples`, etc.
- Documentacion:
  - `get_query_documentation`, `export_documentation`, ejemplos por query
- Problema mayor SRP:
  - el mismo archivo contiene tambien `DatabaseQueryExecutor` legacy con logica de ejecucion SQL, fallback por motor y materializacion.

### 2.5 Como `database_documentation.py` consume APIs actuales
- Usa metodos metadata del manager (`get_tables`, `get_views`, `get_columns`, etc.) correctamente.
- Tambien depende de API legacy:
  - `db_manager.execute_query(..., fetch_one=False, ...)`
  - `db_manager.execute_custom_query(..., fetch_one=True, ...)`
  - acceso directo a `db_manager.db_queries` y `db_queries.resolver.resolve(...)`
- Conclusion: si se elimina backward compatibility, `database_documentation.py` requiere ajuste controlado para no romper.

### 2.6 Supuestos y huecos detectados
- Supuesto: la parametrizacion SQL de queries registradas sigue siendo por template con `format(...)` y validacion previa por `QueryResolver`.
- Supuesto: tests de integracion con BD real no forman parte del criterio por defecto.
- Hueco funcional: estilos de placeholders por driver no estan modelados en `database_types.json`; hoy se resuelve antes de ejecutar (SQL final ya interpolada).

## 3. Decisiones de diseno (ADR-style)

### ADR-01: Un solo Query Registry/Store
- Decision: mantener `QueryRegistry` como unico punto de carga de `sql_queries.json`.
- Justificacion: elimina duplicacion de carga y garantiza contrato unico para sync/async.
- Accion: prohibir carga directa de queries fuera de `QueryRegistry`.

### ADR-02: Executors separados y estrictos
- Decision:
  - `QueryResolver`: obtener `QueryDefinition`, validar params, resolver SQL final.
  - `SyncQueryExecutor`: ejecutar solo sync.
  - `AsyncQueryExecutor`: ejecutar solo async.
  - `ValidationExecutor` no se crea como clase nueva; se mantiene estrategia en `validators/` + `QueryResolver`.
- Justificacion: SRP real sin mezclar validacion, resolucion y ejecucion en una clase monolitica.

### ADR-03: Separacion de responsabilidades (manager vs ejecutor vs validacion vs docs)
- Managers (`DatabaseManager`, `AsyncDatabaseManager`):
  - lifecycle de conexion/pool
  - API de alto nivel para consumidores
  - sin logica de SQL raw ni fallbacks por motor
- Executors:
  - ejecucion y timeouts
  - normalizacion de resultados via `ResultNormalizer`
- Validators:
  - reglas por motor y validacion de placeholders/params
- Docs/meta:
  - utilidades de documentacion no ejecutan SQL por rutas legacy
  - deben consumir API publica del manager y resolver dedicado

### ADR-04: API publica final (sin backward compatibility)
- Se mantiene como entrada principal:
  - `DatabaseManager`
  - `AsyncDatabaseManager`
- API de ejecucion final:
  - `execute_query_many(query_name, **params)`
  - `execute_query_one(query_name, **params)`
  - `execute_custom_many(sql, params=None)`
  - `execute_custom_one(sql, params=None)`
- Se eliminan:
  - `execute_query(..., fetch_one=...)`
  - `execute_custom_query(..., fetch_one=...)`
  - acceso publico a ejecutor legacy `DatabaseQueryExecutor`

### ADR-05: Excepciones unificadas y raise chaining obligatorio
- Jerarquia objetivo:
  - `UtilBbddError` (alias semantico de base)
  - `QueryNotFoundError`
  - `QueryValidationError`
  - `QueryParameterError`
  - `QueryTimeoutError`
  - `DatabaseTypeNotSupportedError`
  - `DatabaseOperationError`
- Regla de traduccion:
  - errores de dominio se relanzan sin envolver
  - errores de infraestructura se traducen con `raise DomainError(...) from err`
- Decision adicional: eliminar aliases de compatibilidad legacy en PR final.

### ADR-06: Logging uniforme
- Regla:
  - `logger = logging.getLogger(__name__)`
  - eventos de ejecucion deben incluir: `query_name`, `db_type`, `elapsed_ms`, `result_rows`
  - no loggear secretos ni SQL con datos sensibles.

### ADR-07: Timeout uniforme sync/async
- Sync:
  - mantener timeout por llamada (deadline monotonic) en executor.
- Async:
  - eliminar timeout por estado global de instancia.
  - aplicar timeout por llamada en `AsyncQueryExecutor` (parametro `timeout` en APIs publicas de manager/executor).

## 4. Modelo unificado de consultas y metadata

### 4.1 QueryDefinition
- Campos sugeridos:
  - `name`
  - `db_type`
  - `sql_template`
  - `required_params`
  - `metadata` (origen, tags, capacidades)
- Estado actual: ya existe `QueryDefinition` en `models.py`.

### 4.2 DatabaseTypeDefinition
- Fuente: `database_types.json`.
- Campos minimos:
  - identidad del motor (`name`, `description`, `version_range`)
  - conexion (`required`, `optional`)
  - capacidades (`supported_features`)
  - drivers (`driver_info`)
  - reglas de compatibilidad/metadata.
- Estado actual: existe estructura equivalente y acceso via `DatabaseTypeValidator`.

### 4.3 QueryInfo (informacion y documentacion)
- Entidad de consulta resuelta para UI/docs:
  - `query_name`
  - `db_type`
  - `required_params`
  - `resolved_sql` (sin secretos)
  - `warnings`
  - `metadata` (elapsed, source, feature flags)

### 4.4 Mapa de correspondencia
- `sql_queries.json` -> `QueryDefinition`
- `database_types.json` -> `DatabaseTypeDefinition`
- `QueryDefinition + DatabaseTypeDefinition + params` -> `ResolvedQuery / QueryInfo`

## 5. Prompt con cambios a realizar por motor (obligatorio)

### SQL Server
- Validacion avanzada:
  - schema por defecto `dbo` y limites de nombres (128 chars).
  - mantener reglas en `validators/sqlserver_validator.py`; quitar duplicadas en `database_queries.py`.
- Placeholders:
  - no modelar placeholder nativo de driver en registry; queries registradas se resuelven por template.
- Conveniencia:
  - mantener solo helpers puros de metadata/documentacion si aportan valor.
  - eliminar helpers que ejecutan SQL.
- Tests contrato por motor:
  - resolucion de placeholders `database/esquema/tabla`
  - error por feature no soportada segun `database_types.json`
  - parity sync/async en SQL resuelta.

### MariaDB
- Validacion avanzada:
  - schema/database obligatorios segun query y reglas de identificador.
  - centralizar fallback HEX en modulo dedicado de adaptador de motor (no en `database_queries.py`).
- Placeholders:
  - mantener escape especial de `%` solo donde el driver async lo exija y encapsulado en executor/adaptador.
- Conveniencia:
  - eliminar rutas legacy de fallback en `DatabaseQueryExecutor`.
- Tests:
  - fallback de decode controlado
  - timeout sync/async
  - wrapping con `raise ... from err`.

### Oracle
- Validacion avanzada:
  - `schema` max 30 y formato identificadores.
  - packaged routines: conservar soporte en componente de motor, no en clase generica.
- Placeholders:
  - `esquema`, `rutina`, `tipo_rutina` consistentes con resolver.
- Conveniencia:
  - mover helpers Oracle de `database_queries.py` a servicio Oracle-specific.
- Tests:
  - packaged routine id parse
  - DDL de package/package body
  - feature unsupported control.

### HSQLDB
- Validacion avanzada:
  - reglas minimas de nombres e identificadores.
  - no forzar reglas adicionales si no estan en `database_types.json`.
- Placeholders:
  - mantener `database` (schema) y no introducir variantes nuevas.
- Conveniencia:
  - eliminar wrappers de ejecucion; conservar solo resolucion/documentacion.
- Tests:
  - resolucion basica
  - error claro cuando se pide feature no soportada async.

### PostgreSQL
- Validacion avanzada:
  - manejo explicito de `schema` y reserved schemas.
  - alinear `database` vs `schema` para evitar ambiguedad en queries metadata.
- Placeholders:
  - estandarizar contexto de schema en resolver/manager.
- Conveniencia:
  - retirar duplicados de validacion en `database_queries.py`.
- Tests:
  - schema por defecto y schema explicito
  - timeout y error chaining.

### SQLite
- Validacion avanzada:
  - minima (tabla/query name cuando aplica), sin sobreingenieria.
- Placeholders:
  - queries pragmas sin schema real; contrato `Rows` uniforme.
- Conveniencia:
  - mantener solo helpers necesarios para introspeccion/documentacion.
- Tests:
  - resultados vacios consistentes
  - feature unsupported declarado en metadata.

### Decisiones de descarte (justificadas)
- No se implementa traduccion de placeholders por driver a nivel registry:
  - motivo: hoy el flujo usa SQL template resuelta antes de ejecutar.
- No se mantiene `DatabaseQueryExecutor` legacy:
  - motivo: rompe SRP y duplica Sync/Async executors.
- No se mantiene API `fetch_one`:
  - motivo: contratos ambiguos y duplicacion de caminos.

## 6. Plan PR por fase (checklist exacto por archivo)

### PR 0 - Preparacion y contrato de ruptura
**Objetivo**
- fijar baseline de ruptura, Python objetivo y reglas de test.

**Cambios por archivo**
- [ ] `pyproject.toml` subir `requires-python` a `>=3.11`
- [ ] `src/util_bbdd/database_exceptions.py` retirar aliases de compatibilidad deprecated
- [ ] `tests/unit/test_database_exceptions_pr0.py` actualizar a nomenclatura final (sin aliases)
- [ ] `tests/conftest.py` agregar fakes comunes para sync/async executor tests

**Tests**
- [ ] `tests/unit/test_database_exceptions_pr0.py`
- [ ] `tests/unit/test_contract_return_types.py`

**Criterios de aceptacion**
- [ ] `pytest tests/unit/test_database_exceptions_pr0.py tests/unit/test_contract_return_types.py -q`
- [ ] No hay referencias a aliases deprecated en codigo fuente.

**Incompatibilidades introducidas**
- Eliminacion de aliases legacy en excepciones.
- Requisito minimo Python 3.11.

---

### PR 1 - Registry/Resolver unico y API de resolucion publica
**Objetivo**
- consolidar un solo punto de carga/resolucion y exponerlo desde managers sin `db_queries` directo.

**Cambios por archivo**
- [ ] `src/util_bbdd/query_registry.py` endurecer contrato y errores
- [ ] `src/util_bbdd/query_resolver.py` API estable para `ResolvedQuery`
- [ ] `src/util_bbdd/database_manager.py` agregar metodo publico `resolve_query(...)`
- [ ] `src/util_bbdd/async_database_manager.py` agregar metodo publico `resolve_query(...)` async-safe
- [ ] `src/util_bbdd/database_queries.py` dejar solo capa de conveniencia pura (sin ejecucion)

**Tests**
- [ ] `tests/unit/test_query_registry.py`
- [ ] `tests/unit/test_query_resolver_simplified.py`
- [ ] `tests/unit/test_sync_async_contract.py` (paridad de SQL resuelta)

**Criterios de aceptacion**
- [ ] `pytest tests/unit/test_query_registry.py tests/unit/test_query_resolver_simplified.py tests/unit/test_sync_async_contract.py -q`
- [ ] managers pueden resolver SQL sin exponer `db_queries` internamente.

**Incompatibilidades introducidas**
- consumidores no deben usar `manager.db_queries` como API publica.

---

### PR 2 - Executor sync definitivo (sin fetch_one)
**Objetivo**
- dejar `SyncQueryExecutor` como unico ejecutor sync.

**Cambios por archivo**
- [ ] `src/util_bbdd/executors/sync_query_executor.py` eliminar APIs legacy con `fetch_one`
- [ ] `src/util_bbdd/database_manager.py` eliminar `execute_query(...)` y `execute_custom_query(...)`
- [ ] `src/util_bbdd/database_manager.py` eliminar dependencia funcional de `DatabaseQueryExecutor`
- [ ] `src/util_bbdd/database_queries.py` remover `DatabaseQueryExecutor` (si no se movio antes)

**Tests**
- [ ] `tests/unit/test_sync_executor_contract.py`
- [ ] `tests/unit/test_execute_query_contract.py`
- [ ] `tests/unit/test_execute_custom_query_contract.py`

**Criterios de aceptacion**
- [ ] `pytest tests/unit/test_sync_executor_contract.py tests/unit/test_execute_query_contract.py tests/unit/test_execute_custom_query_contract.py -q`
- [ ] no quedan llamadas a `fetch_one` en rutas sync publicas.

**Incompatibilidades introducidas**
- `execute_query(..., fetch_one=...)` eliminado en sync.
- `execute_custom_query(..., fetch_one=...)` eliminado en sync.

---

### PR 3 - Executor async definitivo (paridad total con sync)
**Objetivo**
- alinear contrato async con sync y timeout por llamada.

**Cambios por archivo**
- [ ] `src/util_bbdd/executors/async_query_executor.py` timeout por llamada, eliminar estado `query_timeout`
- [ ] `src/util_bbdd/async_database_manager.py` eliminar wrappers legacy `execute_query`/`execute_custom_query`
- [ ] `src/util_bbdd/async_database_manager.py` migrar metodos metadata a `*_many/*_one` unicamente
- [ ] `src/util_bbdd/connection/async_protocols.py` validar contrato de cierre usado por async manager

**Tests**
- [ ] `tests/unit/test_async_executor_contract.py`
- [ ] `tests/unit/test_async_sync_parity_results.py`
- [ ] `tests/unit/test_timeout_behavior.py`

**Criterios de aceptacion**
- [ ] `pytest tests/unit/test_async_executor_contract.py tests/unit/test_async_sync_parity_results.py tests/unit/test_timeout_behavior.py -q`
- [ ] paridad de firma y semantica entre manager sync y async (except `await`).

**Incompatibilidades introducidas**
- `fetch_one` eliminado en API async publica.
- cambios de timeout async a modo por llamada.

---

### PR 4 - Validacion avanzada por motor centralizada
**Objetivo**
- dejar toda validacion por motor en `validators/` + metadata.

**Cambios por archivo**
- [ ] `src/util_bbdd/validators/mariadb_validator.py`
- [ ] `src/util_bbdd/validators/oracle_validator.py`
- [ ] `src/util_bbdd/validators/postgresql_validator.py`
- [ ] `src/util_bbdd/validators/sqlserver_validator.py`
- [ ] `src/util_bbdd/validators/hsqldb_validator.py`
- [ ] `src/util_bbdd/validators/sqlite_validator.py`
- [ ] `src/util_bbdd/validators/__init__.py`
- [ ] `src/util_bbdd/data/database_types.json` (solo si se requieren campos nuevos)
- [ ] `src/util_bbdd/database_queries.py` eliminar duplicados `_validate_*`

**Tests**
- [ ] `tests/unit/test_validations_by_motor.py`
- [ ] `tests/unit/validators/test_mariadb_validator.py`
- [ ] `tests/unit/validators/test_oracle_validator.py`
- [ ] `tests/unit/validators/test_postgresql_validator.py`
- [ ] `tests/unit/validators/test_sqlserver_validator.py`
- [ ] `tests/unit/validators/test_hsqldb_validator.py`
- [ ] `tests/unit/validators/test_sqlite_validator.py`

**Criterios de aceptacion**
- [ ] `pytest tests/unit/test_validations_by_motor.py tests/unit/validators -q`
- [ ] ninguna validacion por motor queda en managers ni ejecutores.

**Incompatibilidades introducidas**
- remocion de metodos privados de validacion en `DatabaseQueries`.

---

### PR 5 - Refactor SRP de `database_queries.py`
**Objetivo**
- convertir `database_queries.py` en modulo de conveniencia/documentacion o dividirlo en componentes SRP.

**Cambios por archivo**
- [ ] `src/util_bbdd/database_queries.py` reducir a capa SRP (sin ejecucion SQL)
- [ ] `src/util_bbdd/query_info_service.py` (nuevo, si aplica)
- [ ] `src/util_bbdd/motor_adapters/mariadb_adapter.py` (nuevo, para fallback HEX si aplica)
- [ ] `src/util_bbdd/motor_adapters/oracle_adapter.py` (nuevo, packaged routines)

**Tests**
- [ ] `tests/unit/test_database_queries_refactor_pr5.py`
- [ ] `tests/unit/test_queries_convenience.py` (nuevo si se mantienen helpers)
- [ ] `tests/unit/test_error_wrapping_raise_from.py`

**Criterios de aceptacion**
- [ ] `pytest tests/unit/test_database_queries_refactor_pr5.py tests/unit/test_error_wrapping_raise_from.py -q`
- [ ] `database_queries.py` no contiene clase ejecutora.

**Incompatibilidades introducidas**
- eliminacion de `DatabaseQueryExecutor` como API/import utilizable.

---

### PR 6 - No romper documentacion + README + CHANGELOG
**Objetivo**
- adaptar capa de documentacion al nuevo contrato y cerrar release notes.

**Cambios por archivo**
- [ ] `src/util_bbdd/doc/database_documentation.py` migrar llamadas:
  - `execute_query(..., fetch_one=...)` -> `execute_query_many/one`
  - `execute_custom_query(..., fetch_one=...)` -> `execute_custom_many/one`
  - `manager.db_queries` -> `manager.resolve_query(...)` o API publica equivalente
- [ ] `README.md` actualizar API publica real y ejemplos sync/async
- [ ] `CHANGELOG.md` registrar breaking changes sin compatibilidad
- [ ] `src/util_bbdd/__init__.py` revisar exportes finales de API publica

**Tests**
- [ ] `tests/unit/test_documentation_contract.py` (nuevo)
- [ ] `tests/unit/test_async_database_manager.py`
- [ ] `tests/unit/test_database_manager_normalized_methods.py`

**Criterios de aceptacion**
- [ ] `pytest tests/unit/test_documentation_contract.py tests/unit/test_async_database_manager.py tests/unit/test_database_manager_normalized_methods.py -q`
- [ ] `database_documentation.py` genera reportes sin uso de API legacy.

**Incompatibilidades introducidas**
- cambios de llamadas en consumidores de documentacion.
- cambios de imports si se elimina `DatabaseQueryExecutor`.

## 7. Tests requeridos (contrato, timeout, errores)

### 7.1 Contrato sync vs async
- Caso base:
  - mismo `query_name + db_type + params` produce misma `final_sql` y mismo shape de resultado (`Rows` o `RowOrNone`).
- Archivos:
  - `tests/unit/test_sync_async_contract.py`
  - `tests/unit/test_async_sync_parity_results.py`

### 7.2 Timeout
- Sync:
  - simular cursor lento y validar `QueryTimeoutError`.
- Async:
  - awaitable lento y validar timeout por llamada.
- Archivos:
  - `tests/unit/test_timeout_behavior.py`
  - `tests/unit/test_sync_executor_contract.py`
  - `tests/unit/test_async_executor_contract.py`

### 7.3 Errores y chaining
- Coberturas minimas:
  - query inexistente -> `QueryNotFoundError`
  - params invalidos -> `QueryValidationError`
  - db_type invalido -> `DatabaseTypeNotSupportedError`
  - traduccion de errores internos con `raise ... from err` y `__cause__` presente
- Archivos:
  - `tests/unit/test_error_wrapping_raise_from.py`
  - `tests/unit/test_query_registry.py`
  - `tests/unit/test_query_resolver_simplified.py`

### 7.4 Restricciones de test
- Default sin BD real, sin red.
- Usar `pytest`, `unittest.mock`, fakes de conexion/cursor.
- Integracion real queda fuera del criterio de aceptacion por defecto.

## 8. Consistencia de excepciones y logging (normas)

### 8.1 Normas
- Todas las capas (registry, resolver, executors, validators, managers):
  - levantan excepciones de dominio coherentes
  - loguean con mismo patron
  - traducen errores con `raise ... from err`

### 8.2 Tabla excepcion -> cuando -> capa

| Excepcion | Cuando se levanta | Capa responsable |
|---|---|---|
| `QueryNotFoundError` | `query_name` no existe para `db_type` | `QueryRegistry` |
| `QueryValidationError` | params no cumplen reglas de motor | `QueryResolver` + `validators/*` |
| `QueryParameterError` | interpolacion de template falla (param faltante/invalido) | `QueryResolver` |
| `QueryTimeoutError` | operacion excede timeout configurado por llamada | `SyncQueryExecutor` / `AsyncQueryExecutor` |
| `DatabaseTypeNotSupportedError` | motor desconocido/no soportado | `DatabaseTypeValidator` / factory de validator |
| `DatabaseOperationError` | error de ejecucion SQL no mapeable a error mas especifico | Executors / Managers |

### 8.3 Campos de logging minimos
- `query_name`
- `db_type`
- `elapsed_ms`
- `result_rows`
- `timeout` (si aplica)

## 9. Incompatibilidades (sin backward compat)

### 9.1 Imports/paths que cambian o se eliminan
- Eliminado uso/import de `DatabaseQueryExecutor` desde `src/util_bbdd/database_queries.py`.
- Eliminados aliases de excepciones deprecated (si se completa PR0).
- Consumidores no deben depender de `manager.db_queries` como API publica.

### 9.2 Firmas de metodos cambiadas
- Eliminar:
  - `execute_query(query_name, fetch_one=False, **params)`
  - `execute_custom_query(sql, fetch_one=False, params=None)`
- Sustituir por:
  - `execute_query_many(...)`, `execute_query_one(...)`
  - `execute_custom_many(...)`, `execute_custom_one(...)`

### 9.3 Estructura de JSON y metadata
- Si se agregan campos en `database_types.json` para validacion avanzada, debe declararse como cambio breaking de metadata interna.
- `sql_queries.json` mantiene estructura actual salvo normalizaciones explicitamente documentadas.

### 9.4 Cambios en documentacion consumidora
- `src/util_bbdd/doc/database_documentation.py` debe dejar de llamar:
  - `execute_query(..., fetch_one=...)`
  - `execute_custom_query(..., fetch_one=...)`
  - `db_manager.db_queries` directo

### 9.5 Nota de version
- `pyproject.toml` actual declara `>=3.10`; mover a `>=3.11` es cambio de compatibilidad de runtime y debe publicarse como breaking.

## 10. Checklist final de salida
- [ ] `pytest -q` pasa sin servicios externos (al menos suite unitaria)
- [ ] Sync y async usan el mismo `QueryRegistry`/`QueryResolver` y no duplican logica
- [ ] Validacion por motor esta centralizada en `validators/` y testeada
- [ ] `database_documentation.py` funciona sin API legacy
- [ ] `README.md` y `CHANGELOG.md` actualizados con decisiones y soporte real
- [ ] No queda duplicacion sustancial de codigo (SRP + DRY)
- [ ] No quedan wrappers publicos con `fetch_one`
- [ ] Toda traduccion de excepciones usa `raise ... from err`
