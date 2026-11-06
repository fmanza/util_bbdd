# TRACEABILITY

## Session metadata
- id: 2026-11-06-gaps-g50-g51
- fecha: 2026-11-06
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (U-11.1, U-11.2) + AUDIT_CODE + VERSION (v5.4.0)

## Prompt issued
Ver [00_REQUEST.md](00_REQUEST.md): ola 11 del plan de huecos de util_bbdd_web (U-11.1 y U-11.2), un commit por
fase, MINOR 5.4.0, `manifest.json` v1 legible, T3/T4 verificadas y documentadas, títulos de `pages` en texto plano.

## Context supplied
- util_bbdd_web `.ai/sessions/2026-11-06-gaps-g50-g51/PLAN.md` y `AUDIT_PLAN.md` (plan `c6cb768`, web 1.12.0).
- `docs/plan/UTIL_BBDD_GAPS.md` de la web (G50, G51).
- Código de `doc/infrastructure/renderers/markdown/` y sesión `2026-11-05-doc-markdown`.

## AI output summary
- PLAN y AUDIT_PLAN propios verificando las referencias del plan de la web; ajustes: `mermaid_ref` como parámetro
  nuevo de `mkdocs_yml`, aviso sin `mkdocs.yml`, `index_page_titles` hermana de `index_pages`, títulos desde el valor
  original. Hallazgo T2 (huérfanos al pasar de copia a referencia). GO_CONDICIONAL, aprobado («Adelante»).
- T3/T4 verificados antes de implementar con Zensical 0.0.71 y MkDocs 1.6.1 + Material 9.7.7: build `--strict` sin
  aviso con el fichero ausente; los bundles cargan `mermaid@11` de unpkg si no hay `window.mermaid`.
- U-11.1 `a3025d3c`: `mermaid_js_ref`, validación en `documentation_orchestrator.py`, `publish(keep=…)`, docs y 27
  tests (`test_doc_markdown_mermaid_ref.py`).
- U-11.2 `5b443659`: `manifest.json` v2 con `pages` (`PageEntry`, `ordered_pages`, `plain_text`,
  `index_page_titles`), ADR-006 enmendado, docs y 7 tests (`test_doc_markdown_pages.py`).
- AUDIT_CODE: APROBADO ([AUDIT_CODE.md](AUDIT_CODE.md)).
- VERSION: release v5.4.0, wheel y `.sha256` en `dist/`, tag anotado local `v5.4.0`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN / AUDIT_PLAN | `.ai/sessions/2026-11-06-gaps-g50-g51/` | aprobados |
| U-11.1 | `a3025d3c` | completado |
| U-11.2 | `5b443659` | completado |
| AUDIT_CODE | `AUDIT_CODE.md` | APROBADO |
| Release | `release: v5.4.0` + tag local | pendiente de push (usuario) |

## Traspaso a util_bbdd_web (W-11)

- Pin 5.4.0 con el wheel y su `.sha256` de la release (W-11.0).
- G50: pasar `imprimir["markdown"]["mermaid_js_ref"] = "assets/javascripts/mermaid.min.js"` en lugar de
  `mermaid_js`. util_bbdd no copia nada ni comprueba la ruta; `mkdocs.yml` lleva `extra_javascript` con esa ruta y
  `theme.font: false`. Si el ZIP sale sin el fichero, el sitio carga `mermaid@11` de unpkg (sin Internet, sin
  diagramas) y el build no avisa: es lo que cubre la cabecera `X-UBW-Warning` del plan.
- G51: `manifest.json` → `format_version` 2, `pages`: `[{path, title, section, role, letter?, id?, kind?}]`. Las
  claves opcionales **no aparecen** cuando no aplican (no van como `null`): el modelo Pydantic de la web debe tenerlas
  como opcionales con defecto. `section` incluye `database`; `role` `page` para `database/*`, `traceability.md` y
  `changes.md`. Los *slugs* siguen siendo los de 5.3.0 (`ACM_AGENDA` → `tables/acm-agenda.md`).

## Directrices para Futuras IAs
- **[doc/markdown]**: `manifest.json` es contrato versionado (ADR-006, enmienda 2026-11-06); `catalog.json` sigue
  siendo solo de objetos. Una página nueva debe anotarse en `pages` donde se escribe (`PageEntry`) o
  `test_pages_list_every_markdown_page_once` falla.
- **[doc/markdown]**: los títulos de `pages` se calculan desde el valor original con `plain_text`, nunca desescapando
  el H1; si cambia un H1, cambia también la cadena de su `PageEntry` (lo vigila `test_titles_are_plain_text_and_match_the_h1`).
- **[doc/markdown]**: `StagedWriter.publish(keep=…)` excluye rutas de la limpieza de huérfanos; úsalo para ficheros
  que una generación anterior escribió y la nueva solo referencia.
- **[doc/markdown]**: con `extra_javascript` local ausente, `zensical build --strict` y `mkdocs build --strict` no
  avisan; Zensical 0.0.71 y Material 9.7.7 recurren a `unpkg.com/mermaid@11` si no hay `window.mermaid`.
- **[herramientas]**: en este entorno, un heredoc de bash con texto largo y comillas mezcladas puede fallar
  («unexpected EOF»); escribir el script con Write en el scratchpad y ejecutarlo con `python -I`.

## Veredicto final
Veredicto: CLOSED (v5.4.0)
Pendientes al cierre:
- Push de `develop`, del tag `v5.4.0` y ff de `main`; release en GitHub con el wheel y el `.sha256` (usuario,
  release_guide §6–7).
- W-11 en util_bbdd_web.
