# PHASE 4B PLANNING: Metadata Adapters Refactor — Herencia + Logging

**Fecha**: 18 de abril de 2026
**Status**: 🟡 **GO_CONDICIONAL** (Requiere Fase 4B.1 previa)
**Esfuerzo estimado**: 4.5 horas (1h validación + 3-4h implementación)
**Riesgo**: MEDIUM (Herencia múltiple + Manager protocols incompletos)

---

## 📋 RESUMEN EJECUTIVO

### Objetivo
Refactorizar **14 adaptadores concretos** (MariaDB, PostgreSQL, Oracle, SQLite, SQLServer, MySQL, Redshift, Snowflake × Sync/Async) para heredar de `BaseSourceAdapter` + `BaseRoutineAdapter`, eliminando duck-typing y ganando logging tipado automático.

### Hallazgo Crítico 🔴
**Los 8 manager protocols NO exponen `logger` property** — BLOQUEANTE para herencia.

**Solución**: Fase 4B.1 (validación previa) debe crear/actualizar protocolos antes de Fase 4B.2 (implementación).

### Timeline Recomendado
- **Hoy**: Fase 4B.1 (Validación + Protocolos) — 1 hora
- **Próxima sesión**: Fase 4B.2 (Implementación) + Fase 4B.3 (Testing) — 3-4 horas

---

## 🔍 SITUACIÓN ACTUAL (Auditoría)

### BaseSourceAdapter + BaseRoutineAdapter ✅
- **Ubicación**: [src/util_bbdd/metadata/adapters/base_adapter.py](src/util_bbdd/metadata/adapters/base_adapter.py)
- **Status**: Completo, con logger tipado (v0.6.7 tras Fase 4A)
- **Requisitos**: `logger: logging.Logger`, `cache_service: CacheService` en `__init__`

### Manager Protocols — **PROBLEMA ENCONTRADO** 🔴

| Motor | Protocolo | `db_cache` | `logger` | Status |
|-------|-----------|-----------|----------|--------|
| MariaDB | `MariaDBSyncManagerProtocol` | ✅ | ❌ | INCOMPLETO |
| MariaDB | `MariaDBAsyncManagerProtocol` | ✅ | ❌ | INCOMPLETO |
| PostgreSQL | — | — | — | ❌ NO EXISTE |
| Oracle | — | — | — | ❌ NO EXISTE |
| SQLite | — | — | — | ❌ NO EXISTE |
| SQL Server | — | — | — | ❌ NO EXISTE |
| MySQL | — | — | — | ❌ NO EXISTE |
| Redshift | — | — | — | ❌ NO EXISTE |
| Snowflake | — | — | — | ❌ NO EXISTE |

**Realidad**: `SyncDatabaseManager` y `AsyncDatabaseManager` SÍ exponen `logger` y `db_cache`, pero los **protocolos no los documentan**.

### 14 Adaptadores Concretos — Estado

Ninguno hereda de BaseSourceAdapter/BaseRoutineAdapter:
- **MariaDB** (2 clases): MariaDBSyncAdapter, MariaDBAsyncAdapter
- **PostgreSQL** (2 clases): PostgreSQLSyncAdapter, PostgreSQLAsyncAdapter
- **Oracle** (2 clases): OracleSyncAdapter, OracleAsyncAdapter
- **SQLite** (2 clases): SqliteSyncAdapter, SqliteAsyncAdapter
- **SQL Server** (2 clases): SqlServerSyncAdapter, SqlServerAsyncAdapter
- **MySQL** (2 clases): MysqlSyncAdapter, MysqlAsyncAdapter
- **Redshift** (2 clases): RedshiftSyncAdapter, RedshiftAsyncAdapter
- **Snowflake** (2 clases): SnowflakeSyncAdapter, SnowflakeAsyncAdapter

**Todos declaran**: `def __init__(self, manager: Any)` (duck-typed, sin contrato).

---

## 📊 PLAN FASE 4B

### Scope

**IN**:
- ✅ Herencia múltiple: `class XxxSyncAdapter(BaseSourceAdapter, BaseRoutineAdapter):`
- ✅ Inyección de logger y cache_service desde manager
- ✅ Actualizar/crear 8 manager protocols
- ✅ Tipado fuerte: Cambiar `manager: Any` por protocolos específicos
- ✅ Validación de MRO (Method Resolution Order)

**OUT**:
- ❌ Cambios en APIs públicas (firma `__init__` sigue siendo `(manager)`)
- ❌ Refactor de MetadataFetcher, MetadataManager
- ❌ Cambios en QueryRegistry o Comparar

---

### Fase 4B.1 — Validación + Protocolos (1 hora) ⚠️ REQUERIDA

**Tareas**:

1. **Actualizar MariaDBSyncManagerProtocol** + **MariaDBAsyncManagerProtocol**
   - Añadir property: `logger: logging.Logger`
   - Archivo: `src/util_bbdd/metadata/mariadb/_manager_protocol.py`

2. **Crear 6 nuevos protocolos base** (para PostgreSQL, Oracle, SQLite, SQLServer, MySQL, Redshift, Snowflake)
   - Cada uno: `class XxxSyncManagerProtocol(Protocol):` con `logger` + `db_cache` properties
   - Ubicación: `src/util_bbdd/metadata/xxx/_manager_protocol.py` (o centralizado)

3. **Validación de importación** (sin ciclos)
   ```bash
   python -c "from util_bbdd.metadata.mariadb import MariaDBSyncAdapter; print('✅')"
   ```

4. **Validación de atributos**
   ```bash
   python << 'EOF'
   from util_bbdd.managers import SyncDatabaseManager
   mgr = SyncDatabaseManager(...)
   assert hasattr(mgr, 'logger'), "manager.logger falta"
   assert hasattr(mgr, 'db_cache'), "manager.db_cache falta"
   print("✅ Manager expone atributos requeridos")
   EOF
   ```

**Entrega Fase 4B.1**: Reporte GO/NO-GO con 8 protocolos listos.

---

### Fase 4B.2 — Implementación Incremental (2-3 horas)

**Estrategia**: Patrón piloto (MariaDB) → Replicar a 13 adapters.

**Pattern General**:
```python
# ANTES
class MariaDBSyncAdapter:
    def __init__(self, manager: MariaDBSyncManagerProtocol) -> None:
        self.manager = manager

# DESPUÉS
from logging import Logger
from ..adapters.base_adapter import BaseSourceAdapter, BaseRoutineAdapter

class MariaDBSyncAdapter(BaseSourceAdapter, BaseRoutineAdapter):
    def __init__(self, manager: MariaDBSyncManagerProtocol) -> None:
        logger: Logger = manager.logger
        cache_service: CacheService = CacheService(manager.db_cache)  # si aplica
        super().__init__(logger=logger, cache_service=cache_service)
        self.manager = manager
```

**Ejecución**:
1. **MariaDB piloto** (30 min)
   - Editar: `mariadb/sync_adapter.py` + `mariadb/async_adapter.py`
   - Test: `pytest tests/integration/test_mariadb_metadata.py -v`
   - Si PASSED → continuar
   - Si FAILED → RCA, ajustar patrón

2. **Replicar a 6 motores restantes** (1.5-2 horas)
   - ~10 min por motor (2 archivos: sync + async)

**Archivos a modificar**:
```
src/util_bbdd/metadata/
├── mariadb/sync_adapter.py         (+ async_adapter.py)
├── postgresql/sync_adapter.py      (+ async_adapter.py)
├── oracle/sync_adapter.py          (+ async_adapter.py)
├── sqlite/sync_adapter.py          (+ async_adapter.py)
├── sqlserver/sync_adapter.py       (+ async_adapter.py)
├── mysql/sync_adapter.py           (+ async_adapter.py)
├── redshift/sync_adapter.py        (+ async_adapter.py)
└── snowflake/sync_adapter.py       (+ async_adapter.py)
```

---

### Fase 4B.3 — Validación Completa (1 hora)

**Tareas**:
1. Type-check: `mypy src/util_bbdd/metadata/ --strict` → 0 errores
2. Lint: `ruff check src/util_bbdd/metadata/` → 0 errores
3. MRO validation: Verificar que cada adapter hereda correctamente
4. Integration tests: `pytest tests/integration/test_*_metadata.py -v` → 100% pass (8 motores)

**Script de validación MRO**:
```python
# scripts/validate_metadata_mro.py
from util_bbdd.metadata.mariadb import MariaDBSyncAdapter, MariaDBAsyncAdapter
from util_bbdd.metadata.postgresql import PostgreSQLSyncAdapter, PostgreSQLAsyncAdapter
# ... etc

adapters = [
    MariaDBSyncAdapter, MariaDBAsyncAdapter,
    PostgreSQLSyncAdapter, PostgreSQLAsyncAdapter,
    # ... 10 más
]

from util_bbdd.metadata.adapters.base_adapter import BaseSourceAdapter, BaseRoutineAdapter

for adapter_cls in adapters:
    mro = [c.__name__ for c in adapter_cls.__mro__]
    print(f"{adapter_cls.__name__}: {mro}")
    assert BaseSourceAdapter in adapter_cls.__mro__, f"{adapter_cls.__name__} no hereda BaseSourceAdapter"
    assert BaseRoutineAdapter in adapter_cls.__mro__, f"{adapter_cls.__name__} no hereda BaseRoutineAdapter"

print("✅ Todas las heredancias validadas")
```

---

## ⚠️ RIESGOS IDENTIFICADOS

### Bloqueantes 🔴

| Riesgo | Encontrado | Mitigación |
|--------|-----------|-----------|
| **Manager protocols no exponen `logger`** | ✅ SÍ | Fase 4B.1: Actualizar 8 protocolos |
| **7 motores sin protocolos definidos** | ✅ SÍ | Fase 4B.1: Crear 6 nuevos protocolos |
| **Ciclo de importación metadata/mariadb ↔ adapters** | DESCONOCIDO | Validar: `python -c "from util_bbdd.metadata.mariadb import..."` |

### Técnicos 🟡

| Riesgo | Probabilidad | Impacto | Validación |
|--------|-------------|--------|-----------|
| Herencia múltiple genera MRO conflict | MEDIA | MEDIUM | Script MRO post-impl |
| BaseSourceAdapter + BaseRoutineAdapter comparten métodos | BAJA | MEDIUM | Audit de method names |
| Tests de integración fallan por herencia | MEDIA | MEDIUM | Suite completa 8 motores |
| Métodos override en adapters compiten | BAJA | MEDIUM | Grep de overrides previa |

---

## 🎯 VEREDICTO

### **🟡 GO_CONDICIONAL**

**Condiciones para proceder**:

#### **PRE-4B.2** (Fase 4B.1):
- [ ] Actualizar 2 protocolos MariaDB con `logger` property
- [ ] Crear 6 nuevos protocolos (PostgreSQL, Oracle, SQLite, SQLServer, MySQL, Redshift, Snowflake)
- [ ] Validar `python -c "from util_bbdd.metadata.mariadb import MariaDBSyncAdapter"` (sin ciclos)
- [ ] Validar managers reales exponen `logger` y `db_cache`

#### **POST-4B.2** (Fase 4B.3):
- [ ] `mypy src/util_bbdd/metadata/ --strict` → PASSED
- [ ] `ruff check src/util_bbdd/metadata/` → PASSED
- [ ] MRO validation script → PASSED
- [ ] Integration tests 8 motores → 100% PASSED

#### **Timeline**:
- **Sesión 1 (Hoy)**: Fase 4B.1 (1 hora) ← Decisión aquí
- **Sesión 2 (Próxima)**: Fase 4B.2 + 4B.3 (4 horas)

---

## 📈 IMPACTO

**Pre-4B**:
- 14 adapters sin logging tipado
- Duck-typed `manager: Any`
- Código duplicado de caché

**Post-4B**:
- ✅ 14 adapters con logging tipado (heredado)
- ✅ Tipado fuerte via protocolos
- ✅ 0% código duplicado (heredado)
- ✅ Cobertura metadata: 100% (21 clases totales)

**Cobertura Global Post-4B**:
- Hoy: 21.2% (60 clases)
- Post-4B: 21.5% (60 + 14 = 74 clases)

---

## 🚀 OPCIONES PARA PROCEDER

### **OPCIÓN 1: Ejecutar Fase 4B.1 Hoy** (RECOMENDADO)
- Tiempo: 1 hora
- Tareas: Validación + crear/actualizar 8 protocolos
- Resultado: Reporte GO/NO-GO para Fase 4B.2
- **Ventaja**: Clarificas bloqueantes hoy, decisión clara para próxima sesión

👉 **Di**: `Ejecutar Fase 4B.1 (Validación)`

---

### **OPCIÓN 2: Posponer Fase 4B Completamente**
- Completar Fase 5 primero (Doc + Analysis)
- Fase 4B para v0.6.8 o v0.7.0
- **Ventaja**: Menos presión, mejor planificación

👉 **Di**: `Ejecutar Fase 5`

---

### **OPCIÓN 3: Completar Fase 4B Hoy** (RIESGO)
- Todas las fases (4B.1 + 4B.2 + 4B.3) en ~4.5 horas
- Requiere mantener focus sin interrupciones
- **Riesgo**: Si aparece bloqueante en 4B.1, sesión se arruina

👉 **Di**: `Ejecutar Fase 4B Completa` (no recomendado)

---

### **OPCIÓN 4: Terminar Sesión**
- Hacer commit de Fases 1-4A
- Documentación + release notes
- Postergar 4B para próxima sesión

👉 **Di**: `Terminar sesión` o `Hacer commit`

---

## 📝 CHECKLIST FASE 4B.1

Si decides **Ejecutar Fase 4B.1**, necesitarás:

- [ ] Ubicar 8 manager protocol files (MariaDB existe, otros 7 crear)
- [ ] Auditar qué properties exponen actualmente
- [ ] Añadir `logger: logging.Logger` a cada uno
- [ ] Crear script de validación de imports
- [ ] Ejecutar validaciones previa
- [ ] Documentar hallazgos

**Estimado**: 1 hora, resultado claro para próxima sesión.

---

*Planificación completada: 18 de abril de 2026, 20:00 UTC*
