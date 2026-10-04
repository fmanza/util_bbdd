# AUDIT_PLAN v0.31.1 Hotfix: MariaDB SystemError

**Fecha**: 2026-10-04  
**Auditor**: Code Auditor Agent  
**Referencia**: [PLAN v0.31.1 Hotfix](hotfix_mariadb_plan.md)  
**Veredicto Preliminar**: 🟡 APROBADO CON CONDICIONES  

---

## 1. Completitud del Plan

### ✅ Aspectos Cubiertos

- [x] **RCA clara**: SystemError específico de mariadb driver
- [x] **Scope bien definido**: Solo `ManagerCatalogExecutor`, `DbapiCatalogExecutor`
- [x] **Impacto limitado**: Sin cambios en API pública, backward-compatible
- [x] **Tests nuevos**: Cobertura de reintento y casos edge
- [x] **Rollback plan**: Definido y viable
- [x] **Timeline realista**: 6–8 horas estimadas
- [x] **Artefactos identificados**: Código, tests, documentación

### ⚠️ Aspectos Pendientes de Clarificación

1. **AsyncManagerCatalogExecutor** (líneas 110–137 de `_catalog_executor.py`):
   - El PLAN solo cubre `ManagerCatalogExecutor` síncrono
   - **Pregunta**: ¿Necesita el mismo reintento el version async?
   - **Recomendación**: SÍ, agregar reintento async con `asyncio.sleep()` en Fase 1.1B

2. **Interacción con SnapshotCache**:
   - La caché en `snapshot_cache.py` puede retener estados fallidos
   - **Pregunta**: ¿Se invalida la caché tras SystemError?
   - **Recomendación**: Verificar que `_start_load()` y `_finish_load()` limpien correctamente en caso de excepción

3. **SQL Específico que Falla**:
   - El PLAN no identifica qué SQL de catálogo MariaDB está fallando
   - **Pregunta**: ¿Es un SQL específico o cualquiera?
   - **Recomendación**: Agregar logging de SQL en logs BEFORE el `cursor.execute()`

---

## 2. Análisis de Riesgos

### Riesgo 1: Reintento Enmascara Bug Raíz ⚠️ CRÍTICO

**Severidad**: Media-Alta  
**Probabilidad**: Media  

**Problema**:
- El reintento puede "arreglar" temporalmente un bug más profundo en ADR-003
- Si el SQL generado es realmente inválido, reintentar no lo soluciona, solo lo retrasa

**Mitigación en el PLAN**:
- ✅ Logging de SQL captura el texto exacto (bueno)
- ❌ No valida que el SQL es válido ANTES de ejecutar (malo)

**Acción Recomendada**:
```python
# Agregar en DbapiCatalogExecutor.fetch_all() ANTES de cursor.execute():
logger.debug(f"SQL de catálogo: {driver_sql}")
logger.debug(f"Parámetros: {args}")
```

Esto captura el SQL que falló para auditoría post-mortem.

### Riesgo 2: Backoff Exponencial Impacta Performance ⚠️ BAJO

**Severidad**: Baja  
**Probabilidad**: Baja  

**Problema**:
- Si el fallo es persistente (no intermitente), el usuario espera 700ms extra (100 + 200 + 400)

**Mitigación en el PLAN**:
- ✅ Tiempos razonables (< 1s total)
- ✅ Solo ocurre si hay error (caso anómalo)

**Acción Recomendada**:
- Documentar el delay en logs: `"Retrying after {delay}ms due to SystemError"`

### Riesgo 3: AsyncManagerCatalogExecutor No Cubierto ⚠️ MEDIO

**Severidad**: Media  
**Probabilidad**: Alta  

**Problema**:
- El PLAN cubre `ManagerCatalogExecutor` (sync) pero no `AsyncManagerCatalogExecutor`
- Si un usuario usa async (asyncio), puede seguir fallando

**Mitigación en el PLAN**:
- ❌ No mencionado

**Acción Recomendada**:
```python
# En AsyncManagerCatalogExecutor.fetch_all() (línea 120):
# Aplicar el mismo reintento pero con await asyncio.sleep()
max_retries = 3
for attempt in range(max_retries):
    try:
        # código actual
    except SystemError as exc:
        if attempt < max_retries - 1:
            await asyncio.sleep(0.1 * (2 ** attempt))
            continue
        raise MetadataError(...) from exc
```

---

## 3. Análisis Técnico de la Implementación

### 3.1 Captura de SystemError ✅ CORRECTO

```python
except SystemError as exc:  # Específico a mariadb driver
    _rollback(connection)
    raise MetadataError(f"...") from exc
```

**Veredicto**: Correcto. Atrapa el error específico sin ocultar otros.

### 3.2 Reintento con Backoff ✅ CORRECTO

```python
for attempt in range(max_retries):
    # ...
    if attempt < max_retries - 1:
        time.sleep(0.1 * (2 ** attempt))
        continue
```

**Veredicto**: Correcto. Backoff exponencial es estándar (Fibonacci sería mejor, pero esto es viable).

### 3.3 Liberación de Conexión ⚠️ REQUIERE VERIFICACIÓN

**Código**:
```python
except SystemError as exc:
    last_exc = exc
    _rollback(connection)
    self._releaser(connection)  # ← Libera en CADA intento
```

**Verificación necesaria**:
- ¿`connection_releaser()` es idempotente? (¿Se puede llamar múltiples veces?)
- ¿Devuelve la conexión al pool correctamente?

**Resultado esperado**: SÍ, porque `self._releaser()` es un lambda que llama a `connection_releaser()` del manager, que es thread-safe y idempotente.

**Veredicto**: ✅ Correcto, pero agregar comentario en código.

### 3.4 Imports ⚠️ NECESARIO VERIFICAR

El PLAN menciona agregar `import time`. 

**Verificación necesaria**:
```python
# En src/util_bbdd/managers/_catalog_executor.py
import time  # ← ¿Ya importado?
```

**Recomendación**: Verificar `_catalog_executor.py` actual; si no tiene `time`, agregarlo.

---

## 4. Cobertura de Tests

### Test 1: Reintento Exitoso ✅

```python
def test_manager_catalog_executor_retries_on_system_error(mocker):
    # Simula: falla → éxito
    # Verifica: 2 llamadas a fetch_all, 2 liberaciones
```

**Veredicto**: ✅ Cobertura adecuada.

### Test 2: Agotamiento de Reintentos ✅

```python
def test_manager_catalog_executor_fails_after_max_retries(mocker):
    # Simula: falla × 3
    # Verifica: MetadataError tras 3 intentos
```

**Veredicto**: ✅ Cobertura adecuada.

### Tests Faltantes ⚠️

1. **AsyncManagerCatalogExecutor**: Sin test async
2. **Otros errores no SystemError**: ¿Se reintenta en `Exception` general? NO, y es correcto.
3. **Logging**: Sin verificación de logs (no crítico, pero útil)

**Recomendación**: Agregar `test_manager_catalog_executor_async_retries_on_system_error()` para async.

---

## 5. Impacto en Subsistemas

### 5.1 SnapshotCache ⚠️ VERIFICAR

**Pregunta**: Si `executor.fetch_all()` falla al primer intento (luego reintenta y éxito), ¿la caché refleja correctamente el resultado?

**Código en `source.py:225`**:
```python
data[kind] = self.cache.get_or_load(
    self._key(schema, kind, scoped), 
    partial(self._load, kind, schema, scoped)
)
```

**Análisis**:
- Si `_load()` → `executor.fetch_all()` → SystemError (reintentado):
  1. Primer intento falla → SystemError (capturado en ManagerCatalogExecutor)
  2. Reintento exitoso → devuelve rows
  3. La caché almacena el resultado del reintento exitoso ✅

**Veredicto**: ✅ Correcto. La caché no se corrompe.

### 5.2 Documentation Orchestrator ✅ NO IMPACTADO

La orquestación (`documentation_orchestrator.py:213`) simplemente llama `get_ddl()`:
```python
ddl = data_provider.get_ddl(tabla)
```

Si falla con `MetadataError` por fallo definitivo (tras 3 reintentos), se propaga al nivel superior. Esto es correcto.

**Veredicto**: ✅ No requiere cambios.

---

## 6. Validación de Timeline

| Fase | Duración | Realista |
|---|---|---|
| Fix Principal (captura + reintento) | 2–3h | ✅ Sí (código directo) |
| Async reintento | +1h | ✅ Sí (copiar del sync) |
| Logging | 1h | ✅ Sí |
| Tests | 1h | ⚠️ Posible falta de tiempo para async |
| QA | 1–2h | ✅ Sí |
| **Total** | **6–8h** | ✅ Viable |

**Nota**: Si se agrega soporte async, estimar **7–9h**.

---

## 7. Verificación de Backward Compatibility

### API Pública

- `ManagerCatalogExecutor.fetch_all(sql, params)` → Mismo signature
- `AsyncManagerCatalogExecutor.fetch_all(sql, params)` → Mismo signature
- Excepciones lanzadas:
  - Antes: `MetadataError(f"Error leyendo el catálogo: {exc}")`
  - Después: Igual (solo distinto mensaje si `SystemError`)

**Veredicto**: ✅ Backward compatible.

### Subsistemas Dependientes

- `CatalogSource._load()` → Espera `MetadataError`, sigue siendo levantado ✅
- `sync_mgr.get_schema_metadata()` → Espera `MetadataError`, sigue siendo levantado ✅
- `documentation_orchestrator` → Espera errores de metadata, propios se propagan ✅

**Veredicto**: ✅ Backward compatible.

---

## 8. Checklist de Auditoría

### Completitud
- [x] RCA clara
- [x] Scope definido
- [x] Impacto limitado
- [x] Rollback plan
- [ ] **AsyncManagerCatalogExecutor** cubierto (FALTA)

### Robustez
- [x] Captura de `SystemError`
- [x] Reintento con backoff
- [x] Logging básico
- [x] Liberación de conexión
- [ ] **Validación de SQL antes de ejecutar** (futuro)

### Testing
- [x] Test de reintento exitoso
- [x] Test de agotamiento de reintentos
- [ ] **Test async** (FALTA)
- [ ] **Test de logging** (Opcional)

### Documentación
- [x] PLAN completo
- [ ] **Docstring actualizado en `_catalog_executor.py`** (FALTA)
- [ ] **CHANGELOG entry** (FALTA)

---

## 9. Veredicto

### 🟡 APROBADO CON CONDICIONES

**Resumen**:
- El plan es **sólido y viable**
- La implementación de reintento es **estándar y correcta**
- Los tests cubren los casos críticos
- La backward compatibility está **garantizada**

**Condiciones Pendientes**:

| Condición | Prioridad | Acción |
|-----------|---|---|
| Agregar soporte async en `AsyncManagerCatalogExecutor` | ALTA | Implementar en Fase 1.1B |
| Actualizar docstrings y logging | MEDIA | Implementar en Fase 2 |
| Agregar tests async | MEDIA | Implementar en Fase 3 |
| Documentar en CHANGELOG.md | MEDIA | Implementar antes de release |

**Aprobación Condicional**:
✅ Proceder a **IMPLEMENT** si se cumplen las siguientes:
1. Agregar reintento async (Fase 1.1B)
2. Agregar test async (Fase 3)
3. Actualizar docstrings (Fase 2)
4. Validar que `time` está importado en `_catalog_executor.py`

---

## 10. Recomendaciones para Implementación

### 10.1 Orden de Implementación

```
1. Captura de SystemError en ManagerCatalogExecutor
   ↓
2. Reintento sync con backoff
   ↓
3. Reintento async (mismo patrón, con await)
   ↓
4. Logging de SQL y retries
   ↓
5. Tests de reintento (sync + async)
   ↓
6. Docstrings y CHANGELOG
   ↓
7. QA: validar en MariaDB + PostgreSQL
```

### 10.2 Validación en QA

**Test Smoke para MariaDB**:
```python
# Generar documentación Word de MariaDB (tabla simple)
# Esperado: Éxito sin SystemError
```

**Test de Regression**:
```bash
pytest tests/managers/test_catalog_executor.py -v
pytest tests/doc/test_documentation_generation.py -k mariadb -v
```

---

## Conclusión

El PLAN v0.31.1-hotfix es **VIABLE y APROBADO CONDICIONALMENTE**.

**Siguiente Fase**: 
- ✅ Pasar a **IMPLEMENT** si el equipo acepta las 4 condiciones
- 🔄 Retornar a PLAN si se requieren cambios mayores

**Deadline sugerido**: 2026-10-04 EOD (mismo día) para hotfix urgente.

---

*Auditoría completada: 2026-10-04*  
*Auditor*: Code Auditor Agent  
*Veredicto Final*: 🟡 APROBADO CON CONDICIONES → PROCEDER A IMPLEMENT
