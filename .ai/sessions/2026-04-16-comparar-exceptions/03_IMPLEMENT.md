# IMPLEMENT: Ejecución de Cambios

## Level 1: Crear Excepciones en `_core/exceptions.py`

### Cambio 1.1: Agregar Categoría 6 de excepciones

**Archivo**: `_core/exceptions.py` (línea ~250)

**Adición**:
```python
# ============================================================================
# Categoría 6: Errores de Comparación de Esquemas (módulo comparar/)
# ============================================================================

class ComparerError(DatabaseException):
    """Excepción base para errores del módulo de comparación de esquemas."""
    pass

class SchemaDiffValidationError(ComparerError):
    """Error validando entrada o parámetros de comparación/reporte."""
    pass

class MetadataIntrospectionError(ComparerError):
    """Error obteniendo metadatos via SQLAlchemy Inspector."""
    pass

class DiffReportGenerationError(ComparerError):
    """Error generando reporte de diferencias en formato específico."""
    pass
```

**Status**: ✅ COMPLETADO

---

## Level 2: Actualizar Exports

### Cambio 2.1: Exportar nuevas excepciones en `_core/exceptions.py`

**Archivo**: `_core/exceptions.py` (`__all__`)

**Cambio**: Agregar 4 nuevas excepciones a `__all__`

**Status**: ✅ COMPLETADO

### Cambio 2.2: Importar y exportar en `comparar/__init__.py`

**Archivo**: `comparar/__init__.py`

**Cambio**:
- Importar desde `util_bbdd._core.exceptions`
- Agregar a `__all__`

**Status**: ✅ COMPLETADO

---

## Level 3: Agregar Imports en Módulos

### Cambio 3.1: Imports en `comparar/comparator.py`
- Añadido: `from util_bbdd._core.exceptions import MetadataIntrospectionError`
- **Status**: ✅ COMPLETADO

### Cambio 3.2: Imports en `reporters/sql_reporter.py`
- Añadido: `from util_bbdd._core.exceptions import SchemaDiffValidationError`
- **Status**: ✅ COMPLETADO

### Cambio 3.3: Imports en `reporters/facade.py`
- Añadido: `from util_bbdd._core.exceptions import DiffReportGenerationError, SchemaDiffValidationError`
- **Status**: ✅ COMPLETADO

### Cambio 3.4: Imports en `reporters/word_reporter.py`
- Añadido: `from util_bbdd._core.exceptions import SchemaDiffValidationError`
- **Status**: ✅ COMPLETADO

---

## Level 4: Reemplazar Excepciones Genéricas

### Cambio 4.1: `reporters/sql_reporter.py` línea 252

**Antes**:
```python
raise ValueError(f"Dialect '{dialect}' no soportado...")
```

**Después**:
```python
raise SchemaDiffValidationError(
    f"Dialect '{dialect}' no soportado...",
    operation="SqlDiffReporter.init",
    details=f"dialect={normalized}",
)
```

**Status**: ✅ COMPLETADO

### Cambio 4.2: `reporters/facade.py` línea 140

**Antes**:
```python
raise ValueError(f"Formato '{format}' no soportado...")
```

**Después**:
```python
raise SchemaDiffValidationError(
    f"Formato '{format}' no soportado...",
    operation="SchemaDiffReporter.render",
    details=f"format={fmt}",
)
```

**Status**: ✅ COMPLETADO

### Cambio 4.3: `reporters/word_reporter.py` línea 88

**Antes**:
```python
raise ValueError(f"'output' debe ser...")
```

**Después**:
```python
raise SchemaDiffValidationError(
    f"'output' debe ser...",
    operation="WordDiffReporter.render",
    details=f"output_path={output}...",
)
```

**Status**: ✅ COMPLETADO

---

## Level 5: Actualizar Tests

### Cambio 5.1 - 5.6: Actualizar tests en `test_diff_reporters.py`

| Test | Cambio |
|------|--------|
| `test_render_raises_on_directory_output` | `ValueError` → `SchemaDiffValidationError` |
| `test_render_raises_on_path_without_extension` | `ValueError` → `SchemaDiffValidationError` |
| `test_invalid_dialect_raises` | `ValueError` → `SchemaDiffValidationError` |
| `test_render_invalid_format` | `ValueError` → `SchemaDiffValidationError` |

**Import agregado**: `from util_bbdd._core.exceptions import SchemaDiffValidationError`

**Status**: ✅ COMPLETADO

---

## Validación

### Lint
```
All checks passed! ✅
```

### Type-check
```
Found 9 errors in 1 file (pre-existing, no-redef) ✅
```

### Tests
```
1878 passed, 1 skipped in 12.44s ✅
```

## Resumen de Cambios

- **Líneas agregadas**: ~60 (docstrings + 4 clases + imports)
- **Líneas modificadas**: ~15 (reemplazos de ValueError)
- **Líneas de tests actualizadas**: ~6
- **Archivos tocados**: 8
- **Cambios funcionales**: 0 (solo excepciones)
