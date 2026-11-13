# TRACEABILITY

## Session metadata
- id: 2026-11-13c-mermaid-nombre-tipo
- fecha: 2026-11-13
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
«Los diagramas en Mermaid de la base de datos documentada sale primero la columna el tipo y luego el Campo, se quiere
al revés. PLAN y AUDIT_PLAN» → «Adelante» (D1–D4 con las opciones recomendadas).

## Context supplied
- `src/util_bbdd/analysis/mermaid_er.py`, `_core/mermaid.py`, `graphviz_ext.py`, leyenda de `_site_pages.py`, tests de
  `test_analysis_mermaid_er.py`; util_bbdd_web (`test_documentation_markdown.py`).

## AI output summary
- PLAN + AUDIT_PLAN (`PLAN_AUDIT_PLAN.md`): Mermaid dibuja los atributos en el orden del texto y no los reordena;
  Graphviz ya pone el nombre primero; prueba previa en Chromium con Mermaid 12.3.0.
- D4 cumplido antes de tocar el código: `nombre tipo` dibujado sin errores con Mermaid 11.17.2 (y 12.3.0), con tipos
  con paréntesis o corchetes, prefijos `c_`/`t_`, `PK/FK/UK` y comentario.
- `46e7ac9c`: `MermaidRelationshipGraph(attribute_order="name_type" | "type_name")`, `name_type` por defecto;
  `type_name` reproduce el texto anterior byte a byte; `ValueError` si no es válido; fila nueva en la leyenda de la
  portada Markdown. Tests: orden nuevo, anterior, inválido, misma longitud (presupuesto `max_chars`), e2e de página y
  leyenda. R5 descartado: el `hash` del front matter es del registro del objeto, no de los diagramas.
- Salida Markdown generada: `zensical build --strict` limpio y dibujo sin red con Mermaid 12.3.0 y 11.17.2
  (`cliente_id | INTEGER | FK`).
- VERSION 5.8.0: campos de `sync.instructions.md` § 4, 19 pines `@v5.8.0`, CHANGELOG, estado e índices.

## Pruebas
- pytest local: 7156 passed, 619 skipped; venv limpio `.[dev-full]`: 7155 passed, 619 skipped.
- ruff, `ruff format`, mypy (375) limpios; `zensical build --strict` sin incidencias; `python -m build` 5.8.0.

## Directrices para Futuras IAs
- **[analysis]**: el orden de las columnas de `erDiagram` lo decide `MermaidRelationshipGraph._attribute()`
  (`attribute_order`); Mermaid no tiene opción para reordenar: dibuja en el orden del texto.
- **[analysis]**: `normalize_er_name` produce un subconjunto de los caracteres de `normalize_er_type`; por eso los dos
  tokens se pueden intercambiar sin romper la gramática (verificado con Mermaid 11.17.2 y 12.3.0).
- **[doc]**: el texto `erDiagram` de la documentación Markdown ya no sigue la semántica canónica (primer token = tipo):
  la leyenda de la portada lo explica; los datos exactos de cada columna están en el front matter y en `catalog.json`.
- **[pruebas]**: para validar sintaxis de Mermaid sin navegador abierto: `mermaid.render()` en Chromium (Playwright)
  con el `mermaid.min.js` de la versión a probar (script `mermaid_swap.py` de la sesión, en el scratchpad).

## Veredicto final
Veredicto: CLOSED — v5.8.0 (commit y tag anotado `v5.8.0` en local).
Pendientes al cierre:
- Publicación (push de `develop` y del tag, ff de `main`, release con wheel y `.sha256`) si el usuario la pide.
