# TRACEABILITY

## Session metadata
- id: 2026-05-22c-hotfix-package-data-templates
- fecha: 2026-05-22
- rama: develop
- skill: hotfix
- fase: FIX + AUDIT_CODE

## Prompt issued
Al usar este proyecto en otros proyectos no se descarga
`src\util_bbdd\comparar\reporters\templates\diff_report.html.j2` y se tiene que descargar.

## Context supplied
- `pyproject.toml` — sección `[tool.setuptools.package-data]`
- `src/util_bbdd/comparar/reporters/templates/diff_report.html.j2` — fichero afectado

## AI output summary
- RCA: La sección `[tool.setuptools.package-data]` en `pyproject.toml` incluía patrones `doc/templates/**/*.j2` y `doc/data/**/*` pero omitía `comparar/reporters/templates/**/*.j2`. Al empaquetar, setuptools no incluía el template HTML Jinja2 del módulo comparar.
- FIX: Añadida entrada `"comparar/reporters/templates/**/*.j2"` al listado `util_bbdd` en `[tool.setuptools.package-data]`.
- AUDIT_CODE: Cambio mínimo, sin riesgo funcional; el template queda incluido en la distribución wheel/sdist.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| package-data comparar templates | `pyproject.toml` L76-83 | completado |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. Cambio de una línea en pyproject.toml; requiere nuevo build para que la distribución lo recoja.
