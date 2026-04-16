# AUDIT_PLAN: Evaluación de Riesgos

## Riesgos Funcionales

| Riesgo | Severidad | Impacto | Remediación |
|--------|-----------|--------|-------------|
| Código externo captura `ValueError` o `Exception` genéricas | 🔴 ALTO | Ese código no atrapará nueva excepción | Exportar nuevas excepciones como API pública; CHANGELOG |
| Tests que usan `pytest.raises(ValueError)` fallan | 🟡 MEDIO | CI rota | Actualizar todos los `pytest.raises()` en tests/comparar/ |

## Riesgos Técnicos

| Riesgo | Severidad | Impacto | Remediación |
|--------|-----------|--------|-------------|
| Excepciones pierden contexto de `cause` | 🟡 MEDIO | Stack traces confusos | Usar `raise ... from e` en reemplazos |
| Logging diverge entre módulos | 🟢 BAJO | Inconsistencia visual | Mantener `logger.exception()` en bloques críticos |

## Riesgos de Seguridad

| Riesgo | Severidad | Impacto | Remediación |
|--------|-----------|--------|-------------|
| Excepciones exponen rutas, BD names | 🟡 MEDIO | Information disclosure | Sanitizar `details` en excepciones; maskear paths |

## Simplificaciones Descartadas

- ❌ **NO consolidar** `MetadataIntrospectionError` + `DiffReportGenerationError` → Responsabilidades distintas
- ❌ **NO heredar** directo de `DatabaseException` → `ComparerError` permite captura genérica

## Tipado y Contratos

- ✅ `ComparerError` respeta `DatabaseException` (LSP)
- ✅ Firmas públicas no cambian (métodos públicos mantienen misma interfaz)
- ✅ Tests de contrato (LSP): subclases capturables por `except DatabaseException`

## Veredicto

### 🟢 GO CONDICIONAL

**Condiciones:**
1. ✅ Confirmación de ruptura de compatibilidad (autorizado en request)
2. ✅ Audit de seguridad pre-implementación (campos `details` sanitizados)
3. ✅ Strategy de rollback claro (`git revert` disponible)
4. ✅ Documentación de salida (CHANGELOG.md + docstrings)

**Impacto SOLID:**
- ✅ **SRP**: Cada excepción tiene responsabilidad única
- ✅ **OCP**: Agregar tipo de error → nueva subclase sin editar existentes
- ✅ **LSP**: Todas respetan `DatabaseException`
- ✅ **ISP**: Excepciones compactas
- ✅ **DIP**: Código que captura `DatabaseException` sigue funcionando
