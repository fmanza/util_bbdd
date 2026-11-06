# CONTEXT SNAPSHOT

## Contexto del repositorio revisado

- `src/util_bbdd/doc/database_documentation.py` — fachada `DatabaseDocumentation`; registra Word/Excel/HTML con
  `build_default_renderer_registry(...)`.
- `src/util_bbdd/doc/infrastructure/renderers/registry.py:41` — `RendererRegistration` (`output_extension`,
  `include_graph_generator`, `accepts_graph_generator`, `factory`).
- `src/util_bbdd/doc/application/ports.py:207` — `DocumentRendererPort.generate_document(tables, views, routines,
  data_provider, output_target, print_config, graph_generator)`.
- `src/util_bbdd/doc/application/use_cases/documentation_orchestrator.py:396,433` — el generador de grafos se crea
  una vez por sesión si `needs_graph_generator()`; `DocumentationGraphDomainService.GRAPH_FORMATS = {"word","html"}`
  (`doc/domain/services.py:43`).
- `src/util_bbdd/doc/infrastructure/runtime/output_runtime.py:21-25` — formatos soportados y carpetas
  `WORD/EXCEL/HTML`.
- `src/util_bbdd/doc/infrastructure/renderers/word_generator.py` — orden de referencia: `_generate_single_document_chunk`
  (:227: título → leyenda si hay diagramas → inventario → tablas → vistas → rutinas → info BD → almacenamiento →
  condiciones del motor), `_add_table_section` (:494: comentario, charset, DDL, columnas, PK, FK, únicas, índices,
  diagrama), `_build_diagram_summary_payload` (:627).
- `src/util_bbdd/doc/infrastructure/renderers/shared/print_config_manager.py` — `DEFAULT_GRAPH` (`max_depth=1`,
  `max_subnodes=10`, `direction="both"`), `resolve_for_word` (:300), `resolve_for_excel` (:355), `resolve_for_html`
  (:374).
- `src/util_bbdd/doc/infrastructure/renderers/html_generator.py:1095-1116` — `_build_unique_slug` / `_build_slug_map`
  (sufijo `-2`, `-3` según orden de entrada).
- `src/util_bbdd/_core/filenames.py:6` — `safe_file_stem` (sin travesía; no trata nombres reservados de Windows).
- `src/util_bbdd/analysis/base.py` — `GraphDocument` agnóstico (:114), `build_graph_document` (:168),
  `_traverse_levels` (:283) con frontera `set[str]` (:293, :331).
- `src/util_bbdd/analysis/graphviz_ext.py:16-22` — `graphviz` se importa opcional; construir el generador no exige `dot`.
- `src/util_bbdd/comparar/reporters/_base.py:111` — `escape_mermaid_label` (G46);
  `comparar/reporters/markdown_reporter.py:29` — `_mermaid_node_id`.
- `src/util_bbdd/comparar/comparator.py:95` — `SchemaComparator.compare(source: Inspector, target: Inspector, …)`:
  necesita dos conexiones vivas. `comparar/models.py` — `SchemaDiff` puro con `to_dict`/`from_dict` (:114, :129).
- `src/util_bbdd/metadata/model.py:260` — `SchemaSnapshot` sin serialización.
- `scripts/gen_arquitectura_capas.py:43-65` — capas: `doc` 7, `comparar` 6, `analysis` 6, `_core` 1; `doc → comparar`
  permitido pero no dibujado (`DRAWN`).
- `mkdocs.yml:261-265, 292` — `pymdownx.superfences` con `custom_fences` mermaid; el sitio del repo carga `mermaid@11`
  de CDN.
- `pyproject.toml` — dependencias: sqlalchemy, pandas, openpyxl, python-docx, jinja2 (sin PyYAML). Versión 5.2.0.
- `C:\Desarrollo\python\libs\util_bbdd_web`:
  - `backend/app/integrations/util_bbdd/documentation.py:42,360` — `_FORMAT_DIRS` (`word/excel/html`) y recolocación.
  - `backend/app/api/v1/runs.py:482,505` — sitio HTML con URL firmada y ZIP de la ejecución (`/{run_id}/archive`).
  - `docs/plan/UTIL_BBDD_GAPS.md` — último hueco G48; siguiente libre G49.

## Hechos externos verificados (2026-11-05)

- Zensical soporta oficialmente `erDiagram` (y flowchart, secuencia, clases, estados); configuración: la misma
  `custom_fences` de `pymdownx.superfences`. No documenta qué versión de Mermaid empaqueta. Fuente:
  <https://zensical.org/docs/authoring/diagrams/>.
- Mermaid `erDiagram` (docs 12.3.0): alias `p[Person]` o `a["Customer Account"]`; nombres unicode y con espacios
  entre comillas; tipo de atributo: empieza por letra, admite dígitos, `-`, `_`, paréntesis y corchetes (**no comas
  ni espacios**: `decimal(10,2)`, `double precision` no valen); claves `PK`, `FK`, `UK` separadas por coma; comentario
  entre comillas sin `"` dentro; `--` identificante, `..` no identificante; desde 12.0 el ER usa ELK y look `neo` por
  defecto. Fuente: <https://mermaid.js.org/syntax/entityRelationshipDiagram.html>.
- Versionado multi-sitio (mike) en Zensical: no verificado (la página de compatibilidad devolvió 404).

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: `.gitignore` (del usuario); de esta sesión, `.github/AGENTS.md` y
  `.github/prompts/doc_markdown_feature.prompt.md`.
- Último tag / versión publicada: v5.2.0

## Clasificación metodológica
- Tipo principal: new_feature
- Estado real de alcance: acotado a `doc/` (+ punto común de escape Mermaid); web planificada aparte
- Consecuencia: PLAN + AUDIT_PLAN; IMPLEMENT tras aprobación

## Gate G0 · Context Ready
- [x] Código de `doc/`, `analysis/`, `comparar/` y web leído
- [x] Decisiones del usuario registradas
