# Plan de Acción - PRs de Refactorización (v0.4.0 → v0.5.0)

**Documento:** Plan detallado para ejecución de 19 PRs
**Inicio:** Pendiente aprobación
**Fin:** ~11 semanas
**Status:** 📋 En Propuesta

> Nota Fase 4 (2026-03-31): este documento conserva el plan historico de migracion por PRs. Las menciones a modulos raiz como `database_type_validator.py` o a layouts previos deben interpretarse como origen de la migracion; hoy la referencia vigente distingue entre rutas internas canonicas y facades de compatibilidad.

> Lectura actual: las secciones de `Backward Compatibility` pertenecen al plan histórico y no deben interpretarse como guía viva de imports. Para documentación actual, la referencia principal es la superficie canónica documentada en README y `docs/MIGRATION_GUIDE.md`.

---

## Estructura de PRs por Fase

### FASE 1: Preparación y Validación

#### PR #1: Crear estructura `_core/` - Tipos, Excepciones y Contracts

**Objetivo:** Centralizar abstracciones y tipos comunes

**Archivos a crear:**
```
src/util_bbdd/_core/
├── types.py          # ~150 líneas
├── exceptions.py     # ~200 líneas - Migrar de database_exceptions.py
├── contracts.py      # ~100 líneas - Protocols e interfaces
├── constants.py      # ~80 líneas - Enums y constantes
└── __init__.py       # ~30 líneas - Exports
```

**Checklist:**
- [ ] Crear `_core/types.py` con type aliases
- [ ] Crear `_core/exceptions.py` con jerarquía de excepciones
- [ ] Crear `_core/contracts.py` con Protocols
- [ ] Crear `_core/constants.py` con Enums
- [ ] Crear `_core/__init__.py` exportando públicamente
- [ ] Actualizar imports en `database_exceptions.py` (deprecate)
- [ ] ✅ 443/443 tests passing
- [ ] Coverage > 80%
- [ ] mypy sin errores
- [ ] Documentar en docstrings

**Archivos a modificar:**
- `src/util_bbdd/__init__.py` - Agregar imports de _core

**Backward Compatibility:**
- Mantener `database_exceptions.py` importando de `_core/exceptions.py`
- Deprecation warning en `database_exceptions.py`

---

#### PR #2: Crear estructura `_drivers/` - Drivers y Validación Centralizada

**Objetivo:** Unificar gestión de drivers y validación

**Archivos a crear:**
```
src/util_bbdd/_drivers/
├── validator.py      # ~300 líneas - Migrar de database_type_validator.py
├── capabilities.py   # ~200 líneas - Capacidades por motor
├── registry.py       # ~150 líneas - Registry centralizado
└── __init__.py       # ~40 líneas - Exports
```

**Checklist:**
- [ ] Migrar `database_type_validator.py` → `_drivers/validator.py`
- [ ] Crear `_drivers/capabilities.py` consolidando `core/capabilities.py`
- [ ] Crear `_drivers/registry.py` con registro centralizado
- [ ] Crear `_drivers/__init__.py`
- [ ] Lógica de validadores específicos en validator.py
- [ ] ✅ 443/443 tests passing
- [ ] Coverage > 80%
- [ ] mypy sin errores
- [ ] Eliminar `core/` directorio (vacío after this PR)

**Archivos a eliminar/modificar:**
- `core/` → Vacío después, se elimina en PR #17
- `database_type_validator.py` → Deprecate en PR #17

**Backward Compatibility:**
- Mantener `database_type_validator.py` importando de `_drivers/validator.py`
- Tratar `database_type_validator.py` como facade legacy soportada, no como ruta canonica para documentacion nueva

---

### FASE 2: Reorganización de Conexiones

#### PR #3: Refactorizar y consolidar `connection/`

**Objetivo:** Eliminar archivos dispersos, consolidar en factory/pool/config/params

**Archivos a crear:**
```
src/util_bbdd/connection/
├── factory.py        # ~400 líneas - migrate connect_factory.py
├── pool.py           # ~350 líneas - migrate pool_factory.py
├── config.py         # ~150 líneas - migrate connection_configs.py
├── params.py         # ~200 líneas - migrate connection_params_manager.py
├── builder.py        # ~100 líneas - migrate conn_params_builder.py
├── protocols.py      # ~150 líneas - merge async_protocols.py + pool_protocol.py
├── close.py          # ~200 líneas - merge async_close_utils.py + sync_close_utils.py
└── __init__.py       # ~50 líneas - Exports
```

**Acciones:**
1. Crear factory.py consolidando connect_factory.py
2. Crear pool.py consolidando pool_factory.py
3. Crear config.py consolidando connection_configs.py
4. Crear params.py consolidando connection_params_manager.py
5. Crear builder.py consolidando conn_params_builder.py
6. Crear protocols.py consolidando async_protocols.py + pool_protocol.py
7. Crear close.py consolidando async_close_utils.py + sync_close_utils.py
8. Actualizar imports en `__init__.py`

**Checklist:**
- [ ] Migrar `connect_factory.py` → `connection/factory.py`
- [ ] Migrar `pool_factory.py` → `connection/pool.py`
- [ ] Migrar `connection_configs.py` → `connection/config.py`
- [ ] Migrar `connection_params_manager.py` → `connection/params.py`
- [ ] Migrar `conn_params_builder.py` → `connection/builder.py`
- [ ] Migrar `async_protocols.py` + `pool_protocol.py` → `connection/protocols.py`
- [ ] Migrar `async_close_utils.py` + `sync_close_utils.py` → `connection/close.py`
- [ ] Actualizar `connection/__init__.py`
- [ ] ✅ 443/443 tests passing
- [ ] Backward compatibility - imports siguen funcionando
- [ ] Documentar imports en __init__.py
- [ ] Deprecate old files

**Archivos a eliminar (después de migración):**
- `connect_factory.py` (no es public API)
- `pool_factory.py`
- `connection_configs.py`
- `connection_params_manager.py`
- `conn_params_builder.py`
- `async_protocols.py`
- `pool_protocol.py`
- `async_close_utils.py`
- `sync_close_utils.py`

---

#### PR #4: Crear `connection/motors/` - Drivers específicos por motor

**Objetivo:** Organizar lógica específica de cada motor jerarquicamente

**Archivos a crear:**
```
src/util_bbdd/connection/motors/
├── base.py           # ~150 líneas - Base class
├── mariadb.py        # ~150 líneas - MariaDB específico
├── postgresql.py     # ~100 líneas - PostgreSQL específico
├── oracle.py         # ~100 líneas - Oracle específico
├── sqlserver.py      # ~100 líneas - SQL Server específico
├── sqlite.py         # ~80 líneas - SQLite específico
├── hsqldb.py         # ~80 líneas - HSQLDB específico
└── __init__.py       # ~30 líneas - Exports
```

**Acciones:**
1. Crear `motors/base.py` con clase base `DriverConnectionBase`
2. Migrar lógica de `connection/mariadb/` → `motors/mariadb.py`
3. Migrar lógica de `connection/postgresql/` → `motors/postgresql.py`
4. Migrar lógica de `connection/oracle/` → `motors/oracle.py`
5. Migrar lógica de `connection/sqlserver/` → `motors/sqlserver.py`
6. Migrar lógica de `connection/sqlite/` → `motors/sqlite.py`
7. Migrar lógica de `connection/hsqldb/` → `motors/hsqldb.py`
8. Cada driver implementa interfaz base

**Checklist:**
- [ ] Crear `motors/base.py` con DriverConnectionBase
- [ ] Migrar `connection/mariadb/` → content en `motors/mariadb.py`
- [ ] Migrar `connection/postgresql/` → content en `motors/postgresql.py`
- [ ] Migrar `connection/oracle/` → content en `motors/oracle.py`
- [ ] Migrar `connection/sqlserver/` → content en `motors/sqlserver.py`
- [ ] Migrar `connection/sqlite/` → content en `motors/sqlite.py`
- [ ] Migrar `connection/hsqldb/` → content en `motors/hsqldb.py`
- [ ] Cada driver implementa `DriverConnectionBase`
- [ ] `motors/__init__.py` con exports
- [ ] ✅ 443/443 tests passing
- [ ] Eliminar directorios `connection/{motor}/...`

**Archivos a eliminar:**
- `connection/mariadb/` (directorio completo)
- `connection/postgresql/` (directorio completo)
- `connection/oracle/` (directorio completo)
- `connection/sqlserver/` (directorio completo)
- `connection/sqlite/` (directorio completo)
- `connection/hsqldb/` (directorio completo)

---

#### PR #5: Crear `data/loader.py` - Cargador dinámico de datos

**Objetivo:** Abstraer carga de JSON y caché

**Archivos a crear:**
```
src/util_bbdd/data/
├── loader.py         # ~150 líneas
└── __init__.py       # Actualizado
```

**Acciones:**
1. Crear `data/loader.py` con clase `DataLoader`
2. Métodos: `load_database_types()`, `load_sql_queries()`
3. Caché en memoria
4. Validación de esquema JSON

**Checklist:**
- [ ] Crear `data/loader.py` con DataLoader
- [ ] Métodos de carga
- [ ] Caché coherencia
- [ ] ✅ 443/443 tests passing
- [ ] Documentar uso

---

### FASE 3: Reorganización de Queries

#### PR #6: Crear `query/` - Part 1: Registry, Resolver, y Executor Base

**Objetivo:** Centralizar gestión de queries

**Archivos a crear:**
```
src/util_bbdd/query/
├── registry.py       # ~150 líneas - migrate query_registry.py
├── resolver.py       # ~150 líneas - migrate query_resolver.py
├── executor.py       # ~100 líneas - NEW: Base executor interface
├── database_queries.py  # MOVED from root
└── __init__.py       # Exports
```

**Acciones:**
1. Migrar `query_registry.py` → `query/registry.py`
2. Migrar `query_resolver.py` → `query/resolver.py`
3. Crear `query/executor.py` con interfaz base `QueryExecutor`
4. Mover `database_queries.py` a `query/` o renombrar a `query/manager.py`
5. Actualizar imports

**Checklist:**
- [ ] `query/registry.py` de `query_registry.py`
- [ ] `query/resolver.py` de `query_resolver.py`
- [ ] Crear `query/executor.py` - Base interface
- [ ] Mover `database_queries.py` a `query/database_queries.py`
- [ ] `query/__init__.py` con exports
- [ ] ✅ 443/443 tests passing
- [ ] Backward compatibility

---

#### PR #7: Crear `query/executors/` - Ejecutores específicos

**Objetivo:** Reorganizar ejecutores sync/async

**Archivos a crear:**
```
src/util_bbdd/query/executors/
├── sync.py           # migrate sync_query_executor.py
├── async.py          # migrate async_query_executor.py
└── __init__.py       # Exports
```

**Acciones:**
1. Migrar `executors/sync_query_executor.py` → `query/executors/sync.py`
2. Migrar `executors/async_query_executor.py` → `query/executors/async.py`
3. Renombrar clases: `SyncQueryExecutor` → mismo nombre
4. Actualizar imports
5. Eliminar `executors/` directorio

**Checklist:**
- [ ] Migrar sync executor
- [ ] Migrar async executor
- [ ] `query/executors/__init__.py`
- [ ] Actualizar imports en `managers/`
- [ ] ✅ 443/443 tests passing
- [ ] Eliminar directorio `executors/`

---

### FASE 4: Reorganización de Metadatos

#### PR #8: Crear `metadata/` - Part 1: Cache, Contracts, Normalizer

**Objetivo:** Centralizar operaciones de metadatos

**Archivos a crear:**
```
src/util_bbdd/metadata/
├── cache.py          # migrate metadata_cache.py
├── contracts.py      # migrate metadata_contracts.py
├── normalizer.py     # migrate metadata_normalization.py
└── __init__.py       # Exports
```

**Acciones:**
1. Migrar `metadata_cache.py` → `metadata/cache.py`
2. Migrar `metadata_contracts.py` → `metadata/contracts.py`
3. Migrar `metadata_normalization.py` → `metadata/normalizer.py`
4. Actualizar imports
5. Crear `metadata/__init__.py`

**Checklist:**
- [ ] `metadata/cache.py`
- [ ] `metadata/contracts.py`
- [ ] `metadata/normalizer.py`
- [ ] `metadata/__init__.py`
- [ ] ✅ 443/443 tests passing
- [ ] Backward compatibility imports

---

#### PR #9: Crear `metadata/builder.py` y `metadata/fetcher.py`

**Objetivo:** Extraer lógica de construcción y obtención de metadatos

**Archivos a crear:**
```
src/util_bbdd/metadata/
├── builder.py        # NEW: ~300 líneas
├── fetcher.py        # NEW: ~500 líneas (extracted from database_manager.py)
└── manager.py        # NEW: ~400 líneas (orchestration)
```

**Acciones:**
1. Extraer de `database_manager.py`:
   - `_build_mariadb_ddl_from_metadata()` y helpers → `metadata/builder.py`
   - Lógica de construcción de DDL MariaDB

2. Extraer de `database_manager.py`:
   - `get_columns()` → `metadata/fetcher.py`
   - `get_tables()`, `get_views()`, `get_routines()`
   - `get_primary_keys()`, `get_indices()`, `get_foreign_keys()`, `get_unique_constraints()`
   - `get_table_ddl()`, `get_view_ddl()`, `get_routine_ddl()`

3. Crear `metadata/manager.py` que orqueste: Builder + Fetcher + Cache

**Checklist:**
- [ ] Crear `metadata/builder.py` - DDL builder
- [ ] Crear `metadata/fetcher.py` - Metadata fetcher
- [ ] Crear `metadata/manager.py` - Orchestrator
- [ ] Extraer métodos de `database_manager.py`
- [ ] Mantener compatibilidad en `database_manager.py` (delegación)
- [ ] ✅ 443/443 tests passing
- [ ] Reducir líneas en `database_manager.py`

---

### FASE 5: Reorganización de Resultados y Bulk

#### PR #10: Crear `results/` - Normalización y tipos

**Objetivo:** Centralizar gestión de resultados

**Archivos a crear:**
```
src/util_bbdd/results/
├── normalizer.py     # migrate result_normalizer.py
├── types.py          # migrate result_types.py
├── converters.py     # NEW: Motor-specific converters
└── __init__.py       # Exports
```

**Acciones:**
1. Migrar `result_normalizer.py` → `results/normalizer.py`
2. Migrar `result_types.py` → `results/types.py`
3. Crear `results/converters.py` para conversiones específicas del motor

**Checklist:**
- [ ] `results/normalizer.py`
- [ ] `results/types.py`
- [ ] `results/converters.py`
- [ ] `results/__init__.py`
- [ ] ✅ 443/443 tests passing

---

#### PR #11: Reorganizar `bulk/` - Renombrar de bulk_crud

**Objetivo:** Renombrar y reorganizar operaciones masivas

**Acciones:**
1. Renombrar `bulk_crud/` → `bulk/`
2. Migrar `bulk_crud.py` → `bulk/crud.py`
3. Migrar `audit_manager.py` → `bulk/audit.py`
4. Migrar `normalizacion_sql.py` → `bulk/normalization.py`
5. Crear `bulk/__init__.py`

**Checklist:**
- [ ] Renombrar directorio
- [ ] Migrar archivos
- [ ] `bulk/__init__.py`
- [ ] ✅ 443/443 tests passing
- [ ] Backward compatibility

---

### FASE 6: Reorganización de Análisis

#### PR #12: Reorganizar `analysis/` - Renombrar de grafos

**Objetivo:** Renombrar y reorganizar análisis de relaciones

**Archivos a crear:**
```
src/util_bbdd/analysis/
├── relationship_graph.py     # Base moved from relationship_graph_base.py
├── visualizers/
│   ├── graphviz.py          # from graphviz_relationship_graph.py
│   ├── graphviz_extended.py # from graphviz_relationship_graph_ext.py
│   ├── matplotlib.py        # from matplotlib_relationship_graph.py
│   └── __init__.py
└── __init__.py
```

**Acciones:**
1. Renombrar `grafos/` → `analysis/`
2. Migrar `relationship_graph_base.py` → `analysis/relationship_graph.py`
3. Crear `analysis/visualizers/`:
   - `graphviz_relationship_graph.py` → `visualizers/graphviz.py`
   - `graphviz_relationship_graph_ext.py` → `visualizers/graphviz_extended.py`
   - `matplotlib_relationship_graph.py` → `visualizers/matplotlib.py`

**Checklist:**
- [ ] Renombrar directorio
- [ ] Migrar archivos
- [ ] Crear `visualizers/` subdir
- [ ] `analysis/__init__.py`
- [ ] ✅ 443/443 tests passing

---

### FASE 7: Crear Managers de Alto Nivel

#### PR #13: Crear `managers/database.py` - Refactorizar DatabaseManager

**Objetivo:** Refactorizar `database_manager.py` (~1400 líneas → ~500 líneas)

**Archivos a crear:**
```
src/util_bbdd/managers/
├── database.py       # Refactored database_manager.py
└── __init__.py       # Exports
```

**Cambios principales:**
1. Inyectar dependencias:
   - `ConnectionManager`
   - `MetadataManager`
   - `QueryExecutor`
   - `BulkOperator`

2. Delegación en lugar de implementación:
```python
class DatabaseManager:
    def __init__(self, ...):
        self._connection_mgr = ConnectionManager(...)
        self._metadata_mgr = MetadataManager(...)
        self._query_executor = QueryExecutor(...)
        self._bulk_operator = BulkOperator(...)

    def get_tables(self) -> list:
        return self._metadata_mgr.get_tables()

    def get_columns(self, table: str) -> list:
        return self._metadata_mgr.get_columns(table)

    def execute_query(self, name: str, params: dict):
        return self._query_executor.execute_query(name, params)

    def bulk_insert(self, table: str, records: list):
        return self._bulk_operator.insert(table, records)
```

**Checklist:**
- [ ] Refactorizar `database_manager.py`
- [ ] Crear inyección de dependencias
- [ ] Delegación en lugar de implementación
- [ ] Reducir líneas significativamente
- [ ] Crear `managers/database.py`
- [ ] ✅ 443/443 tests passing
- [ ] Backward compatibility

---

#### PR #14: Crear `managers/async_database.py`

**Objetivo:** Refactorizar `async_database_manager.py`

**Acciones:**
1. Aplicar mismo patrón a `async_database_manager.py`
2. Mover a `managers/async_database.py`
3. Inyectar dependencias async
4. Delegación

**Checklist:**
- [ ] Refactorizar async manager
- [ ] Crear `managers/async_database.py`
- [ ] Paridad async/sync
- [ ] ✅ 443/443 tests passing

---

### FASE 8: Cleanup y Documentación

#### PR #15: Eliminar directorios antiguos y cleanup

**Objetivo:** Limpiar código remanente

**Acciones:**
1. Eliminar `executors/` (migrado a `query/executors/`)
2. Eliminar `connection/{motor}/` (migrado a `connection/motors/`)
3. Eliminar `validators/` (integrado en `_drivers/`)
4. Eliminar `core/` (integrado en `_core/`)
5. Eliminar `bulk_crud/` (renombrado a `bulk/`)
6. Eliminar `grafos/` (renombrado a `analysis/`)
7. Eliminar archivos únicos en raíz (migrados)
8. Actualizar todos los imports

**Checklist:**
- [ ] Eliminar directorios vacíos
- [ ] Eliminar archivos migrados
- [ ] Actualizar imports en `__init__.py`
- [ ] ✅ 443/443 tests passing
- [ ] Validar que no hay referencias a archivos eliminados

---

#### PR #16: Documentación - Arquitectura y Migration Guide

**Objetivo:** Documentar nueva estructura

**Archivos a crear:**
```
docs/
├── ARCHITECTURE.md          # Guía de arquitetura
├── MODULES.md              # Descripción de módulos
├── MIGRATION_GUIDE.md      # Guía de migración para usuarios
└── REFACTORING_COMPLETE.md # Resumen de cambios
```

**Acciones:**
1. Actualizar README.md con nueva estructura
2. Crear `ARCHITECTURE.md` con diagrama y descripción
3. Crear `MODULES.md` con cada módulo y responsabilidad
4. Crear `MIGRATION_GUIDE.md` para users
5. Actualizar todos los docstrings

**Checklist:**
- [ ] README.md actualizado
- [ ] ARCHITECTURE.md creado
- [ ] MODULES.md creado
- [ ] MIGRATION_GUIDE.md creado
- [ ] Todos los docstrings actualizados
- [ ] Ejemplos de uso

---

### FASE 9: Validación Final

#### PR #17: Full Test Suite y Validación

**Objetivo:** Validar que todo sigue funcionando perfectamente

**Acciones:**
1. `pytest tests/ -v` → ✅ 443/443 passing
2. `pytest tests/ --cov` → Coverage > 80%
3. `mypy src/` → 0 errors
4. `ruff check src/` → 0 errors
5. `black src/` → Bien formateado
6. Validar imports circulares
7. Benchmarking de performance

**Checklist:**
- [ ] 443/443 tests passing
- [ ] Coverage > 80%
- [ ] mypy: 0 errors
- [ ] ruff: 0 errors
- [ ] black: formatted ok
- [ ] No imports circulares
- [ ] Performance no degraded

---

## 📊 Resumen de Cambios por PR

| PR | Fase | Objetivo | Archivos | Tests |
|----|------|----------|----------|-------|
| #1 | 1 | _core/ | 5 nuevos | ✅ |
| #2 | 1 | _drivers/ | 4 nuevos | ✅ |
| #3 | 2 | connection/ consolidar | 7 movidos | ✅ |
| #4 | 2 | connection/motors/ | 8 nuevos | ✅ |
| #5 | 2 | data/loader.py | 1 nuevo | ✅ |
| #6 | 3 | query/ - registry/resolver | 4 movidos | ✅ |
| #7 | 3 | query/executors/ | 2 movidos | ✅ |
| #8 | 4 | metadata/ - base | 3 movidos | ✅ |
| #9 | 4 | metadata/ - builder/fetcher | 3 nuevos | ✅ |
| #10 | 5 | results/ | 3 movidos | ✅ |
| #11 | 5 | bulk/ - rename | 3 movidos | ✅ |
| #12 | 6 | analysis/ - rename | 5 movidos | ✅ |
| #13 | 7 | managers/database.py | 1 refactor | ✅ |
| #14 | 7 | managers/async_database.py | 1 refactor | ✅ |
| #15 | 8 | Cleanup | Eliminar | ✅ |
| #16 | 8 | Documentación | 4 nuevos | ✅ |
| #17 | 9 | Validación Final | - | ✅ |

---

## ✅ Criterios de Aceptación por PR

### General (Todas las PRs)
- ✅ 443/443 tests passing (100%)
- ✅ Coverage >= 80%
- ✅ `mypy src/` → 0 errors
- ✅ `ruff check src/` → 0 errors
- ✅ `black --check src/` → formatted ok
- ✅ Backward compatibility mantenida
- ✅ Documentación actualizada
- ✅ Code review approval

### Específico por Fase
- **Fase 1:** `_core/` and `_drivers/` completamente funcionales
- **Fase 2:** `connection/` completamente reorganizado
- **Fase 3:** `query/` funciona sync y async
- **Fase 4:** `metadata/` reemplaza toda lógica antigua
- **Fase 5:** `bulk/` y `results/` funcionan
- **Fase 6:** `analysis/` visualiza relaciones
- **Fase 7:** `managers/` < 500 líneas c/u
- **Fase 8:** No hay código huérfano
- **Fase 9:** Release ready

---

## 🚨 Rollback Plan

Cada PR debe tener rollback plan:

**Si PR falla:**
1. Revert automático
2. Notificar en PR
3. Analizar error
4. Crear PR fix

**No mergear PRs con:**
- ❌ Tests fallando
- ❌ Coverage < 80%
- ❌ Import circulares
- ❌ mypy/ruff errors

---

## 📈 Métricas de Éxito

**Antes (v0.4.0):**
- Líneas máx/archivo: 1400+
- CC máximo: 22
- Módulos en root: 16
- Cohesión: Media

**Después (v0.5.0):**
- Líneas máx/archivo: <500
- CC máximo: ~8
- Módulos en root: 6
- Cohesión: Alta
- Acoplamiento: Bajo

---

## 📅 Timeline Sugerido

```
Semana 1:  PR #1-2 (Preparación)
Semana 2-3: PR #3-5 (Conexión)
Semana 4: PR #6-8 (Queries)
Semana 5-6: PR #9-11 (Metadatos, Resultados)
Semana 7: PR #12 (Análisis)
Semana 8-9: PR #13-16 (Managers, Docs)
Semana 10: PR #17 (Validación)
Semana 11: Release v0.5.0

Total: ~11 semanas
Esfuerzo: 105-140 horas
```

---

**Documento completado.** Listo para iniciar ejecución de PRs.
