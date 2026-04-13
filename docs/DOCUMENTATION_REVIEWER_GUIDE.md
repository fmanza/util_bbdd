# Guía: Documentation Reviewer - Auditoría de Documentación

## ¿Qué es?

El agente `Documentation Reviewer` audita **toda la documentación** de la aplicación `util_bbdd` en busca de:
- ❌ Ejemplos faltantes o rotos
- ❌ Gaps en guías técnicas
- ❌ Módulos públicos sin docstrings
- ❌ Inconsistencias en referencias o links
- ✅ Mejoras y prioridades de acción

## Cuándo usarlo

| Situación | Usar Documentation Reviewer |
|-----------|-----|
| Preparar release o versión pública | ✅ |
| Onboarding de nuevos developers | ✅ |
| Evaluar madurez de documentación | ✅ |
| Mejorar ejemplos de uso | ✅ |
| Después de refactor arquitectónico | ✅ |
| Validar que no haya broken links | ✅ |

## Cómo invocar

### Opción 1: En Claude Code (Recomendado)

Escribir directamente en el chat:

```markdown
Necesito revisar toda la documentación de util_bbdd.

Usa Documentation Reviewer para:
1. Mapear estado actual (README, guías, ejemplos, docstrings)
2. Identificar ejemplos faltantes por módulo principal
3. Encontrar gaps críticos vs mejoras recomendadas
4. Generar backlog de acciones con prioridades

Alcance: Todos los módulos públicos en src/util_bbdd/
```

> **Nota**: No existe `/documentation-review` como slash command en `.claude/commands/`.
> Invócalo mediante lenguaje natural o desde Copilot Chat con `documentation_review.prompt.md`.

### Opción 2: En Copilot Chat

```
@codebase Necesito una auditoría de documentación completa.

Usa el agente Documentation Reviewer para revisar:
- README.md
- Docstrings en src/util_bbdd/**/*.py
- docs/examples/
- docs/v0.6.7/

Busca ejemplos faltantes, gaps críticos y coherencia.
```

## Ejemplo de salida esperada

```
# Documentation Review: util_bbdd

## Executive Summary
- 45% de módulos públicos tienen docstrings
- 62% de features principales cuentan con ejemplos
- 8 gaps críticos que bloquean onboarding
- 23 mejoras recomendadas para claridad

## Critical Gaps (Nivel 1 - Bloquean uso)

### 1. AsyncDatabaseManager sin ejemplo básico
- **Ubicación**: `src/util_bbdd/managers/async_database_manager.py`
- **Problema**: No existe ejemplo de uso simple de `async_fetch_metadata()`
- **Impacto**: Developers no saben cómo empezar con APIs async
- **Recomendación**: Crear `docs/examples/async_basic_example.py` con:
  ```python
  async def main():
      async with AsyncDatabaseManager(...) as manager:
          schema = await manager.async_fetch_metadata()
  ```

### 2. metadata/ module sin arquitectura clara
- **Ubicación**: `src/util_bbdd/metadata/__init__.py`
- **Problema**: No explain qué es fetcher vs normalizer vs builder
- **Impacto**: developers no entienden flujo de introspección
- **Recomendación**: Agregar docstring a `__init__.py`:
  ```python
  """
  Metadata introspection pipeline:

  1. fetcher: Extract raw metadata from database
  2. normalizer: Normalize across database engines
  3. builder: Build high-level Schema/Table/Column objects
  4. manager: Orchestrate the full pipeline
  """
  ```

### 3. bulk/ migration guide missing
- **Ubicación**: `docs/v0.6.7/` (no existe)
- **Problema**: No hay guía de migración de bulk_crud_py
- **Impacto**: Usuarios no saben usar CRUD masivo desde DataFrames
- **Recomendación**: Crear `docs/v0.6.7/BULK_OPERATIONS_GUIDE.md` con:
  - Conceptos de auditoría CSV
  - Ejemplo: bulk insert, update, delete
  - Errores comunes

## High Priority Improvements (Nivel 2 - Mejoran claridad)

### Examples by Module

| Módulo | Tiene Ejemplo | Estado | Prioridad |
|--------|---------------|--------|-----------|
| `connection` | ✅ | Incompleto (solo sync) | Alta |
| `metadata` | ❌ | Falta | Alta |
| `bulk` | ❌ | Falta | Alta |
| `render` | ✅ | Desactualizado (v0.5) | Media |
| `analysis` | ❌ | Falta | Media |
| `comparar` | ❌ | Falta | Baja |

### Missing docstrings in public APIs

```
src/util_bbdd/managers/__init__.py
  - SyncDatabaseManager: docstring exists ✅
  - AsyncDatabaseManager: docstring missing ❌

src/util_bbdd/metadata/__init__.py
  - MetadataFetcher: docstring exists but incomplete ⚠️
  - SchemaBuilder: Missing return type in __call__ ❌
```

## Recommended Enhancements (Nivel 3)

1. Add performance tips for large databases
2. Add troubleshooting guide for common connection issues
3. Document supported SQL features by motor
4. Add comparison examples: sync vs async patterns

## Examples Inventory

### Existing
```
✅ docs/examples/basic_connection_example.py (v0.6.6)
✅ docs/examples/metadata_explorer_example.py (v0.6.6)
✅ docs/examples/bulk_operations_example.py (v0.6.6, pero uses deprecated API)
✅ docs/examples/rendering_documentation_example.py (v0.6.5, desactualizado)
```

### Missing
```
❌ docs/examples/async_database_manager_example.py
❌ docs/examples/schema_comparison_example.py
❌ docs/examples/custom_render_template_example.py
❌ docs/examples/error_handling_example.py
❌ docs/examples/multi_database_example.py
```

## Documentation Readiness Verdict

**NEAR_READY**

- ⚠️ Bloqueantes: 8 críticos deben cerrarse antes de release
- ⚠️ Coherencia: Links rotos a v0.6.6 en README
- ✅ Arquitectura: Bien documentada en .ai/
- ✅ APIs: Mayormente tipadas

### Next Steps (Ranking)
1. [CRÍTICO] Crear ejemplos faltantes: AsyncManager, bulk, analysis
2. [CRÍTICO] Actualizar metadata/ docstrings con flujo de arquitectura
3. [ALTO] Crear guía de troubleshooting
4. [ALTO] Actualizar links de ejemplos v0.6 → v0.6.7
5. [MEDIO] Agregar performance tips
6. [BAJO] Crear plantilla de custom render
```

## Diferencias con otros agentes

| Agente | Foco | Cuando |
|--------|------|--------|
| **Code Auditor** | Bugs, edge cases, contracts | Después de IMPLEMENT |
| **Documentation Reviewer** ⭐ | Gaps, ejemplos, coherencia docs | Auditoría independiente |
| **Maturity Assessment** | Estructura, APIs, tests, readiness | Evaluación completa |
| **Security Reviewer** | Auth, secrets, logging, entrada | Auditoría de seguridad |

## Checklist: Antes de invocar

- [ ] Tengo claro qué área auditar (todas | README | ejemplos | APIs | guías)
- [ ] Conozco versión actual (`v0.6.7` en este repo)
- [ ] Tengo contexto de audiencia (nuevos developers | releases | mantenedores)

## Archivos contactados

El agente leerá:
- `README.md`
- `docs/**/*.md`
- `docs/examples/**/*.py`
- `src/util_bbdd/**/__init__.py` (docstrings)
- `.ai/architecture.md`
- `.ai/standards.md`
- `.github/instructions/`

## Próximas acciones después del review

1. **Crear issues** en GitHub basadas en hallazgos Nivel 1 y 2
2. **Crear PR** con ejemplos nuevos (una por agrupación temática)
3. **Actualizar docstrings** según recomendaciones
4. **Refrescar links** a versiones anteriores
5. **Validar** con Code Auditor después de cambios

## Feedback loop

Después de cada revisión con Documentation Reviewer:
- Guardar output en `.ai/sessions/documentation_review_YYYY-MM-DD.md`
- Rastrear qué gaps se cerraron en `.github/PROGRESS.md`
- Re-auditar antes de cada release

---

**Última actualización**: 2026-04-13
**Versión**: v0.6.7
**Agente**: Documentation Reviewer (`documentation-reviewer.agent.md`)
