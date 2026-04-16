# TRACEABILITY — 2026-04-16

## Resumen de sesión

| Campo | Valor |
|-------|-------|
| Fecha | 2026-04-16 |
| Rama | develop |
| Skill | new_feature |
| Estado | CLOSED |

## Objetivo

Refactorizar el bloque "Diagrama de diferencias (tablas)" del reporte HTML de `SchemaDiffReporter` para mostrar una interfaz tabbed interactiva (Añadidas / Modificadas / Eliminadas) con bloques Mermaid paginados de máx. 9 tablas, renderizado lazy y UX accesible.

## Archivos modificados

| Archivo | Tipo de cambio |
|---------|---------------|
| `src/util_bbdd/comparar/reporters/templates/diff_report.html.j2` | Refactor HTML/CSS/JS (sección Mermaid + scripts) |

## Decisiones técnicas

| ID | Decisión | Alternativas descartadas |
|----|----------|--------------------------|
| D1 | Mermaid `startOnLoad: false` + `mermaid.run({nodes})` lazy | `startOnLoad:true` con todos los diagramas visibles inicialmente (flash de contenido + carga innecesaria) |
| D2 | CDN fijado a `mermaid@10` | CDN sin pin (riesgo de break por cambio de API en v11+) |
| D3 | Paginación y filtrado por categoria 100% en Jinja2 (`batch(9)`) | Pre-cálculo en Python en `_build_context` (innecesario, Jinja2 es suficiente) |
| D4 | `renderedIds: Set<string>` para evitar re-renders | Comprobar `data-processed` de Mermaid (atributo interno, no garantizado entre versiones) |
| D5 | Orden de tabs: Añadidas → Modificadas → Eliminadas | Por volumen de tablas (más complejo, orden predecible preferido) |
| D6 | No introducir D3.js ni dependencias nuevas | D3.js (excesivo para un diagrama de nombres de tabla) |

## Tests

- Suite completa: 1878 passed, 1 skipped (sin regresiones)
- Render de prueba: caso vacío + 44 tablas (25 added, 12 modified, 7 removed) — 15/15 checks HTML pasan

## Veredicto final

**PASS** — Implementación completa, suite verde, cero regresiones.
