# Plan de Refactorización Estructural - util_bbdd v0.4.0

**Autor:** Análisis Automatizado
**Fecha:** 11 de marzo de 2026
**Versión Actual:** 0.4.0
**Estado:** Propuesta de Optimización

> Nota Fase 4 (2026-03-31): este plan describe una propuesta historica sobre la estructura de v0.4.0. Donde aparezcan `database_queries.py`, `database_type_validator.py` o rutas raiz antiguas, deben leerse como fotografia del momento; la referencia actual para managers publicos vive en `util_bbdd`, y la organizacion interna canonica ya distingue wrappers legacy de modulos activos.

> Terminologia historica: cuando este documento menciona `backward compatibility`, capas de aliasing o imports desde modulos raiz previos, describe la estrategia propuesta para ese corte. No sustituye la regla viva actual de imports canónicos desde `util_bbdd` ni la separacion actual entre fachadas legacy y modulos canonicos.

---

## 📋 Tabla de Contenidos

1. [Análisis Actual](#análisis-actual)
2. [Problemas Identificados](#problemas-identificados)
3. [Nueva Estructura Propuesta](#nueva-estructura-propuesta)
4. [Plan de Acción por Fases](#plan-de-acción-por-fases)
5. [Decisiones Arquitectónicas](#decisiones-arquitectónicas)
6. [Beneficios Esperados](#beneficios-esperados)
7. [Riesgos y Mitigación](#riesgos-y-mitigación)

---

## 📊 Análisis Actual

### Estructura Existente

```
util_bbdd/
├── async_database_manager.py         # Gestor async de BD
├── async_utils.py                    # Utilidades async
├── database_manager.py               # Gestor sync de BD (1400+ líneas)
├── database_queries.py               # Gestor de consultas registradas (hoy facade legacy/compat)
├── database_type_validator.py        # Validación de tipos (hoy wrapper de compatibilidad)
├── driver_validator.py               # Validación de drivers
├── database_exceptions.py            # Excepciones centralizadas
├── metadata_cache.py                 # Caché de metadatos
├── metadata_contracts.py             # Contratos de tipos
├── metadata_normalization.py         # Normalización de metadatos
├── models.py                         # Modelos de datos
├── query_registry.py                 # Registro de consultas
├── query_resolver.py                 # Resolución de consultas
├── result_normalizer.py              # Normalización de resultados
├── result_types.py                   # Tipos de resultado
├── bulk_crud/                        # Operaciones en lote
│   ├── audit_manager.py
│   ├── bulk_crud.py
│   ├── normalizacion_sql.py
│   └── __init__.py
├── connection/                       # Gestión de conexiones
│   ├── async_close_utils.py
│   ├── async_protocols.py
│   ├── connection_configs.py
│   ├── connection_params_manager.py
│   ├── connect_factory.py
│   ├── conn_params_builder.py
│   ├── pool_protocol.py
│   ├── sync_close_utils.py
│   ├── hsqldb/  ├── mariadb/
│   ├── oracle/
│   ├── postgresql/
│   ├── sqlite/
│   ├── sqlserver/
│   ├── doc/
│   └── __init__.py
├── core/                             # Capacidades del core
│   ├── capabilities.py
│   └── __init__.py
├── data/                             # Datos de configuración
│   ├── database_types.json
│   └── sql_queries.json
├── executors/                        # Ejecutores de consultas
│   ├── async_query_executor.py
│   ├── sync_query_executor.py
│   └── __init__.py
├── factory/                          # Factories
│   ├── async_sqlalchemy_engine_factory.py
│   ├── pool_factory.py
│   ├── sqlalchemy_engine_factory.py
│   └── __init__.py
├── grafos/                           # Análisis de relaciones
│   ├── graphviz_relationship_graph.py
│   ├── graphviz_relationship_graph_ext.py
│   ├── matplotlib_relationship_graph.py
│   ├── relationship_graph_base.py
│   ├── README_grafos.md
│   └── __init__.py
├── validators/                       # Validadores por motor
│   ├── base_validator.py
│   ├── hsqldb_validator.py
│   ├── mariadb_validator.py
│   ├── oracle_validator.py
│   ├── postgresql_validator.py
│   ├── sqlite_validator.py
│   ├── sqlserver_validator.py
│   └── __init__.py
└── __init__.py
```

### Estadísticas Actuales

| Métrica | Valor |
|---------|-------|
| **Módulos principales** | 16 archivos |
| **Submódulos especializados** | 5 directorios |
| **Líneas de código (database_manager.py)** | 1400+ |
| **Duplicación potencial** | Media-Alta |
| **Complejidad Ciclomática máxima** | ~22 (refactorizado a ~4) |
| **Pruebas** | 443/443 ✅ |

---

## 🔍 Problemas Identificados

### 1. **Falta de Separación de Responsabilidades**
- ❌ `database_manager.py` contiene 1400+ líneas
- ❌ Mezcla: gestión de conexiones, caché, operaciones de metadatos, normalización
- ❌ Difícil de testear y mantener

### 2. **Estructura Superficial de Módulos**
- ❌ Muchos módulos en nivel raíz sin agrupación temática
- ❌ Sin clara jerarquía de capas
- ❌ Dificultad para descubrir responsabilidades

### 3. **Gestión de Metadatos Dispersa**
- ❌ `metadata_cache.py`, `metadata_normalization.py`, `metadata_contracts.py` sin organización
- ❌ Lógica de compilación DDL en `database_manager.py`
- ❌ Sin módulo dedicado a operaciones de metadatos

### 4. **Factory y Pool Sin Claridad**
- ❌ `Connection factory` disperso en `connection/`
- ❌ Factories de engines en `factory/`
- ❌ Inconsistencia en nomenclatura y ubicación
- ❌ Sin patrón claro de creación

### 5. **Validadores Dispersos**
- ❌ `database_type_validator.py` en raíz
- ❌ Validadores específicos por motor en `validators/`
- ❌ Sin estructura jerárquica clara
- ❌ Duplicación de lógica

### 6. **Gestión de Errores**
- ❌ `database_exceptions.py` simple pero centralizado
- ❌ Sin clasificación por capas (conexión, query, metadatos, etc.)
- ❌ Sin enumeraciones de categorías de error

### 7. **Falta de Capas Lógicas**
- ❌ Sin separación clara entre: Acceso a Datos, Negocio, Presentación
- ❌ Sin capa de abstracción de queries
- ❌ Sin capa de transformación de resultados estructurada

---

## 🎯 Nueva Estructura Propuesta

### Estructura Jerárquica

```
util_bbdd/
├── _core/                                    # ← NUEVA: Core interno y abstracciones
│   ├── types.py                             # Tipos y aliases comunes
│   ├── exceptions.py                        # Excepciones reorganizadas
│   ├── contracts.py                         # Interfaces y protocols
│   ├── constants.py                         # Constantes y enums
│   └── __init__.py
│
├── _drivers/                                 # ← NUEVA: Gestión de drivers y validación
│   ├── validator.py                         # Validación centralizada
│   ├── capabilities.py                      # Capacidades por motor
│   ├── registry.py                          # Registro de drivers
│   └── __init__.py
│
├── connection/                               # ← OPTIMIZADO: Pool y factory centralizados
│   ├── pool.py                              # Gestión de pool (pool_factory.py → aquí)
│   ├── factory.py                           # Factoría de conexiones (connect_factory.py → aquí)
│   ├── config.py                            # Configuración (connection_configs.py → aquí)
│   ├── params.py                            # Parámetros (connection_params_manager.py → aquí)
│   ├── builder.py                           # Constructor (conn_params_builder.py → aquí)
│   ├── protocols.py                         # Protocols (async_protocols.py + pool_protocol.py)
│   ├── close.py                             # Cierre (async_close_utils.py + sync_close_utils.py)
│   ├── motors/                              # ← NUEVA: Drivers específicos por motor
│   │   ├── base.py                         # Base class para drivers
│   │   ├── mariadb.py
│   │   ├── postgresql.py
│   │   ├── oracle.py
│   │   ├── sqlserver.py
│   │   ├── sqlite.py
│   │   ├── hsqldb.py
│   │   └── __init__.py
│   └── __init__.py
│
├── query/                                    # ← NUEVA: Gestión de queries y registro
│   ├── registry.py                          # Registry de queries (query_registry.py → aquí)
│   ├── resolver.py                          # Resolver (query_resolver.py → aquí)
│   ├── database_queries.py                  # Gestor de queries registradas
│   ├── executor.py                          # ← NUEVA: Interfaz base de ejecutores
│   ├── executors/                           # ← REORGANIZADO: Ejecutores específicos
│   │   ├── sync.py                         # (sync_query_executor.py → aquí)
│   │   ├── async.py                        # (async_query_executor.py → aquí)
│   │   └── __init__.py
│   └── __init__.py
│
├── metadata/                                 # ← NUEVA: Gestión centralizada de metadatos
│   ├── cache.py                             # Cache (metadata_cache.py → aquí)
│   ├── contracts.py                         # Tipos (metadata_contracts.py → aquí)
│   ├── normalizer.py                        # Normalización (metadata_normalization.py → aquí)
│   ├── builder.py                           # ← NUEVA: Construcción de DDL
│   ├── fetcher.py                           # ← NUEVA: Obtención de metadatos
│   ├── manager.py                           # ← NUEVA: Gestión de operaciones de metadatos
│   └── __init__.py
│
├── results/                                  # ← NUEVA: Normalización de resultados
│   ├── normalizer.py                        # (result_normalizer.py → aquí)
│   ├── types.py                             # (result_types.py → aquí)
│   ├── converters.py                        # ← NUEVA: Conversores específicos por motor
│   └── __init__.py
│
├── bulk/                                     # ← RENOMBRADO: bulk_crud → bulk
│   ├── crud.py                              # (bulk_crud.py → aquí)
│   ├── audit.py                             # (audit_manager.py → aquí)
│   ├── normalization.py                     # (normalizacion_sql.py → aquí)
│   └── __init__.py
│
├── analysis/                                 # ← RENOMBRADO: grafos → analysis
│   ├── relationship_graph.py                # (relationship_graph_base.py → aquí)
│   ├── visualizers/                         # ← NUEVA: Visualizadores específicos
│   │   ├── graphviz.py                     # (graphviz_relationship_graph.py → aquí)
│   │   ├── graphviz_extended.py            # (graphviz_relationship_graph_ext.py → aquí)
│   │   ├── matplotlib.py                   # (matplotlib_relationship_graph.py → aquí)
│   │   └── __init__.py
│   └── __init__.py
│
├── data/                                     # ← OPTIMIZADO: datos de configuración
│   ├── database_types.json
│   ├── sql_queries.json
│   └── loader.py                            # ← NUEVA: Cargador de datos
│
├── managers/                                 # ← NUEVA: Managers de alto nivel
│   ├── database.py                          # (database_manager.py → aquí, refactorizado)
│   ├── async_database.py                    # (async_database_manager.py → aquí)
│   └── __init__.py
│
├── models.py                                 # Modelos de datos (sin cambios)
├── async_utils.py                           # Utilidades async (sin cambios)
├── __init__.py
└── py.typed
```

### Cambios Clave

| Cambio | Rationale |
|--------|-----------|
| `_core/` | Centraliza tipos, excepciones, contracts y constantes |
| `_drivers/` | Unifica validación y gestión de drivers |
| `connection/motors/` | Drivers específicos organizados jerárquicamente |
| `query/executors/` | Ejecutores bajo organización clara |
| `metadata/` | Gestión centralizada de metadatos (cache, normalizaciónen, builder, fetcher) |
| `results/` | Normalize resultados en módulo dedicado |
| `bulk/` | Renombrado de bulk_crud a bulk (más corto, más claro) |
| `analysis/` | Renombrado de grafos a analysis (más profesional) |
| `managers/` | Managers de alto nivel en módulo dedicado |

---

## 📋 Plan de Acción por Fases

### **FASE 1: Preparación y Validación (PR #1-2)**

#### PR #1: Crear estructura `_core/`

**Archivos a crear:**
- `src/util_bbdd/_core/types.py` - Tipos y aliases
- `src/util_bbdd/_core/exceptions.py` - Excepciones (migradas de database_exceptions.py)
- `src/util_bbdd/_core/contracts.py` - Protocols e interfaces
- `src/util_bbdd/_core/constants.py` - Constantes y enums
- `src/util_bbdd/_core/__init__.py` - Exports públicos

**Acciones:**
1. Extraer excepciones de `database_exceptions.py` con nuevas categorías:
   - `ConnectionError` (conexión/pool)
   - `QueryError` (ejecución de queries)
   - `MetadataError` (operaciones de metadatos)
   - `ValidationError` (validación)
   - `DriverError` (drivers)

2. Crear tipos comunes:
   ```python
   RowOrNone: TypeAlias = tuple[Any, ...] | None
   Rows: TypeAlias = list[tuple[Any, ...]]
   SchemaContext: TypeAlias = str  # database/schema
   DDLStatement: TypeAlias = str
   ```

3. Definir protocols para interfaces clave
4. Enums para constantes (DB_TYPE, OPERATION_TYPE, etc.)

**Tests:**
- Pruebas de importación
- Validación de tipos
- Cobertura de excepciones

---

#### PR #2: Crear estructura `_drivers/`

**Archivos a crear:**
- `src/util_bbdd/_drivers/validator.py` - Validación centralizada
- `src/util_bbdd/_drivers/capabilities.py` - Capacidades por motor
- `src/util_bbdd/_drivers/registry.py` - Registro de drivers
- `src/util_bbdd/_drivers/__init__.py`

**Acciones:**
1. Migrar `database_type_validator.py` → `_drivers/validator.py`
2. Migrar validadores específicos de `validators/` → lógica en `_drivers/`
3. Consolidar `core/capabilities.py` → `_drivers/capabilities.py`
4. Crear registry centralizado

**Tests:**
- Validación de drivers
- Capacidades por motor
- Registry coherencia

---

### **FASE 2: Reorganización de Conexiones (PR #3-5)**

#### PR #3: Refactorizar `connection/`

**Acciones:**
1. Consolidar factories:
   - `connect_factory.py` → `connection/factory.py`
   - `pool_factory.py` → `connection/pool.py`

2. Consolidar configuración:
   - `connection_configs.py` → `connection/config.py`
   - `connection_params_manager.py` → `connection/params.py`
   - `conn_params_builder.py` → `connection/builder.py`

3. Consolidar protocols y close:
   - `async_protocols.py` + `pool_protocol.py` → `connection/protocols.py`
   - `async_close_utils.py` + `sync_close_utils.py` → `connection/close.py`

**Tests:**
- Importaciones siguen funcionando
- Backward compatibility con cambios

---

#### PR #4: Crear `connection/motors/`

**Archivos a crear:**
- `src/util_bbdd/connection/motors/base.py` - Driver base
- `src/util_bbdd/connection/motors/mariadb.py`
- `src/util_bbdd/connection/motors/postgresql.py`
- `src/util_bbdd/connection/motors/oracle.py`
- `src/util_bbdd/connection/motors/sqlserver.py`
- `src/util_bbdd/connection/motors/sqlite.py`
- `src/util_bbdd/connection/motors/hsqldb.py`
- `src/util_bbdd/connection/motors/__init__.py`

**Acciones:**
1. Migrar lógica específica de cada motor desde `connection/{motor}/`
2. Crear clase base `DriverConnectionBase`
3. Cada driver implementa interfaz base
4. Eliminar directorios antiguos `connection/{motor}/`

**Tests:**
- Conexión por motor
- Protocolos específicos
- Backward compatibility

---

#### PR #5: Crear `data/loader.py`

**Acciones:**
1. Crear `data/loader.py` para cargar JSON dinámicamente
2. Caché de datos cargados
3. Validación de esquema JSON

**Tests:**
- Carga de datos
- Validación
- Caché coherencia

---

### **FASE 3: Reorganización de Queries (PR #6-8)**

#### PR #6: Crear `query/` - Parte 1: Registry y Resolver

**Acciones:**
1. Migrar `query_registry.py` → `query/registry.py`
2. Migrar `query_resolver.py` → `query/resolver.py`
3. Crear `query/executor.py` - Interfaz base

**Tests:**
- Registry funcionalidad
- Resolver resuelve correctamente
- Interfaz ejecutor

---

#### PR #7: Crear `query/executors/`

**Acciones:**
1. Refactorizar `executors/sync_query_executor.py` → `query/executors/sync.py`
2. Refactorizar `executors/async_query_executor.py` → `query/executors/async.py`
3. Eliminar directorio `executors/`

**Tests:**
- Ejecución sync/async
- Parámetros
- Timeout
- Error handling

---

#### PR #8: Migrar gestión de queries

**Acciones:**
1. `database_queries.py` → `query/database_queries.py` (o renombrar a `query/manager.py`)
2. Exportar desde `query/__init__.py`

**Tests:**
- Queries registradas accesibles
- Backward compatibility

---

### **FASE 4: Reorganización de Metadatos (PR #9-11)**

#### PR #9: Crear `metadata/` - Parte 1: Base

**Acciones:**
1. `metadata_cache.py` → `metadata/cache.py`
2. `metadata_contracts.py` → `metadata/contracts.py`
3. `metadata_normalization.py` → `metadata/normalizer.py`
4. Crear `metadata/__init__.py` con exports

**Tests:**
- Cache funcionalidad
- Normalización
- Tipos

---

#### PR #10: Crear `metadata/builder.py` y `metadata/fetcher.py`

**Acciones:**
1. Extraer lógica DDL de `database_manager.py`:
   - `_build_mariadb_ddl_from_metadata()` → `metadata/builder.py`
   - `_is_valid_column_row()` → `metadata/builder.py`
   - Métodos helper → `metadata/builder.py`

2. Extraer lógica de obtención:
   - `get_columns()` → `metadata/fetcher.py`
   - `get_tables()` → `metadata/fetcher.py`
   - `get_primary_keys()` → `metadata/fetcher.py`
   - `get_indices()` → `metadata/fetcher.py`
   - `get_foreign_keys()` → `metadata/fetcher.py`
   - `get_unique_constraints()` → `metadata/fetcher.py`

**Tests:**
- Builder genera DDL correcto
- Fetcher obtiene metadatos
- Caché funciona

---

#### PR #11: Crear `metadata/manager.py`

**Acciones:**
1. Crear gestor de operaciones de metadatos:
   - `get_tables()`, `get_views()`, `get_routines()`
   - `get_ddl()`, `get_view_ddl()`, `get_routine_ddl()`
   - `get_columns()`, `get_primary_keys()`, etc.

2. Orquestar: Builder + Fetcher + Cache + Normalizer

**Tests:**
- Todas las operaciones de metadatos
- Caché coherencia
- Fallbacks MariaDB

---

### **FASE 5: Reorganización de Resultados y Bulk (PR #12-13)**

#### PR #12: Crear `results/`

**Acciones:**
1. `result_normalizer.py` → `results/normalizer.py`
2. `result_types.py` → `results/types.py`
3. Crear `results/converters.py` - Conversores específicos por motor
4. Extraer lógica de normalización DDL a `results/ddl_normalizer.py`

**Tests:**
- Normalización de resultados
- Conversión por motor
- Tipos

---

#### PR #13: Reorganizar `bulk/`

**Acciones:**
1. Renombrar `bulk_crud/` → `bulk/`
2. `bulk_crud.py` → `bulk/crud.py`
3. `audit_manager.py` → `bulk/audit.py`
4. `normalizacion_sql.py` → `bulk/normalization.py`

**Tests:**
- CRUD en lote funciona
- Auditoría funciona
- SQL normalization ok

---

### **FASE 6: Reorganización de Análisis (PR #14)**

#### PR #14: Reorganizar `analysis/`

**Acciones:**
1. Renombrar `grafos/` → `analysis/`
2. `relationship_graph_base.py` → `analysis/relationship_graph.py`
3. Crear `analysis/visualizers/`:
   - `graphviz_relationship_graph.py` → `analysis/visualizers/graphviz.py`
   - `graphviz_relationship_graph_ext.py` → `analysis/visualizers/graphviz_extended.py`
   - `matplotlib_relationship_graph.py` → `analysis/visualizers/matplotlib.py`

**Tests:**
- Análisis de relaciones
- Visualizadores funcionan

---

### **FASE 7: Crear Managers de Alto Nivel (PR #15-16)**

#### PR #15: Crear `managers/database.py`

**Acciones:**
1. Refactorizar `database_manager.py`:
   - Mover a `managers/database.py`
   - Dividir en responsabilidades claras:
     - Inicialización y conexión
     - Delegación a `metadata.manager`
     - Delegación a `bulk.crud`
     - Delegación a `query.executors`

2. Reducir líneas de código de ~1400 a ~500

**Cambios principales:**
```python
class DatabaseManager:
    def __init__(self, db_type, conn_params, ...):
        self._connection_manager = ConnectionManager(...)
        self._metadata_manager = MetadataManager(...)
        self._query_executor = QueryExecutor(...)
        self._bulk_operator = BulkOperator(...)

    # Delegación
    def get_tables(self) -> list:
        return self._metadata_manager.get_tables()

    def get_columns(self, table: str) -> list:
        return self._metadata_manager.get_columns(table)

    def execute_query(self, name: str, params: dict):
        return self._query_executor.execute_query(name, params)

    def bulk_insert(self, table: str, records: list):
        return self._bulk_operator.insert(table, records)
```

**Tests:**
- Delegación funciona
- Backward compatibility

---

#### PR #16: Crear `managers/async_database.py`

**Acciones:**
1. `async_database_manager.py` → `managers/async_database.py`
2. Aplicar mismo patrón de delegación

**Tests:**
- Async funcionalidad
- Paridad async/sync

---

### **FASE 8: Cleanup y Documentación (PR #17-18)**

#### PR #17: Eliminar directorios antiguos

**Acciones:**
1. Eliminar `executors/` (migrado a `query/executors/`)
2. Eliminar `connection/{motor}/` (migrado a `connection/motors/`)
3. Eliminar `validators/` (integrado en `_drivers/`)
4. Eliminar `core/` (integrado en varios lados)
5. Eliminar `bulk_crud/` (renombrado a `bulk/`)
6. Eliminar `grafos/` (renombrado a `analysis/`)
7. Limpiar archivos obsoletos en raíz

**Acciones:**
- Actualizar todos los imports
- Validar que testes pasan
- Backward compatibility layer si es necesario

**Tests:**
- Todos los tests siguen pasando (443/443)
- Import resolution correcto

---

#### PR #18: Actualizar Documentación

**Acciones:**
1. Actualizar README.md con nueva estructura
2. Crear `ARCHITECTURE.md` - Guía de arquitectura
3. Crear `MODULES.md` - Descripción de cada módulo
4. Actualizar docstrings
5. Crear migration guide para users

**Documentación:**
- Estructura es autoexplicativa
- Diagrama de dependencias
- Ejemplos de uso

---

### **FASE 9: Integración de Tests (PR #19)**

#### PR #19: Full Test Suite - Validar todas las fases

**Acciones:**
1. Ejecutar suite completa: `pytest tests/ -v`
2. Validar cobertura: `pytest tests/ --cov`
3. Verificar tipos: `mypy src/`
4. Linting: `ruff check src/`
5. Formato: `black src/`

**Requisitos:**
- ✅ 443/443 tests passing
- ✅ Coverage > 80%
- ✅ Zero mypy errors
- ✅ Zero ruff errors
- ✅ Black formatted

---

## 🎯 Decisiones Arquitectónicas

### 1. **Prefijo `_` para módulos internos**
- `_core/`, `_drivers/` son internos
- No formaban parte del API público
- Facilita identificación de interno vs públi

co

### 2. **Organización por capas lógicas**
```
_core/          → Abstracciones y tipos
_drivers/       → Gestión de motores
connection/     → Conexión y pool
query/          → Queries y ejecución
metadata/       → Metadatos
results/        → Resultados
bulk/           → Operaciones masivas
analysis/       → Análisis y visualización
managers/       → API de alto nivel
```

### 3. **Segregación de responsabilidades**
- `metadata/builder.py` - Construcción de DDL
- `metadata/fetcher.py` - Obtención de metadatos
- `metadata/cache.py` - Caché
- `metadata/normalizer.py` - Normalización
- `metadata/manager.py` - Orquestación

### 4. **Consistencia en nomenclatura**
- Files: `snake_case`
- Classes: `PascalCase`
- Modules con responsabilidad única

### 5. **Backward Compatibility**
- Exports públicos se mantienen en `__init__.py`
- APIs no cambian, solo ubicación
- Migration path claro para users

---

## ✨ Beneficios Esperados

### Calidad de Código
| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| Líneas máx / archivo | 1400+ | <500 | ✅ 71% ↓ |
| CC máximo | 22 | ~5-8 | ✅ 76% ↓ |
| Cohesión | Media | Alta | ✅ +40% |
| Acoplamiento | Alto | Bajo | ✅ -40% |
| Testabilidad | Media | Alta | ✅ +50% |

### Mantenibilidad
- ✅ Fácil ubicar responsabilidades
- ✅ Menor curva de aprendizaje
- ✅ Refactoring más seguro
- ✅ Mejor documentación

### Escalabilidad
- ✅ Agregar nuevos motores más fácil
- ✅ Nuevas features no impactan base
- ✅ Plugin architecture posible

### Performance
- ✅ Carga lazy de módulos
- ✅ Mejor caché coherencia
- ✅ Menos imports circulares

---

## ⚠️ Riesgos y Mitigación

### Riesgo 1: Ruptura de Backward Compatibility
**Impacto:** Alto - Users que dependen de imports actuales
**Mitigación:**
- Mantener exports públicos en `__init__.py`
- Crear aliasing de imports antiguos
- Deprecation warnings durante 2 releases
- Migration guide en docs

### Riesgo 2: Importes Circulares
**Impacto:** Medio - Problemas de inicialización
**Mitigación:**
- Diseño cuidadoso de dependencias (DAG)
- Usar imports locales si es necesario
- Type checking con `TYPE_CHECKING`
- Tests de importación

### Riesgo 3: Fallos en Tests
**Impacto:** Medio - Suite de 443 tests puede fallar
**Mitigación:**
- PR incremental (una fase por PR)
- Tests antes de cada change
- Full suite en cada PR
- No mergear con fallos

### Riesgo 4: Performance
**Impacto:** Bajo - Más módulos pueden impactar import time
**Mitigación:**
- Perfilar imports
- Lazy load de drivers
- Caché de módulos compilados
- Benchmarking continuo

### Riesgo 5: Complejidad de Migración
**Impacto:** Medio - Requiere refactoring masivo
**Mitigación:**
- Plan por fases (19 PRs)
- Cada fase es independiente
- Automated migration tool si es necesario
- Rollback plan para cada PR

---

## 📊 Timeline Estimado

| Fase | PRs | Estimado | Esfuerzo |
|------|-----|----------|----------|
| **Prep** | #1-2 | 1 semana | 10-15 hrs |
| **Conexión** | #3-5 | 1.5 semanas | 15-20 hrs |
| **Queries** | #6-8 | 1 semana | 10-15 hrs |
| **Metadatos** | #9-11 | 1.5 semanas | 20-25 hrs |
| **Resultados** | #12-13 | 1 semana | 10-12 hrs |
| **Análisis** | #14 | 3-4 días | 5-8 hrs |
| **Managers** | #15-16 | 1.5 semanas | 20-25 hrs |
| **Cleanup** | #17-18 | 1 semana | 10-12 hrs |
| **Tests** | #19 | 3-4 días | 5-8 hrs |
| **TOTAL** | 19 PRs | **10-11 semanas** | **105-140 hrs** |

---

## ✅ Criterios de Éxito

- ✅ 443/443 tests passing (100%)
- ✅ Coverage > 80% (actual: ~85%)
- ✅ CC máximo ≤ 15 en todos los métodos
- ✅ Zero imports circulares
- ✅ Zero deprecation warnings
- ✅ Backward compatible (2 releases)
- ✅ Documentación actualizada
- ✅ Migration guide disponible
- ✅ Performance no degraded (<5% increase en import time)
- ✅ Todos los PRs aprobados y mergeados

---

## 📝 Próximos Pasos

1. **Revisión de propuesta** - Feedback del equipo
2. **Refinamiento** - Ajustes necesarios
3. **Kick-off PR #1** - Crear `_core/`
4. **Iteración semanal** - 2-3 PRs por semana
5. **Release v0.5.0** - Con nueva estructura
6. **Deprecación gradual** - Support v0.4.x durante 2 releases

---

## 📎 Apéndices

### A. Migración de Imports - Ejemplo

**Antes:**
```python
from util_bbdd.database_manager import DatabaseManager
from util_bbdd.executors import SyncQueryExecutor
from util_bbdd.metadata_cache import DatabaseMetadataCache
from util_bbdd.validators import MariaDBValidator
```

**Después (mismo, con alias en `__init__.py`):**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.query.executors import SyncQueryExecutor
from util_bbdd.metadata import DatabaseMetadataCache
from util_bbdd._drivers import MariaDBValidator

# O usando imports legacy (con deprecation warning):
from util_bbdd.database_manager import DatabaseManager  # Ruta legacy historica de compatibilidad
```

### B. Estructura de `_core/exceptions.py`

```python
# Base
class DatabaseException(Exception): pass

# Categories
class ConnectionError(DatabaseException): pass
class QueryError(DatabaseException): pass
class MetadataError(DatabaseException): pass
class ValidationError(DatabaseException): pass
class DriverError(DatabaseException): pass

# Specific
class PoolConnectionError(ConnectionError): pass
class QueryTimeoutError(QueryError): pass
class MetadataFetchError(MetadataError): pass
class InvalidDatabaseType(ValidationError): pass
class DriverNotFoundError(DriverError): pass
```

### C. PR Template Ejemplo

```markdown
# [PHASE X] Description

## Changes
- File A: Changes
- File B: Changes

## Tests
- [ ] 443/443 tests passing
- [ ] New tests for changes
- [ ] Coverage > 80%

## Breaking Changes
- None

## Migration
- No manual changes needed

## Checklist
- [ ] Code reviewed
- [ ] Tests passing
- [ ] Docs updated
- [ ] No regressions
```

---

**Documento terminado.** Listo para iniciar implementación de fases.
