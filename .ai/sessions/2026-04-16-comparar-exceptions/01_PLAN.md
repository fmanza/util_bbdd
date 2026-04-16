# PLAN: Refactor de Excepciones Genéricas en `src/util_bbdd/comparar`

## Objetivo
Refactorizar `src/util_bbdd/comparar/` para reemplazar excepciones genéricas (`ValueError`, `Exception`, `NotImplementedError`) por excepciones específicas y tipadas en la jerarquía `_core/exceptions.py`.

## Scope In

### Nuevas Excepciones a Crear (jerarquía)
```
DatabaseException (existente base)
  ↓
ComparerError ✨ [NEW]
  ├─ SchemaDiffValidationError ✨    — Input validation (dialect, format, paths)
  ├─ MetadataIntrospectionError ✨   — Inspector/dialect failures
  └─ DiffReportGenerationError ✨    — Reporter failures
```

### Archivos a Modificar

| Archivo | Cambios | Tipo |
|---------|---------|------|
| `_core/exceptions.py` | +4 nuevas clases | NEW |
| `comparar/__init__.py` | Importar + exportar excepciones nuevas | UPDATE |
| `comparar/comparator.py` | Import `MetadataIntrospectionError` | UPDATE |
| `reporters/sql_reporter.py` | `ValueError` → `SchemaDiffValidationError` (línea ~252) | REPLACE |
| `reporters/facade.py` | `ValueError` → `SchemaDiffValidationError` (línea ~140) | REPLACE |
| `reporters/word_reporter.py` | `ValueError` → `SchemaDiffValidationError` (línea ~88) | REPLACE |
| `tests/comparar/test_diff_reporters.py` | 6 `pytest.raises(ValueError)` → `SchemaDiffValidationError` | UPDATE |

## Impacto Funcional

- ✅ **Sin cambios en lógica de comparación** — Solo manejo de excepciones
- ⚠️ **BREAKING**: Código capturando `ValueError`/`Exception` debe actualizar
- ✅ Código capturando `DatabaseException` sigue trabajando (herencia)

## Test Strategy

- Actualizar 6 tests que capturen `ValueError` → `SchemaDiffValidationError`
- Todas las excepciones nuevas heredan de `DatabaseException` (LSP)
- Verificación: `pytest` pasa con 1878+ tests

## Riesgos

| Riesgo | Severidad | Mitigación |
|--------|-----------|-----------|
| Código externo captura `ValueError` genéricas | ALTO | Exportar nuevas excepciones; CHANGELOG documenta rotura |
| Pérdida de contexto en stack trace | MEDIO | Usar `raise ... from e` |
| Excepciones exponen datos sensibles | MEDIO | Audit: evitar credenciales en `details` |

## Veredicto
**GO** — Proceder con implementación bajo condiciones aceptadas
