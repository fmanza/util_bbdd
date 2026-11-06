# Traspaso a util_bbdd_web — documentación Markdown (util_bbdd 5.3.0)

Para trabajar **en el proyecto util_bbdd_web** (`C:\Desarrollo\python\libs\util_bbdd_web`). Desde util_bbdd no se
edita la web. Este documento resume lo que la librería ofrece desde 5.3.0 y los cambios que se proponen en la web, con
rutas reales comprobadas el 2026-11-06 (web v1.10.1).

## 1. Qué ofrece util_bbdd 5.3.0

- `DatabaseDocumentation(formatos=["markdown"])` genera la carpeta `<nombre>/MARKDOWN/` con:
  - un `.md` por tabla, vista y rutina;
  - diagramas `erDiagram` de Mermaid, **sin Graphviz**;
  - `catalog.json`, `llms.txt` y `llms-full.txt`;
  - `mkdocs.yml` y `manifest.json`.
- Opciones en `imprimir["markdown"]`: `max_diagram_depth`, `index_page_size`, `front_matter`, `column_anchors`,
  `catalog_json`, `llms_txt`, `llms_full_txt`, `mkdocs_yml`, `site_name`, `mermaid_js`, `trace_map` y `previous`.
  Referencia: `docs/api/database_documentation.md` § «Documentación Markdown».
- Progreso: fase `"markdown"`, un evento por tabla. Cancelación sin dejar la carpeta a medias (staging).
- `changes.json` (con `previous`) es un `SchemaDiff` (`util_bbdd.schema_diff` v1): el mismo formato que ya muestra el
  visor de diferencias de la web.
- Errores al construir (`DocumentationConfigError`): `mermaid_js` inexistente, mapa de trazabilidad inválido (todos
  los errores en el mensaje), `previous` sin `catalog.json` válido. Al generar: `previous` de otro motor.

## 2. Cambios propuestos en la web

| # | Cambio | Dónde (web) | Notas |
|---|---|---|---|
| W-1 | Subir util_bbdd a 5.3.0 (wheel vendorizado y `uv.lock`) | `backend/pyproject.toml` (ADR-006 de la web) | Requisito del resto |
| W-2 | Formato `markdown` en `_FORMAT_DIRS` | `backend/app/integrations/util_bbdd/documentation.py:42` → `{"word": "WORD", "excel": "EXCEL", "html": "HTML", "markdown": "MARKDOWN"}` | — |
| W-3 | **Recolocar la carpeta completa** como HTML | Mismo fichero, bucle de `_document` (≈ líneas 359-372): hoy solo HTML mueve la carpeta; el resto mueve los ficheros de primer nivel (`iterdir() if is_file()`) y **perdería `docs/`** | Rama `if fmt in {"html", "markdown"}`; destino propuesto `outputs/markdown/documentacion`; `produced["markdown"]` = `…/docs/index.md` |
| W-4 | Pasar siempre el Mermaid local | `imprimir["markdown"]["mermaid_js"] = settings.mermaid_js` (`UBW_MERMAID_JS`, `core/config.py:104`), como ya hace `compare.py` | La web no sale a Internet (ADR-007): sin esto, el sitio Zensical no dibuja los diagramas. Pone además `font: false` |
| W-5 | Opciones del formulario | `DocumentationOptions` (`documentation.py:76`) y `domain/runs/operations.py` (`_group`): casilla «Markdown», `site_name` y tope de profundidad (`max_diagram_depth`, 1–3) | Los diagramas usan `graph_depth`, `graph_direction`, `graph_columns` y `graph_max_columns`, que ya existen. `relations_first` de la web corresponde a `compact` de util_bbdd. `graph_data_types` y `graph_orthogonal` no aplican: Mermaid siempre muestra los tipos |
| W-6 | Mapa de trazabilidad por proyecto | Subida de un `.toml`/`.json`, con la validación de subidas (`domain/templates/files.py` como referencia): tamaño máximo 1 MB, igual que la librería | Mostrar el mensaje de `DocumentationConfigError` tal cual: lista todos los errores |
| W-7 | «Comparar con la ejecución…» | Selector de una ejecución anterior de documentación con la misma conexión y el mismo schema; pasa su carpeta `outputs/markdown/documentacion` como `previous` | `docs/changes.json` se puede abrir con el visor de diferencias (`domain/runs/diff.py`, que hoy lee `outputs/diff/schema_diff.json`) |
| W-8 | Vista previa | Reutilizar la vista previa del Markdown de la comparación (con `stripMermaidConfig`, G46) para `docs/index.md` y las páginas | Opcional: construir el sitio con `zensical build` en el job y servirlo con URL firmada, como el HTML (ADR-007) |
| W-9 | Descarga | El ZIP de la ejecución (`api/v1/runs.py:505`) ya incluye la carpeta si se registran sus artefactos | Sin cambios si W-3 registra los ficheros |
| W-10 | ROADMAP | `docs/plan/ROADMAP.md`, sección «Mejoras opcionales» o nueva fase | No es un hueco de API (`UTIL_BBDD_GAPS.md`): es capacidad nueva |

## 3. Pruebas sugeridas en la web

- Integración con SQLite:
  - `formats=("markdown",)`;
  - en la salida, `outputs/markdown/documentacion/docs/index.md`, `catalog.json` y `mkdocs.yml`, este con
    `extra_javascript` cuando hay `UBW_MERMAID_JS`;
  - artefactos registrados y presentes en el ZIP.
- Mapa de trazabilidad inválido: un error de formulario legible.
- Comparación con una ejecución anterior: `changes.json` se abre en el visor de diferencias.
