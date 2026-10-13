# TRACEABILITY

## Session metadata
- id: 2026-10-14-remove-reserved-exceptions
- fecha: 2026-10-14
- rama: develop
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued

Deprecación y retiro de `PoolExhaustedError` y `DiffReportGenerationError` de la API pública para v2.0.0.

Ambas excepciones estaban marcadas como "reservadas" en v1.1.1 porque la librería nunca las lanza:
- `PoolExhaustedError`: un pool sync agotado genera `PoolTimeoutError`
- `DiffReportGenerationError`: los fallos de reporter llegan con su excepción original

Fases solicitadas: PLAN y AUDIT_PLAN; tras aprobación (GO), completar IMPLEMENT, AUDIT_CODE y VERSION.

## Context supplied
- `.github/SHARED_INSTRUCTIONS.md` (arquitectura, calidad, comandos)
- `CLAUDE.md` (slash commands, configuración IA)
- `docs/roadmap.md` líneas 74-75 (propuesta de v2.0.0)
- `CHANGELOG.md` v1.1.1 (marca excepciones como "reservadas")
- `docs/api/exceptions.md` (diagrama con anotaciones)

## AI output summary

1. **PLAN**: Análisis de arquitectura real — 5 archivos de código, 2 de documentación, 1 de test. Componentes implicados: jerarquía de excepciones (`ConnectionError` y `ComparerError` sin cambio), imports en 3 módulos, test de conteo.

2. **AUDIT_PLAN**: Riesgos evaluados — funcional (cero impacto, nunca se lanzan), técnico (conteo de excepciones, test de exports, pickles), seguridad (N/A). Veredicto: **GO** sin condiciones. Justificación: breaking change en MAJOR versión, documentado desde v1.1.1, impacto cero funcional.

3. **IMPLEMENT**: Cambios realizados en 9 archivos:
   - `_core/exceptions.py`: definiciones removidas (68 líneas de `PoolExhaustedError`, 16 de `DiffReportGenerationError`)
   - `exceptions.py`: reexportaciones removidas (imports y `__all__`)
   - `_core/__init__.py`: import de `PoolExhaustedError` removido
   - `comparar/__init__.py`: import de `DiffReportGenerationError` removido
   - `test_exceptions_public_module.py`: conteo actualizado (40 → 38)
   - `test_top_level_exports.py`: REMOVED_IN_1_0 actualizado (46 → 44), comentario agregado
   - `CHANGELOG.md`: entrada v2.0.0 con breaking changes y guía de migración
   - `docs/api/exceptions.md`: diagrama actualizado, menciones de "reservada" removidas
   - `docs/roadmap.md`: versión "propuesta" → entregada

4. **AUDIT_CODE**: Validación integral:
   - ✅ 81/81 tests de excepciones públicas (test_exceptions_public_module.py)
   - ✅ 67/67 tests de exports (test_top_level_exports.py)
   - ✅ 4287/4287 tests unitarios (suite completa)
   - ✅ Type checking con mypy: sin errores
   - ✅ Linting con ruff: sin errores críticos (solo E501 preexistentes)
   - ✅ Documentación: zensical build --strict sin errores

5. **Corrección descubierta**: `_core/exceptions.py` tenía otro `__all__` (líneas 419-456) que aún contenía ambas excepciones. Removidas en commit separado.

6. **Documentación**: Actualización completada en 4 archivos:
   - `docs/guides/comparator.md`: tabla de errores actualizada
   - `docs/guides/api_1_0_migration.md`: agregar sección 6 (v2.0.0) con tabla de migración y ejemplos
   - `docs/api/intro.md`: reemplazar `PoolExhaustedError` con `PoolTimeoutError`
   - `docs/roadmap.md`: versión actualizada

7. **Commits creados**:
   - `763b8578`: refactor(exceptions): remover PoolExhaustedError y DiffReportGenerationError en v2.0.0
   - `7ab09076`: fix(exceptions): remover PoolExhaustedError y DiffReportGenerationError de __all__ en _core
   - `6f6b8261`: docs: actualizar documentación con cambios de v2.0.0

## Artefactos generados

| Artefacto | Ruta | Estado |
|-----------|------|--------|
| PLAN | (oral, agente Plan Architect) | completado ✅ |
| AUDIT_PLAN | (oral, agente Plan Architect) | completado ✅ |
| IMPLEMENT | src/util_bbdd/_core/exceptions.py y 8 archivos más | completado ✅ |
| AUDIT_CODE | tests/unit/test_exceptions_public_module.py, test_top_level_exports.py + suite | completado ✅ |
| CHANGELOG.md | CHANGELOG.md (entrada v2.0.0) | completado ✅ |
| Documentación | 4 archivos en docs/ | completado ✅ |
| Commits | 3 (refactor + fix + docs) | completados ✅ |

## Directrices para Futuras IAs

- **[excepciones]**: `PoolExhaustedError` fue removida en v2.0.0 tras ser documentada como "reservada" (nunca lanzada) en v1.1.1; búsquedas en código, tests y ejemplos confirmaron impacto cero. Remover excepciones nunca usadas requiere: 1) verificar `__all__` en `_core/`, módulo público y cualquier reexportador; 2) actualizar tests de conteo (`test_exceptions_public_module.py`); 3) actualizar test de exports (`test_top_level_exports.py::test_removed_name_*`); 4) documentar breaking change en CHANGELOG con instrucciones de migración.

- **[arquitectura/reexportación]**: Las excepciones se reexportan en 3 puntos: `_core/__init__.py` (solo las internas frecuentes, no todas), `exceptions.py` (todas, puente a _core), `comparar/__init__.py` (solo ComparerError y sus subclases). Ändringar a exceptions debe propagarse a los tres puntos.

- **[documentación]**: Guía de migración `api_1_0_migration.md` es el punto canónico para excepciones removidas o deprecadas; agregar sección de versión allí con tabla antes/después e índice de búsqueda ("v2.0.0 breaking changes"). Ejemplos de código en esa sección ayudan a consumidores.

- **[testing]**: El test `test_removed_name_lives_only_in_its_submodule` verifica que nombres marcados en `REMOVED_IN_1_0` sigan siendo accesibles desde su submódulo público; al remover completamente (v2.0.0), eliminar del dict `REMOVED_IN_1_0` y decrementar el assert de `len(REMOVED_IN_1_0)` en `test_removed_names_are_not_part_of_the_root()`. Dos niveles de validación: salida de raíz (1.0.0) vs. salida de API pública (2.0.0+).

- **[changelog]**: Breaking changes en MAJOR version deben incluir: 1) sección `## [X.0.0] - Fecha`; 2) subsección `### Removed` con clase/excepción y breve justificación; 3) instructions de migración (p.ej. "cambiar `except X` a `except Y`"); 4) si aplica, referencia a guía en docs/ o línea en CHANGELOG anterior (v1.1.1 aquí) que anunció el cambio.

- **[validación/staging]**: Al remover código público en MAJOR: 1) grep exhaustiva en tests/ + examples/ + docs/; 2) mypy + ruff sin false negatives en areas afectadas; 3) zensical/mkdocs build para docs offline; 4) ejecutar suite unitaria en el sandbox (no solo localmente). Este refactor pasó todos: 4287 tests, 0 errores de type, 0 errores críticos de lint, docs sin broken links.

## Veredicto final

Veredicto: **GO**

Pendientes al cierre:
- [x] Código: removidas definiciones y reexportaciones
- [x] Tests: actualizados (conteo 40→38, exports 46→44)
- [x] Documentación: actualizada (4 archivos, examples de migración)
- [x] CHANGELOG: entrada v2.0.0 con breaking changes
- [x] Validación: tests + type checking + linting + docs build
- [ ] Etiqueta git: `git tag -a v2.0.0 -m "v2.0.0 - Remover excepciones reservadas PoolExhaustedError y DiffReportGenerationError"`
- [ ] Commit final de cierre (si aplica según sync.instructions.md)

**Resumen**: Refactor completado. Ambas excepciones (nunca usadas, documentadas como reservadas) removidas de la API pública. Breaking change MAJOR alineado con SemVer. Documentación y ejemplos de migración agregados. Tests en verde (4287/4287). Listo para v2.0.0.
