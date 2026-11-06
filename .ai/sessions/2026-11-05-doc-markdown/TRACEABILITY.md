# TRACEABILITY

## Session metadata
- id: 2026-11-05-doc-markdown
- fecha: 2026-11-05 – 2026-11-06
- rama: develop
- skill: new_feature (grupos A–F), con dos `fix(analysis)` y un `fix(comparar)` dentro de la sesión
- fase: PLAN + AUDIT_PLAN (general y por grupo) + SPIKE_C3 + IMPLEMENT + AUDIT_CODE por grupo; VERSION con
  `/version-closure`

## Prompt issued

Prompt de `.github/prompts/doc_markdown_feature.prompt.md`. Pedía:

- documentación Markdown en `doc/` con las reglas de Word;
- opciones para que una IA la trace con el código y los documentos;
- diagramas ER en Mermaid y una decisión sobre la profundidad;
- paginación para más de 500 tablas;
- integración con util_bbdd_web y con Zensical/MkDocs;
- descarga y versionado.

## Context supplied

- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`, `.github/prompts/new_feature.prompt.md` y
  `.github/DOCUMENTATION_STANDARD.md`.
- Código de `doc/`, `analysis/`, `comparar/` y `metadata/model.py`, y la web (`integrations/util_bbdd/documentation.py`,
  `api/v1/runs.py`, `domain/runs/diff.py`).
- Documentación de Zensical (diagramas) y de Mermaid (`erDiagram`, 12.3); bundle de Zensical 0.0.71.

## AI output summary

- PLAN/AUDIT_PLAN general (`GO_CONDICIONAL`). Decisiones del usuario:
  - un fichero por objeto;
  - profundidad variable con tope 2 y aviso;
  - todo lo de IA en el MVP;
  - `CHANGES.md` en el MVP;
  - TOML/JSON por extensión;
  - sin ZIP en la librería;
  - lado padre `|o`.
- SPIKE_C3: `erDiagram` validado con Mermaid 11.17.2 y 12.2.0 y con Zensical en Chromium (Playwright). Escape por
  entidades, reservados `PK`/`FK`/`UK`, guarda de 40 entidades y riesgo de Mermaid desde unpkg.
- Grupo A (`fa6af78c`): `_core/mermaid.py`, recorrido estable, cardinalidad en la base y `MermaidRelationshipGraph`.
  `efb40252` `fix(analysis)`: cardinalidad con todas las columnas de la FK.
- Grupo B (`72a30117`): renderer Markdown (páginas, slugs, escape, front matter, índices, staging, `manifest.json`).
- Grupo C (`8c629287`): `catalog.json` (ADR-006 aceptado), `llms*.txt`, `mkdocs.yml` con `nav` corta, `mermaid_js`
  (verificado sin red) y limpieza que respeta los ficheros editados.
- Grupo D (`db1e6b7b`): mapa de trazabilidad (TOML/JSON, estricto, por columna) y `traceability.md`.
- E0 (`98248a46`) `fix(comparar)`: escape de *code spans* y HTML en el informe Markdown de comparación.
- Grupo E (`b2128968`): `changes.md` / `changes.json` (`SchemaDiff`) desde `previous`, sin conexión.
- `9e1838bc` `fix(analysis)`: `columns.mode` de Mermaid con la misma política que Graphviz y `show_columns`.
- Grupo F: documentación técnica, funcional, guía, ejemplo ejecutable, `troubleshooting`, `SHARED_INSTRUCTIONS`,
  `docs/index.md`, `WEB_HANDOFF.md` y este fichero.
- Suite completa en cada grupo (la última, 7061 passed y 618 skipped, más los tests de F); `zensical build --strict`
  limpio.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Prompt | `.github/prompts/doc_markdown_feature.prompt.md` | emitido |
| PLAN / AUDIT_PLAN generales | `PLAN.md`, `AUDIT_PLAN.md` | emitidos |
| Spikes | `SPIKE_C3.md` + `spike_c3/`, `cc2_mermaid_local/` | completados |
| PLAN y AUDIT_CODE por grupo | `PLAN_GRUPO_{A..F}.md`, `AUDIT_CODE_GRUPO_{A..E}.md` | completados |
| Código | `src/util_bbdd/_core/{mermaid,markdown}.py`, `analysis/mermaid_er.py`, `doc/infrastructure/renderers/markdown/` | completado |
| ADR | `docs/adr/ADR-006-catalogo-documentacion-markdown.md` | ACEPTADO |
| Documentación | `docs/api/database_documentation.md`, `docs/api/analysis*.md`, `docs/functional/*`, `docs/guides/markdown_documentation_guide.md`, `docs/examples/markdown_documentation.{py,md}` | completado |
| Traspaso web | `WEB_HANDOFF.md` | emitido |

## Directrices para Futuras IAs

- **[doc/markdown]**: el renderer vive en `doc/infrastructure/renderers/markdown/`, un módulo por responsabilidad:
  - `_text.py`: escape;
  - `_slugs.py`: nombres de fichero;
  - `_pages.py` y `_site_pages.py`: páginas;
  - `_front_matter.py`: registros (`id`/`hash` comunes con `catalog.json`);
  - `_catalog.py`, `_site.py`, `_trace.py`, `_changes.py`;
  - `_writer.py`: staging, manifiesto y limpieza.
- **[doc/markdown]**: `hash` de un objeto = sha256 del registro **sin** `trace` ni `path`. La traza se añade después a
  propósito, para que no marque cambios en `changes.md`.
- **[doc/markdown]**: la limpieza al regenerar solo borra lo que lista el `manifest.json` anterior (de formato
  `util_bbdd.doc.markdown`), que ya no se genera y cuyo hash sigue igual. Nunca se borra nada fuera de la carpeta.
- **[doc/markdown]**: `previous` puede ser la misma carpeta que se regenera. El catálogo anterior se lee antes de
  publicar (test `test_previous_can_be_the_folder_being_regenerated`).
- **[catalog.json]**: contrato público ADR-006. Añadir campos opcionales no sube `format_version`; quitar o renombrar
  sí, y obliga a leer las versiones anteriores en `_changes.load_previous`.
- **[_core]**: `_core/mermaid.py` (escape de flowchart G46, escape ER por entidades y normalización) y
  `_core/markdown.py` (`code_span`, `escape_html`) son el punto común de `analysis`, `comparar` y `doc`. No dupliques
  escapes en los módulos.
- **[analysis]**: `columns.mode` significa lo mismo en Graphviz y Mermaid:
  - `relations`: solo las columnas relacionadas;
  - `compact`: esas primero y después el resto;
  - `all`: todas.

  Para no mostrar columnas: `show_columns=False`.
- **[analysis]**: la cardinalidad (`DatabaseRelationshipGraphBase._determine_cardinality`) usa todas las columnas de
  la FK. Devuelve `1:1` o `1:N`; ya no `M:N` ni `N:1` (la leyenda perdió el marcador «M»).
- **[analysis]**: `_traverse_levels` y `_collect_next_level_tables` recorren `sorted(frontier)`. No vuelvas a iterar
  conjuntos donde importe el orden de salida (G47, C1).
- **[Mermaid]**: en `erDiagram`, un `%` o `\` suelto en un alias rompe el parser. Usa `escape_mermaid_er_text`
  (códigos `#37;`…), no `escape_mermaid_label`. `PK`, `FK` y `UK` no valen como tipo ni como nombre de atributo.
  `maxEdges` no limita los ER; el límite real es el tiempo de dibujo.
- **[Zensical]**: la 0.0.71 carga `mermaid@11` de unpkg solo si `window.mermaid` no existe. Un `extra_javascript`
  local lo evita (verificado con Playwright sin red). El tema pide Google Fonts salvo `theme.font: false`.
- **[herramientas]**: `ruff format` sobre `docs/examples` formatea también los bloques de código de los `.md` y rompe
  los snippets `--8<--`. Formatea solo `src tests` y, si acaso, el `.py` concreto.
- **[herramientas]**: la herramienta Write convierte ` `/` ` dentro de cadenas en caracteres reales;
  revísalo tras escribir regex con esos escapes. `str.splitlines()` también corta por ellos: usa `split("\n")` al
  editar esos ficheros.
- **[entorno]**: el venv local tiene una instalación editable 3.4.1. `importlib.metadata.version("util_bbdd")`
  devuelve 3.4.1 hasta `pip install -e .`.

## Veredicto final

Veredicto: GO (grupos A–F completados; pendiente el cierre de versión 5.3.0)

Pendientes al cierre:

- `/version-closure` 5.3.0: `pyproject.toml`, CHANGELOG `[5.3.0]`, pie de figura de `docs/architecture.md` (v5.3.0,
  fecha, 371 ficheros), commit `release:` y tag anotado en local; el push, el usuario.
- util_bbdd_web: aplicar `WEB_HANDOFF.md` en ese proyecto.
