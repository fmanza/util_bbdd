## 1. Resumen Ejecutivo
Se revisó `src/util_bbdd/**` excluyendo `bulk_crud`, `doc` y `grafos`.
Hallazgo principal: hoy conviven dos arquitecturas en paralelo (legacy y nueva) para ejecución de queries, con duplicidad fuerte entre sync/async y responsabilidades mezcladas.

Decisiones clave:
- Consolidar una sola capa de ejecución con contrato único sync/async.
- Mantener `QueryRegistry` + `QueryResolver` como núcleo común.
- Dividir responsabilidades por dominio (queries, execution, connection/pool, engine policies, validation).
- Mantener enfoque **sin backward compatibility**.
- Conservar soporte por motor con matriz explícita de capacidades (incluyendo límite async de `hsqldb`).

Validación rápida ejecutada:
- `pytest -q tests/unit/test_sync_async_contract.py tests/unit/test_sync_executor_contract.py tests/unit/test_async_executor_contract.py` -> 27/27 OK.
- `pytest -q tests/test_database_query_executor_mariadb_fallback.py tests/unit/test_async_database_manager.py tests/test_async_factory_selection.py` -> 22/22 OK.

## 2. Inventario Actual (excluyendo bulk_crud/doc/grafos)
Paquetes revisados:
- `connection`
- `data`
- `executors`
- `factory`
- `validators`

Módulos raíz revisados:
- `__init__.py`
- `database_manager.py`
- `async_database_manager.py`
- `database_queries.py`
- `async_database_query_executor.py`
- `query_registry.py`
- `query_resolver.py`
- `database_type_validator.py`
- `driver_validator.py`
- `metadata_cache.py`
- `models.py`

Clases públicas relevantes (sync vs async):
- Sync manager: [DatabaseManager](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\database_manager.py:41)
- Async manager: [AsyncDatabaseManager](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\async_database_manager.py:22)
- Sync executor (legacy): [DatabaseQueryExecutor](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\database_queries.py:786)
- Sync executor (nuevo): [SyncQueryExecutor](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\executors\sync_query_executor.py:18)
- Async executor (legacy): [AsyncDatabaseQueryExecutor](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\async_database_query_executor.py:30)
- Async executor (nuevo): [AsyncQueryExecutor](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\executors\async_query_executor.py:19)
- Catálogo/resolución: [QueryRegistry](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\query_registry.py:24), [QueryResolver](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\query_resolver.py:26)

Entrypoints principales:
- `DatabaseManager` / `AsyncDatabaseManager`
- `ConnectFactory` / `PoolFactory`
- `QueryRegistry` / `QueryResolver`

Queries por motor (`sql_queries.json`):
- `mariadb: 18`
- `oracle: 17`
- `postgresql: 17`
- `hsqldb: 16`
- `sqlserver: 17`
- `sqlite: 18`

## 3. Duplicidades Detectadas (tabla)
| Duplicidad | Evidencia | Impacto | Dueño propuesto | Acción |
|---|---|---|---|---|
| Ejecutor sync duplicado | [database_queries.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\database_queries.py:786), [sync_query_executor.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\executors\sync_query_executor.py:18) | Dos contratos y dos caminos de errores/timeouts | `execution/sync` | Eliminar legacy y converger en uno |
| Ejecutor async duplicado | [async_database_query_executor.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\async_database_query_executor.py:30), [async_query_executor.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\executors\async_query_executor.py:19) | Divergencia de firma (`fetch_options` vs `fetch_one`) | `execution/async` | Unificar firma y borrar duplicado |
| Validación de queries duplicada | [query_resolver.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\query_resolver.py:57), [database_queries.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\database_queries.py:294) | Reglas potencialmente inconsistentes | `query/resolver` + `validation/query` | Centralizar validación en resolver+validadores |
| Wrappers de manager muy repetidos | [database_manager.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\database_manager.py:561) | Alto coste de mantenimiento y riesgo de drift | `manager/*` | Extraer patrón común por operación |
| Paridad manager rota | [database_manager.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\database_manager.py:561), [async_database_manager.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\async_database_manager.py:90) | Sync tiene gran API de conveniencia, async no | `manager` | Definir API paritaria y aplicar en ambos |
| Pipeline de conn params duplicado | [conn_params_builder.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\connection\conn_params_builder.py:7), [connection_params_manager.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\connection\connection_params_manager.py:56) | Validación/construcción redundante | `connection/params` | Un único pipeline tipado |
| Factorías SQLAlchemy ambiguas | [sqlalchemy_engine_factory.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\factory\sqlalchemy_engine_factory.py:13), [async_sqlalchemy_engine_factory.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\factory\async_sqlalchemy_engine_factory.py:381), [factory/__init__.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\factory\__init__.py:5) | API pública confusa (`SQLAlchemyEngineFactory` apunta a async alias) | `factory/engine` | Separar nombres y exports sin alias engañosos |
| Lógica específica de motor embebida en ejecutor genérico | [database_queries.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\database_queries.py:1039), [database_queries.py](c:\Desarrollo\python\libs\util_bbdd\src\util_bbdd\database_queries.py:1601) | SRP roto, alto acoplamiento | `engine/policies` | Mover fallbacks/reglas por motor a adapters |

## 4. Arquitectura Objetivo de Paquetes (target tree)
```text
src/util_bbdd/
  core/
    exceptions.py
    types.py
  query/
    registry.py
    resolver.py
    catalog.py
    metadata.py
  execution/
    sync/
      executor.py
    async/
      executor.py
  engine/
    mariadb.py
    oracle.py
    postgresql.py
    hsqldb.py
    sqlserver.py
    sqlite.py
  connection/
    params/
      manager.py
      models.py
    sync/
      ...
    async/
      ...
  pool/
    sync/
      ...
    async/
      ...
  manager/
    sync_manager.py
    async_manager.py
  factory/
    connection_factory.py
    pool_factory.py
    sqlalchemy_sync_factory.py
    sqlalchemy_async_factory.py
  validation/
    query/
      base.py
      mariadb.py
      oracle.py
      postgresql.py
      hsqldb.py
      sqlserver.py
      sqlite.py
```

## 5. Normalización DatabaseQueries vs DatabaseQueryExecutor (sync/async)
Contrato objetivo:

| Componente | Responsabilidad | Métodos objetivo |
|---|---|---|
| `DatabaseQueries` | Catálogo y resolución de definiciones SQL + metadata; sin acceso a conexión | `get_query_definition`, `render_query`, `list_queries`, `get_query_info` |
| `DatabaseQueryExecutor` (sync) | Ejecutar SQL resuelto y custom SQL; manejo de timeout/errores/fetch/transacción | `execute_query(query_name, db_type, params, fetch_one=False, timeout=None)`, `execute_custom_query(sql, params=None, fetch_one=False, timeout=None)`, `execute_batch(...)` |
| `DatabaseQueryExecutor` (async) | Mismo contrato semántico del sync, con `await` | Misma firma funcional (sin `fetch_options`) |

Reglas de paridad:
- Misma lista de capacidades sync/async.
- Mismo tipo de errores funcionales.
- Mismo comportamiento `fetch_one` / `fetch_all`.
- Mismo mapping por motor (con capability flags para excepciones reales como `hsqldb` async no soportado).

## 6. Decisiones de Refactor vs Clase Nueva
| Componente | Decisión | Justificación |
|---|---|---|
| `QueryRegistry` + `QueryResolver` | Refactor ligero | Ya están bien delimitados |
| `DatabaseQueries` | Refactor fuerte | Mezcla catálogo + metadata + validaciones legacy |
| `DatabaseQueryExecutor` legacy (en `database_queries.py`) | Clase nueva sustituta + retiro | Clase demasiado grande y acoplada |
| `AsyncDatabaseQueryExecutor` | Eliminar y migrar | Duplicado directo de `executors/async_query_executor.py` |
| `DatabaseManager` | Refactor por extracción de orquestación común | Mucho boilerplate repetido |
| `AsyncDatabaseManager` | Ampliación para paridad o reducción simétrica de sync | Hoy contrato no equivalente |
| `conn_params_builder` + `ConnectionParamsManager` | Unificar en una sola capa | Doble validación/construcción |
| SQLAlchemy factories | Reestructurar como clases separadas reales | Alias actual crea ambigüedad de API pública |

## 7. Matriz por Motor
| Motor | Estado actual (módulos/clases implicadas) | Duplicidades/Problemas | Decisión (refactor o nuevo) | Cambios clave propuestos | Tests de contrato (mock/fake, sin servicios externos) |
|---|---|---|---|---|---|
| `sqlserver` | sync/async connection+pool presentes; validador presente | Ejecutores duplicados; reglas dispersas de driver | Refactor | Unificar executor; mover políticas SQL Server a `engine/sqlserver.py` | `execute_query`, `fetch_one`, timeout, error mapping, factory selection |
| `mariadb` | cobertura amplia sync/async; fallback HEX en legacy executor | Lógica de fallback metida en ejecutor genérico | Refactor | Extraer fallback HEX a policy MariaDB reutilizable sync/async | fallback decode, parámetros obligatorios, rutas alternas `information_schema` |
| `oracle` | sync/async connection+pool; soporte de rutinas empaquetadas en legacy executor | Lógica Oracle embebida en clase genérica | Refactor | Mover packaged routine DDL/params a policy Oracle | routine ddl normal/packaged, errores `oracledb` async, fetch parity |
| `hsqldb` | solo sync connection; sin async connection/pool | No paridad async; manejo disperso de no soporte | Refactor + capability explícita | Capability flag `async_supported=False` con error estándar | tests de fail-fast en async manager/factory y contrato sync básico |
| `postgresql` | sync/async connection+pool completos | Duplicidad de ejecutores y validadores base repetidos | Refactor | Reusar contrato único y policy de placeholders/contexto | execute by name, custom query, pool lifecycle async |
| `sqlite` | sync/async connection+pool wrapper; validador | Duplicidad general de capas; posible drift de APIs | Refactor | Contrato único de ejecución y normalización params/path | `:memory:`/filepath, fetch parity, release/close semantics |

## 8. Plan por Fases
1. **Fase 0 (Baseline de contrato)**: crear tests de contrato únicos para executor y manager sync/async por motor (mock/fake), incluyendo capability flags; componentes `tests/unit/*contract*`; aceptación: tests verdes y sin servicios externos; breaking: ninguno funcional todavía.
2. **Fase 1 (Núcleo query único)**: consolidar `query_registry` y `query_resolver` como única vía de validación/resolución; componentes `src/util_bbdd/query/*` y `validators/*`; aceptación: no hay validación duplicada fuera de resolver; breaking: eliminación de APIs de validación legacy en `DatabaseQueries`.
3. **Fase 2 (Executor único por modo)**: implementar `execution/sync/executor.py` y `execution/async/executor.py` con firma equivalente; componentes legacy `database_queries.py` y `async_database_query_executor.py` pasan a deprecados internos y luego se retiran; aceptación: paridad de contrato sync/async en tests; breaking: firma unificada (sin `fetch_options`).
4. **Fase 3 (Policies por motor)**: mover lógica específica (MariaDB HEX, Oracle packaged routines, etc.) a `engine/*.py`; aceptación: tests por motor mantienen comportamiento; breaking: reubicación de código y símbolos internos.
5. **Fase 4 (Managers paritarios)**: reducir `DatabaseManager` a orquestador fino y alinear `AsyncDatabaseManager` con mismo set funcional o set mínimo común decidido; aceptación: tests de paridad manager; breaking: métodos legacy removidos o renombrados.
6. **Fase 5 (Factory/params cleanup)**: unificar pipeline de params y limpiar factorías SQLAlchemy/exports públicos; aceptación: imports públicos coherentes y tests de factoría por motor; breaking: paths/imports de factorías y helpers.
7. **Fase 6 (Limpieza final)**: borrar clases legacy duplicadas, ajustar `__init__.py` y documentación mínima de migración; aceptación: suite de contrato + smoke tests verdes; breaking: eliminación definitiva de APIs antiguas.

## 9. Breaking Changes + Guía de Migración
Breaking changes esperados:
- Se elimina `DatabaseQueryExecutor` dentro de `database_queries.py`.
- Se elimina `AsyncDatabaseQueryExecutor` como clase pública separada.
- Se unifica la firma async y sync de `execute_query` (sin `fetch_options`).
- Se retiran validaciones de query duplicadas fuera de `QueryResolver`.
- Se reubican símbolos de factorías para eliminar alias ambiguos.
- Se consolidan pipelines de `conn_params`.
- Se redefinen exports de `util_bbdd.__init__` a API pública mínima coherente.

Guía corta de migración:
1. Reemplazar imports legacy de ejecutores por el nuevo paquete `execution`.
2. Adaptar llamadas async de `execute_query(..., fetch_options=...)` a `fetch_one=...`.
3. Mover cualquier uso de validación manual de query al resolver central.
4. Actualizar imports de factorías SQLAlchemy a nombres explícitos `sync`/`async`.
5. Si usas `hsqldb` async, tratarlo como no soportado y usar ruta sync explícita.

## 10. Riesgos y Mitigaciones
| Riesgo | Mitigación |
|---|---|
| Pérdida de comportamiento específico por motor (MariaDB/Oracle) | Extraer policies por motor con tests dedicados por caso crítico |
| Drift entre contratos sync/async durante el refactor | Tests espejo de contrato ejecutados en ambas rutas |
| Rotura por cambios de imports públicos | Matriz de migración explícita y tests de import de API pública |
| Regresión en lifecycle de conexiones/pools | Tests de acquire/release/close por manager y por factoría |
| Confusión por coexistencia temporal de legacy y nuevo | Fases cortas con retirada temprana de duplicados y fail-fast en rutas obsoletas |

## 11. Checklist de Aceptación
- [x] Revisión ejecutada excluyendo `bulk_crud`, `doc`, `grafos`.
- [x] Duplicidades identificadas por nombre, comportamiento y responsabilidad.
- [x] Contrato objetivo `DatabaseQueries` vs `DatabaseQueryExecutor` definido.
- [x] Paridad sync/async definida de forma verificable.
- [x] Matriz por motor completada (`sqlserver`, `mariadb`, `oracle`, `hsqldb`, `postgresql`, `sqlite`).
- [x] Plan por fases con aceptación y breaking changes.
- [x] Guía de migración corta incluida.
- [x] Enfoque sin backward compatibility respetado.
- [x] Criterio “sin servicios externos” respetado en tests propuestos.
- [x] Smoke tests de contrato ejecutados y en verde (49/49 en los subconjuntos ejecutados).
