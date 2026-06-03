# TRACEABILITY

## Session metadata
- id: 2026-06-03-docs-standard-v2
- fecha: 2026-06-03
- rama: develop
- skill: refactor / new_feature (docs)
- fase: PROMPT → PLAN + AUDIT_PLAN → IMPLEMENT (FASE 0–8) + AUTODOC FIXES

## Prompt issued
1. Generar prompt para homogenizar documentación MkDocs con nuevo estándar de 4 arquetipos estructurados.
2. Propuesta de mejoras: soporte Java, arquetipos según estándares de industria, enlace técnica↔ejemplos obligatorio, 7 secciones nav exactas.
3. PLAN y AUDIT_PLAN para ejecutar la propuesta — C1: posponer §4 Criterios de Aceptación hasta validación QA; C6: verificar anchors antes de renumeración.
4. IMPLEMENT: ejecutar el plan con las condiciones C1 y C6 resueltas.
5. Revisar por qué Autodoc (mkdocstrings) no muestra todo el API de Bulk Operations.
6. Revisar por qué Autodoc no muestra todo el API del módulo dump.
7. Actualizar .ai/sessions y preparar mensaje para subir código a GitHub.

## Context supplied
- `mkdocs.yml` — configuración del generador estático y nav actual
- `.github/instructions/docs.instructions.md` — instrucciones de documentación activas
- `.github/DOCUMENTATION_STANDARD.md` — estándar actual
- `.github/prompts/functional_doc.prompt.md`, `technical_doc.prompt.md` — prompts activos
- `docs/functional/`, `docs/api/`, `docs/examples/`, `docs/` (guías) — documentación a homogenizar
- `src/util_bbdd/bulk/crud.py`, `src/util_bbdd/dump/__init__.py` — código fuente para diagnóstico autodoc

## AI output summary

### Iteración 1 — Prompt de homogenización (estándar de 4 arquetipos v1)
- Generado prompt completo con 4 arquetipos × 4 secciones, 6 fases de ejecución y reglas de snippets/Mermaid.

### Iteración 2 — PLAN + AUDIT_PLAN
- Inventario exacto: 19 functional, 24 api, 18 examples, 18 guías, 1 ADR, 337 .py, 0 Java, 0 TypeScript.
- PLAN estructurado en 8 fases con estimaciones de esfuerzo.
- AUDIT_PLAN con 7 hallazgos: C1 bloqueante (criterios QA), C2 alto (correspondencia incompleta), C3 alcance, C4 API_REFERENCE, C5 roadmap, C6 anchors, C7 lenguaje Python-only.
- Veredicto: APROBADO CON CONDICIONES.

### Iteración 3 — IMPLEMENT (Estándar v2: 5 arquetipos × 5 secciones)
**FASE 0:** Detección de lenguaje → Python 100% (337 .py, 0 Java/TS). Build inicial: 99 warnings (4 guías IA con links a .github/).

**FASE 1 — Instrucciones IA** (7 archivos + 1 nuevo):
- `docs.instructions.md`: TL;DR + Arquetipo 1 (§4 Criterios pendiente QA + §5 Glosario), Arquetipo 2 (§5 Ejemplos Relacionados, directiva autodoc multi-lenguaje), Arquetipo 3 (§1 Objetivo + §5 Variantes), Arquetipo 4 (§5 Referencias), Arquetipo 5 (nuevo ADR), tabla lenguajes + regla alias autodoc.
- `DOCUMENTATION_STANDARD.md`: §3.1–§3.5 (5 arquetipos) + §3.6 multi-lenguaje + criterios de completitud actualizados.
- `functional_doc.prompt.md`, `technical_doc.prompt.md`, `guide_doc.prompt.md`, `example_doc.prompt.md`: actualizados a 5 secciones.
- `architecture_doc.prompt.md`: creado (Arquetipo 5 ADR).
- Build: 0 errores, 0 warnings.

**FASE 2 — mkdocs.yml** (7 secciones exactas):
- Nav consolidado de 9 a 7 secciones top-level.
- "Roadmap & Planificación" + "Versiones Históricas" → bajo "Arquitectura".
- `API_REFERENCE.md` reemplazado por `api/intro.md` en nav + añadido a `exclude_docs`.
- Creado `docs/api/intro.md` con índice de clases y tabla de importaciones canónicas.
- Links rotos a API_REFERENCE.md corregidos en `index.md`, `legacy-versions.md`, `api/index.md`.
- Build: 0 errores, 0 warnings.

**FASE 3 — docs/api/ → §5 Ejemplos Relacionados** (24 archivos):
- 24 archivos manuales actualizados: `## 5. Ejemplos Relacionados` al final.
- 4 archivos sin ejemplo correspondiente usan admonition `!!! info "Ejemplo en preparación"`.
- Build: 0 errores, 0 warnings.

**FASE 4 — docs/examples/ → §5 Referencias Relacionadas** (18 archivos):
- 18 archivos actualizados con enlaces bidireccionales a functional/ y api/.
- Build: 0 errores, 0 warnings.

**FASE 5 — POSPUESTA** (criterios de aceptación — pendiente validación QA).

**FASE 6 — docs/ guías → §1 Objetivo + renumeración** (13 archivos):
- Script Python procesó 13 guías: insertó `## 1. Objetivo`, renumeró §1→§2, §2→§3, §3→§4, §4→§5 Variantes.
- Grep de anchors: 0 referencias rotas.
- Build: 0 errores, 0 warnings.

**FASE 7 — docs/adr/ → Arquetipo 5**:
- `ADR-001-STRUCTURE-REFACTORING.md` reestructurado de 12 secciones libres → 5 secciones Arquetipo 5.
- Creado `docs/adr/ADR-TEMPLATE.md` con plantilla completa.
- `v0.8.0/PLAN_*.md` marcado `<!-- arquetipo: informativo-libre -->`.
- `ADR-TEMPLATE.md` añadido a nav bajo Arquitectura.
- Build: 0 errores, 0 warnings.

**FASE 8 — Validación final:**
- `mkdocs build --strict`: 0 errores, 0 warnings.
- Nav: 7 secciones top-level verificadas.
- 24 api + 18 examples + 13 guías + 1 adr verificados con sus nuevas secciones.

### Iteración 4 — Corrección autodoc Bulk Operations
- Diagnóstico: `docs/api/bulk.md` usaba `::: util_bbdd.bulk.crud.bulk_crud` (alias variable `bulk_crud = BulkCrud`). mkdocstrings no expande clases desde aliases → API incompleta.
- Fix: cambiado a `::: util_bbdd.bulk.crud.BulkCrud`.
- Gap secundario: `ParallelBulkLoader`, `AuditManager`, `AuditTransaction` no tenían directivas — añadidas.
- Regla documentada en `docs.instructions.md`: checklist de 5 puntos + señales de alias incorrecto.
- Build: 0 errores, 0 warnings.

### Iteración 5 — Corrección autodoc módulo Dump
- Diagnóstico: módulo dump sin ningún archivo autodoc en sección Autodoc de mkdocs.yml. `api/dump.md` y `api/dump-reporter.md` son manuales, no autodoc.
- 11 clases en `__all__` sin cobertura autodoc: `DumpOrchestrator`, `DumpConfig`, `DumpResult`, `DumpReporter`, `ConstraintManager`, `ConstraintResult`, `IndexManager`, `IndexActionResult`, `DumpAuditSummary`, `TableDumpResult`, `BulkInserter`.
- Creado `docs/api/dump-autodoc.md` con directivas `:::` para las 11 clases.
- `PKSyncResult` excluido (re-export de `bulk._models`, ya cubierto en `bulk.md`).
- Añadida entrada `Dump: api/dump-autodoc.md` en sección `Autodoc (mkdocstrings)` de `mkdocs.yml`.
- Regla de cobertura documentada en `docs.instructions.md`: patrón `[modulo].md` manual + `[modulo]-autodoc.md` autodoc, checklist de detección.
- Build: 0 errores, 0 warnings.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Instrucciones IA actualizadas | `.github/instructions/docs.instructions.md` | completado |
| Estándar documental | `.github/DOCUMENTATION_STANDARD.md` | completado |
| Prompts funcional/técnico/guía/ejemplo | `.github/prompts/*.prompt.md` | completado |
| Nuevo prompt ADR | `.github/prompts/architecture_doc.prompt.md` | creado |
| Nav 7 secciones | `mkdocs.yml` | completado |
| Índice Referencia Técnica | `docs/api/intro.md` | creado |
| §5 en 24 docs/api/ | `docs/api/*.md` | completado |
| §5 en 18 docs/examples/ | `docs/examples/*.md` | completado |
| §1+§5 en 13 guías | `docs/*.md` | completado |
| ADR restructurado | `docs/adr/ADR-001-STRUCTURE-REFACTORING.md` | completado |
| Plantilla ADR | `docs/adr/ADR-TEMPLATE.md` | creado |
| 4 guías IA movidas de examples/ a docs/ | `docs/claude_code_guide.md`, `docs/codex_guide.md`, `docs/doc_generation_vscode_guide.md`, `docs/github_copilot_guide.md` | creado |
| Autodoc Bulk corregido | `docs/api/bulk.md` | completado |
| Autodoc Dump creado | `docs/api/dump-autodoc.md` | creado |
| 7 .py de ejemplos creados | `docs/examples/migrate-*.py`, `docs/examples/example-connect-introspect.py`, `docs/examples/query_execution_example.py`, `docs/examples/dump_data_export.py` | creado |

## Directrices para Futuras IAs

**[autodoc alias]**: `mkdocstrings` NO expande miembros de clase cuando la directiva `:::` apunta a un alias de variable (`alias = Clase`). Siempre usar el nombre real de la clase definida con `class NombreClase:`. Señal: sección autodoc vacía o sin métodos a pesar de que el código tiene docstrings.

**[autodoc cobertura]**: Cuando se crea un módulo nuevo con `__all__`, crear también su archivo autodoc `docs/api/[modulo]-autodoc.md` y añadirlo a la sección `Autodoc (mkdocstrings)` de `mkdocs.yml`. Sin este archivo, los docstrings del código nunca se renderizan aunque exista documentación manual en `docs/api/[modulo].md`.

**[criterios aceptación]**: La sección `## 4. Criterios de Aceptación` del Arquetipo 1 está definida en el estándar pero PENDIENTE de validación QA. No rellenar con contenido derivado automáticamente hasta que el equipo QA valide. El placeholder actual es: `*Pendiente de definición con el equipo QA.*`

**[nav 7 secciones]**: La nav de MkDocs tiene exactamente 7 secciones top-level: Inicio, Instalación, Documentación Funcional, Referencia Técnica, Guías, Ejemplos, Arquitectura. No añadir más secciones top-level.

**[PKSyncResult re-export]**: `PKSyncResult` vive en `util_bbdd.bulk._models` y se re-exporta en `util_bbdd.dump`. Está cubierto en `docs/api/bulk.md`. No duplicar en `docs/api/dump-autodoc.md`.

**[FASE 5 pendiente]**: No rellenar `## 4. Criterios de Aceptación` en `docs/functional/*.md` hasta sesión específica con QA. Actualmente contiene placeholder.

## Veredicto final
CLOSED — `mkdocs build --strict` 0 errores/0 warnings. Estándar v2 implementado: 5 arquetipos × 5 secciones, 7 secciones nav, enlace bidireccional api↔examples, autodoc Bulk y Dump corregidos.
