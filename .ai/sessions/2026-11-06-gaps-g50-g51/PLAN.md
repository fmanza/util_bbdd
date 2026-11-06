# PLAN — U-11.1 (G50) y U-11.2 (G51): util_bbdd 5.4.0

Sesión `2026-11-06-gaps-g50-g51` · util_bbdd 5.3.0 (`2841111d`) · Fase: PLAN. Origen: plan de la ola 11 de
util_bbdd_web (`.ai/sessions/2026-11-06-gaps-g50-g51/`, aprobado allí; D11-1 a D11-8). Las referencias de ese plan se
han verificado contra este árbol; las diferencias van marcadas con **[ajuste]**.

## 1. Objetivo

1. **G50**: que la documentación Markdown pueda referenciar un `mermaid.min.js` ya publicado (ruta relativa a `docs/`
   o URL `https://`) sin copiarlo en cada generación.
2. **G51**: que `manifest.json` liste **todas** las páginas `.md` con título en texto plano, sección y papel, para que
   un visor (la web) no tenga que deducir el árbol de la estructura de carpetas.

Dos fases independientes, un commit cada una, y la release 5.4.0.

## 2. Estado verificado (5.3.0)

| Pieza | Dónde | Hoy |
|---|---|---|
| Opción `mermaid_js` | `print_config_manager.py:93` (defecto), `:276` (normaliza), `:466` (resuelve) | Ruta a un fichero |
| Validación | `documentation_orchestrator.py:126-134` `_check_markdown_files` | Fichero existente o `DocumentationConfigError` |
| Copia | `markdown_generator.py:380-382` | `writer.copy("docs/assets/javascripts/mermaid.min.js", …)`, **aunque `mkdocs_yml=False`** |
| `mkdocs.yml` | `_site.py:17-51` `mkdocs_yml(..., with_mermaid_js: bool, nav)` | `theme.font: false` + `extra_javascript: [MERMAID_JS_PATH]` |
| Manifiesto | `_writer.py:92-119` `publish(metadata)`, `MANIFEST_FORMAT_VERSION = 1` | `files` (ruta → sha256) de todo lo escrito |
| Huérfanos | `_writer.py:128-160` | Borra lo que listaba el manifiesto anterior y ya no se genera, si está intacto; solo mira `format`, no `format_version` |
| Títulos | `_pages.py:73-77` (`Tabla: …`, `Vista: …`, `<Tipo>: …`), `_site_pages.py:50,90,103,128,142,167`, `_trace.py:287`, `_changes.py:382` | H1 con `md_text` (escapes y entidades) |
| Índices por letra | `_site_pages.py:64-113` `index_pages(title, entries, page_size) -> dict[str, list[str]]` | Título de cada página (`heading`) y letra solo dentro de la función |

## 3. U-11.1 — `feat(doc): Mermaid del sitio Markdown referenciado sin copiarlo` (G50)

### API

`imprimir["markdown"]["mermaid_js_ref"]: str | None` (defecto `None`).

| Valor | `mkdocs.yml` | Copia | `theme.font: false` |
|---|---|---|---|
| Ruta relativa a `docs/` (`assets/javascripts/mermaid.min.js`) | `extra_javascript: ["<ruta>"]` | No | Sí (sitio sin Internet, como `mermaid_js`) |
| URL `https://…` | `extra_javascript: ["<url>"]` | No | No (sitio con Internet) |

Reglas de validación (`DocumentationConfigError`, al construir, antes de conectar):

- Excluyente con `mermaid_js`.
- Cadena no vacía, sin espacios en los extremos, sin caracteres de control.
- URL: solo `https://` con host (`urlsplit`); `http:`, `javascript:`, `data:`, `file:` y `//host` → error.
- Ruta: POSIX relativa, sin `\`, sin `/` inicial, sin `:` (letras de unidad y esquemas), sin segmentos `..`, `.` ni
  vacíos.
- El valor se escribe en YAML con `json.dumps` (como `site_name`): sin inyección.
- Con `mkdocs_yml=False`, la opción no tiene efecto: aviso en el log (no error; compatible). **[ajuste]**

### Cambios

| Fichero | Cambio |
|---|---|
| `print_config_manager.py` | `DEFAULT_MARKDOWN["mermaid_js_ref"] = None`; normalizada con `_normalize_non_empty_str(...) or None`; incluida en `resolve_for_markdown` |
| `documentation_orchestrator.py` | `_check_markdown_files`: exclusión y reglas de arriba (función privada `_check_mermaid_ref`, pura, en la capa de aplicación: no importa la infraestructura) |
| `_site.py` | `mkdocs_yml(..., with_mermaid_js, nav, mermaid_ref: str \| None = None)` **[ajuste: parámetro nuevo con defecto en lugar de sustituir `with_mermaid_js`]**; con `mermaid_ref` escribe `json.dumps(ref)` en `extra_javascript` y `font: false` solo si no es URL |
| `markdown_generator.py` | `_write_machine_files` pasa `mermaid_ref`; no copia nada con él |
| `_writer.py` | `publish(metadata, *, keep=frozenset())`: rutas que **no** se borran como huérfanas aunque las listara el manifiesto anterior. El generador pasa `docs/<ref>` si la referencia es relativa **[ajuste: ver AUDIT_PLAN T2]** |
| `database_documentation.py` | Docstring de `imprimir`: `markdown.mermaid_js_ref` |
| Docs | `docs/api/database_documentation.md` (opción, tabla de comportamiento con el fichero ausente, T3/T4), `docs/examples/markdown_documentation.md`, `docs/functional/…` si lista las opciones, `CHANGELOG.md` |

### Tests (`tests/unit/test_doc_markdown_*.py`)

- `mkdocs.yml` con ruta (con `font: false`) y con URL (sin él); nada en `docs/assets/` ni en `manifest.json["files"]`.
- Las dos opciones a la vez → error; `..`, `./x`, `a//b`, `/abs`, `C:\x`, `C:/x`, `javascript:alert(1)`, `data:…`,
  `http://x`, `//host/x`, `""`, `"  "`, salto de línea → error, sin haber conectado.
- `mermaid_js` sin cambios (copia, `font: false`, `extra_javascript`).
- Carpeta con copia anterior (`mermaid_js`) regenerada con `mermaid_js_ref` a la misma ruta: el fichero **sigue ahí**.
- `mkdocs_yml=False` + ref: aviso, sin error.
- Valor con comillas o `:` en la URL → YAML válido (`yaml.safe_load` en el test, si PyYAML está en `dev`; si no,
  comparación de texto).

## 4. U-11.2 — `feat(doc): índice de páginas en manifest.json` (G51)

### Contrato (`manifest.json`, `format_version` 2)

```json
{
  "format": "util_bbdd.doc.markdown",
  "format_version": 2,
  "files": {"…": "sha256:…"},
  "pages": [
    {"path": "index.md", "title": "Documentación de la Base de Datos - ventas", "section": "home", "role": "home"},
    {"path": "tables/index.md", "title": "Tablas", "section": "tables", "role": "index"},
    {"path": "tables/index-a.md", "title": "Tablas: A", "section": "tables", "role": "letter", "letter": "a"},
    {"path": "tables/acm_agenda.md", "title": "Tabla: ACM_AGENDA", "section": "tables", "role": "object",
     "id": "table:ACM_AGENDA", "kind": "table"},
    {"path": "database/info.md", "title": "Información de la Base de Datos", "section": "database", "role": "page"},
    {"path": "traceability.md", "title": "Trazabilidad", "section": "traceability", "role": "page"},
    {"path": "changes.md", "title": "Cambios de esquema", "section": "changes", "role": "page"}
  ]
}
```

(Los `id` y *slugs* del ejemplo son ilustrativos: los reales salen de `ObjectRecords` y `unique_slugs`.)

- `path` relativa a `docs/`, POSIX; una entrada por cada `.md` escrito, ni más ni menos.
- `title`: **texto plano** (T5), calculado desde el valor original, no desde el H1: mismo texto que el H1 sin escapes
  ni entidades; saltos de línea y caracteres de control → espacio (helper `plain_text` en `_text.py`, que reutiliza
  `_LINE_BREAKS`).
- `section` ∈ `home`, `tables`, `views`, `routines`, `database`, `traceability`, `changes`; `role` ∈ `home`, `index`,
  `letter`, `object`, `page`. Claves opcionales **ausentes** cuando no aplican (`letter` solo en `letter`; `id` y
  `kind` solo en `object`), como el resto de contratos JSON de la librería.
- Orden: el de la `nav` — portada, tablas, vistas, rutinas, base de datos, trazabilidad, cambios — y dentro de cada
  sección `index` → letras (en el orden del índice, con sus subpáginas) → objetos (orden alfabético de la librería).
- `id` y `kind`: los del registro del objeto (los mismos que `catalog.json` y el front matter), **también** con
  `catalog_json=False` o `front_matter=False`.
- Lectura de un manifiesto v1 anterior (limpieza de huérfanos): sin cambios (solo mira `format` y `files`).

### Cambios

| Fichero | Cambio |
|---|---|
| `_writer.py` | `MANIFEST_FORMAT_VERSION = 2`; `publish(metadata, *, keep=…, pages=())` escribe `pages` (lista de dicts ya ordenada) |
| `_text.py` | `plain_text(value) -> str` |
| `_site_pages.py` | `index_page_titles(title, entries, page_size) -> dict[str, tuple[str, str \| None]]` (fichero → título plano y letra) con la misma paginación que `index_pages` **[ajuste: función hermana en lugar de cambiar el retorno de `index_pages`, que usa `test_doc_markdown_text.py`; la paginación se extrae a un helper privado común para no duplicarla]** |
| `markdown_generator.py` | Recoge `PageEntry` (dataclass privada) en `_write_home`, `_write_index`, `_emit` (objetos), `traceability` y `changes`; ordena al final y lo pasa a `publish` |
| Docs | `docs/api/database_documentation.md` (contrato de `manifest.json` v2), ADR-006 (enmienda: el manifiesto también es contrato versionado; `pages` aditivo), `CHANGELOG.md` |

### Tests

- Conjunto de `pages[].path` == conjunto de `.md` bajo `docs/` en `files` (sin duplicados).
- `title` con nombres `ACM_AGENDA`, `_x_`, `a|b`, `*c*`, `<d>` y `e&f` → texto idéntico al original con su prefijo.
- `id` de cada `object` == `id` de `catalog.json`; presente con `catalog_json=False`.
- Orden de secciones y de roles; subpáginas `index-a-2.md` con `letter = "a"`.
- Dos generaciones del mismo esquema → mismo `pages`.
- Regeneración sobre una carpeta con `manifest.json` v1 (fixture escrito a mano) → limpia los huérfanos como antes.
- Trazabilidad y cambios presentes → sus páginas en `pages`.

## 5. Release `release: v5.4.0`

`pyproject.toml` 5.4.0, `CHANGELOG.md`, `docs/plan`/handoff a la web (`WEB_HANDOFF` de esta sesión: opción, contrato
y comportamiento de T3/T4), wheel + `.sha256` (release_guide §5–7; push y subida, el usuario).

## 6. Riesgos

- R1 Cambio de `format_version` del manifiesto: consumidores que exijan `== 1` (ninguno en el repo; la web no lo lee
  aún). Aditivo.
- R2 Doble fuente del título (H1 escapado y `title` plano): pueden divergir si alguien cambia uno. Mitigación: test
  que compara cada `title` con el H1 de su página desescapado (solo en el test) en un fixture con caracteres especiales.
- R3 Orphans al cambiar de `mermaid_js` a `mermaid_js_ref` en la misma carpeta (ver AUDIT_PLAN T2).
- R4 Tamaño del manifiesto (~150 B por página).
