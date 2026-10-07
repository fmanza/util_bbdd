# PLAN v0.31.1 Hotfix: MariaDB SystemError en Lectura de Catálogo

**Fecha**: 2026-10-04  
**Versión**: 0.31.1  
**Tipo**: Hotfix CRÍTICO  
**Componentes afectados**: `metadata/`, `managers/`  
**Estimado**: 3–4 horas  

---

## Objetivo

Solucionar el `SystemError` que bloquea la generación de documentación en MariaDB, causado por corrupción de cursor en la nueva capa `ManagerCatalogExecutor` (ADR-003, v0.31.0). El fix debe ser **mínimo, no invasivo y sin romper API**.

---

## Análisis de Alcance

### Causa Raíz Confirmada
- **Driver**: `mariadb` library (MariaDB Connector/Python)
- **Función**: `DbapiCatalogExecutor.fetch_all()` en [src/util_bbdd/metadata/source.py](src/util_bbdd/metadata/source.py) línea 74
- **Problema**: El método nativo `cursor.fetchall()` retorna `SystemError` cuando el SQL ha fallado silenciosamente
- **Inicio**: v0.31.0 (ADR-003 centralización de metadatos)
- **Alcance**: Solo MariaDB/MySQL con driver `mariadb`; PostgreSQL, Oracle, SQL Server, SQLite **no afectados**

### Stack Trace Crítico
```
sync_mgr.py:680 (get_schema_metadata)
  → source.py:225 (_load via cache)
    → _catalog_executor.py:99 (ManagerCatalogExecutor.fetch_all)
      → source.py:74 (DbapiCatalogExecutor.fetch_all → cursor.fetchall) ❌
```

---

## Estrategia de Fix

### Nivel 1: Defensa en Profundidad (Inmediato)
Interceptar `SystemError` específico del driver mariadb y convertirlo a `MetadataError` tipado.

**Rationale**: El error es inherente al binding de C de mariadb; no se puede prevenir. Lo que podemos hacer es:
1. Capturar `SystemError` en `ManagerCatalogExecutor.fetch_all()`
2. Proporcionar mensaje de error claro
3. Activar reintento automático (Nivel 2)

### Nivel 2: Reintento Automático (Corto plazo)
Implementar retry con backoff exponencial en `ManagerCatalogExecutor.fetch_all()`.

**Rationale**: El problema es intermitente (depende de estado del cursor/conexión). Reintentar con nueva conexión del pool solventa la mayoría de casos.

### Nivel 3: Validación de SQL (Futuro)
En v0.32.0: Validar que `to_driver()` produce SQL válido antes de ejecutar.

---

## Plan de Implementación

### Fase 1: Fix Principal (2–3 horas)

#### 1.1 Captura de `SystemError` en `ManagerCatalogExecutor`

**Archivo**: `src/util_bbdd/managers/_catalog_executor.py`  
**Cambio**: Líneas 96–105

```python
def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    connection = self._provider()
    try:
        rows = DbapiCatalogExecutor(connection, driver_paramstyle(connection)).fetch_all(sql, params)
        return [tuple(_materialize(v) for v in row) for row in rows]
    except DatabaseException:
        raise
    except SystemError as exc:  # ← NUEVO: Capturar error específico de mariadb driver
        _rollback(connection)
        # Re-lanzar como MetadataError con contexto
        raise MetadataError(
            f"Error interno del driver MariaDB (cursor corrupto): {exc}. "
            "Reintentando con nueva conexión."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        _rollback(connection)
        raise MetadataError(f"Error leyendo el catálogo: {exc}") from exc
    finally:
        self._releaser(connection)
```

#### 1.2 Reintento Automático en `ManagerCatalogExecutor`

**Archivo**: `src/util_bbdd/managers/_catalog_executor.py`  
**Cambio**: Envolver `fetch_all()` en loop de reintento

```python
def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    max_retries = 3
    last_exc = None
    
    for attempt in range(max_retries):
        connection = self._provider()
        try:
            rows = DbapiCatalogExecutor(connection, driver_paramstyle(connection)).fetch_all(sql, params)
            return [tuple(_materialize(v) for v in row) for row in rows]
        except DatabaseException:
            self._releaser(connection)
            raise
        except SystemError as exc:  # ← Error específico de mariadb
            last_exc = exc
            _rollback(connection)
            self._releaser(connection)
            
            if attempt < max_retries - 1:
                # Backoff: 100ms, 200ms, 400ms
                time.sleep(0.1 * (2 ** attempt))
                continue
            
            # Último reintento falló
            raise MetadataError(
                f"Error leyendo catálogo (retentado {max_retries} veces): {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            _rollback(connection)
            self._releaser(connection)
            raise MetadataError(f"Error leyendo el catálogo: {exc}") from exc
    
    # No debería llegar aquí
    if last_exc:
        raise MetadataError(f"Error leyendo catálogo tras {max_retries} reintentos: {last_exc}") from last_exc
```

**Imports necesarios**: Agregar `import time` en `_catalog_executor.py`

---

### Fase 2: Logging Detallado (1 hora)

#### 2.1 Agregar Logs de Debug

**Archivo**: `src/util_bbdd/managers/_catalog_executor.py`  
**Cambio**: Logging dentro del reintento

```python
import logging

logger = logging.getLogger(__name__)

# Dentro del loop de reintento, línea 101 (aproximadamente)
logger.debug(f"[Attempt {attempt + 1}/{max_retries}] Ejecutando SQL de catálogo: {sql[:100]}...")
```

---

### Fase 3: Tests de Validación (1 hora)

#### 3.1 Test de Reintento (Nuevo)

**Archivo**: `tests/managers/test_catalog_executor.py` (crear si no existe)

```python
def test_manager_catalog_executor_retries_on_system_error(mocker):
    """Verifica que ManagerCatalogExecutor reinenta tras SystemError del driver mariadb."""
    provider = mocker.Mock()
    releaser = mocker.Mock()
    connection = mocker.Mock()
    provider.return_value = connection
    
    executor = ManagerCatalogExecutor(provider, releaser)
    
    # Simular SystemError en primer intento, éxito en segundo
    with mocker.patch("util_bbdd.managers._catalog_executor.DbapiCatalogExecutor") as mock_dbapi:
        mock_instance = mocker.Mock()
        mock_dbapi.return_value = mock_instance
        mock_instance.fetch_all.side_effect = [
            SystemError("cursor corrupto"),  # Primer intento: falla
            [(1, 2, 3)],  # Segundo intento: éxito
        ]
        
        result = executor.fetch_all("SELECT * FROM test", {})
        
        assert result == [(1, 2, 3)]
        assert mock_instance.fetch_all.call_count == 2
        assert releaser.call_count == 2  # Libera conexión en cada intento
```

#### 3.2 Test de Agotamiento de Reintentos

```python
def test_manager_catalog_executor_fails_after_max_retries(mocker):
    """Verifica que MetadataError se lanza tras agotar reintentos."""
    provider = mocker.Mock()
    releaser = mocker.Mock()
    connection = mocker.Mock()
    provider.return_value = connection
    
    executor = ManagerCatalogExecutor(provider, releaser)
    
    with mocker.patch("util_bbdd.managers._catalog_executor.DbapiCatalogExecutor") as mock_dbapi:
        mock_instance = mocker.Mock()
        mock_dbapi.return_value = mock_instance
        mock_instance.fetch_all.side_effect = SystemError("cursor siempre corrupto")
        
        with pytest.raises(MetadataError, match="retentado 3 veces"):
            executor.fetch_all("SELECT * FROM test", {})
        
        assert mock_instance.fetch_all.call_count == 3  # 3 intentos
```

---

## Requisitos No Funcionales

| Requisito | Cumplimiento |
|-----------|---|
| **Compatibilidad** | Backward-compatible; sin cambios en API pública |
| **Performance** | < 1 segundo de delay en caso de reintento (backoff exponencial) |
| **Mensajes de error** | Claros y actionable |
| **Logging** | DEBUG para SQL, ERROR para fallos finales |
| **Tests** | 100% cobertura de reintento y casos edge |

---

## Validación del Plan

### Criterios de Éxito

✅ **Funcional**:
- MariaDB + documentación Word/Excel/HTML sin error  
- Primer intento exitoso (sin reintentos visibles)  
- Reintentos automáticos si falla (transparentes para usuario)  

✅ **No Funcional**:
- Linting: 0 issues (ruff)  
- Type-checking: 0 errors (mypy)  
- Tests: 100% pass rate (pytest, incluye nuevos tests de reintento)  
- Backward compatibility: Todos los tests existentes pasan  

### Rollback Plan
Si hay problemas:
1. Revertir commits de Fase 1-2
2. Downgrade a v0.31.0
3. Usar workaround: PostgreSQL/SQL Server para documentación

---

## Timeline Estimado

| Fase | Duración | Hitos |
|---|---|---|
| **1. Fix Principal** | 2–3h | Captura de `SystemError` + reintento implementado |
| **2. Logging** | 1h | Debug logs agregados |
| **3. Tests** | 1h | Test suite ampliada (cobertura de reintento) |
| **QA** | 1–2h | Validación en MariaDB + PostgreSQL/Oracle |
| **Total** | **6–8h** | Hotfix v0.31.1 listo |

---

## Riesgos Identificados

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Reintento enmascara otro bug subyacente | Media | Alto | Logging detallado captura SQL y contexto |
| Backoff exponencial demora documentación | Baja | Bajo | Máx 400ms × 3 = 1.2s de delay |
| Otros drivers afectados | Muy baja | Alto | Solo mariadb tiene este `SystemError` |

---

## Artefactos de Salida

1. **Código**:
   - `src/util_bbdd/managers/_catalog_executor.py` (modificado)
   - `tests/managers/test_catalog_executor.py` (nuevo)

2. **Documentación**:
   - Este fichero (PLAN)
   - `AUDIT_PLAN.md` (auditoría técnica)
   - Entry en `CHANGELOG.md`

3. **Tests**:
   - `test_manager_catalog_executor_retries_on_system_error()`
   - `test_manager_catalog_executor_fails_after_max_retries()`
   - Suite de integración existente (sin cambios)

---

## Siguiente Paso

➜ **AUDIT_PLAN**: Revisar este plan contra:
  - Completitud (¿cubra todos los casos?)
  - Consistencia (¿sin conflictos internos?)
  - Riesgos (¿identificados correctamente?)
  - Realismo (¿timeline viable?)

---

*Fecha*: 2026-10-04  
*Versión*: PLAN v0.31.1-hotfix-001  
*Estado*: Listo para AUDIT_PLAN
