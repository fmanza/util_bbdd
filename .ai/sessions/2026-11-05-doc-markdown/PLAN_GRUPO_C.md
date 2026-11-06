# PLAN + AUDIT_PLAN — Grupo C (`catalog.json`, `llms.txt`, `mkdocs.yml`, Mermaid local)

`/new-feature` sobre la sesión `2026-11-05-doc-markdown` (PLAN §7, grupo C). Se apoya en el grupo B (`72a30117`).
Quedan fuera D (trazabilidad), E (`CHANGES.md`) y F (documentación, versión).

## Inputs

| Input | Valor |
|---|---|
| Objetivo | Añadir a la salida Markdown: catálogo máquina-legible versionado, ficheros `llms.txt`/`llms-full.txt` y un `mkdocs.yml` listo para `zensical build`, con opción de Mermaid local para sitios sin Internet |
| Módulos | `doc/infrastructure/renderers/markdown/`: `_catalog.py` (nuevo), `_site.py` (nuevo), `_front_matter.py`, `_writer.py`, `markdown_generator.py`; `print_config_manager.py`; `docs/adr/ADR-006-catalogo-documentacion-markdown.md` (nuevo) |
| API pública | Claves nuevas en `imprimir["markdown"]`: `catalog_json`, `llms_txt`, `llms_full_txt`, `mkdocs_yml` (bool, por defecto `True`), `site_name` (str), `mermaid_js` (ruta). `catalog.json` pasa a ser **contrato público versionado** (ADR-006). MINOR |
| Contrato de entrada | El del grupo B; `mermaid_js` debe existir y ser fichero |
| Contrato de salida | Todo determinista salvo `manifest.json`; cada fichero nuevo listado en el manifiesto |
| Restricciones | Sin dependencias nuevas: YAML escrito a mano con escalares JSON; sin red |
| Migraciones | No |

## Hechos verificados

- `zensical/templates/assets/javascripts/bundle.*.min.js` (0.0.71) carga Mermaid así:
  `typeof mermaid=="undefined"||mermaid instanceof Element ? ct("https://unpkg.com/mermaid@11/…") : U(void 0)`.
  Si `window.mermaid` ya existe, **no va a unpkg**. Hace falta comprobar en un navegador sin red que el
  `extra_javascript` local se carga antes de que el bundle procese el primer bloque (condición CC2).
- Snapshot disponible para el catálogo: `ColumnMeta` (`ordinal`, `data_type`, `nullable`, `default`, `comment`,
  `identity`, `generated`), `IndexMeta` (`columns`, `unique`, `primary`, `method`), `ViewMeta.definition`,
  `RoutineMeta` (`signature`, `definition`), `ForeignKeyMeta` (`on_delete`, `on_update`).

## PLAN

### C1 · `catalog.json` (formato v1, ADR-006)

Se escribe en `docs/catalog.json`, con JSON ordenado, `indent=2`, sin fechas y determinista:

```json
{
  "format": "util_bbdd.doc.catalog", "format_version": 1,
  "engine": "sqlite", "schema": "main", "database": "…",
  "selection": {"tables": true, "views": true, "procedures": false, "functions": false},
  "objects": [
    {"id": "table:main.pedidos", "kind": "table", "name": "pedidos", "schema": "main", "path": "tables/pedidos.md",
     "comment": "…",
     "columns": [{"name": "id", "ordinal": 1, "type": "INTEGER", "nullable": false, "default": null,
                  "comment": null, "identity": "by default", "generated": null}],
     "pk": {"name": "…", "columns": ["id"]},
     "fk_out": [{"name": "…", "columns": [...], "ref": "table:main.clientes", "ref_columns": [...],
                 "on_delete": "NO ACTION", "on_update": "NO ACTION"}],
     "fk_in": ["table:main.lineas"],
     "uniques": [{"name": "…", "columns": [...]}],
     "indexes": [{"name": "…", "columns": [...], "unique": false, "primary": false, "method": null}],
     "hash": "sha256:…"},
    {"id": "view:main.v_pedidos", "kind": "view", …, "columns": […], "definition_hash": "sha256:…", "hash": "…"},
    {"id": "procedure:main.p_alta", "kind": "procedure", …, "signature": "…", "definition_hash": "sha256:…", "hash": "…"}
  ]
}
```

- **Contenido**: los objetos documentados, es decir, la misma selección de `imprimir` que las páginas. `selection`
  la registra para que `CHANGES.md` (grupo E) distinga un objeto borrado de uno que no se pidió.
- **Orden**: por tipo (`table`, `view`, rutinas) y nombre (`sort_key`); listas internas en el orden del catálogo
  (columnas por `ordinal`) o por nombre.
- **Definiciones** de vistas y rutinas: solo el hash. El texto completo ya está en su página y haría el fichero muy
  grande.
- `ObjectRecords` (grupo B) se amplía con estos campos. El **front matter publica el mismo `id` y `hash`** que el
  catálogo, y sigue siendo el subconjunto `FRONT_MATTER_KEYS`.
- **ADR-006**:
  - `format_version` sube solo con cambios incompatibles (quitar o renombrar campos, cambiar significado);
  - los campos nuevos opcionales no la suben, así que los lectores deben ignorar campos desconocidos;
  - `id` y `path` son estables mientras el nombre del objeto no cambie.

### C2 · `llms.txt` y `llms-full.txt` (formato de llmstxt.org)

`docs/llms.txt`:

```markdown
# Documentación de la base de datos <bd>

> Schema main (sqlite): 3 tablas, 1 vista, 0 rutinas. Un fichero Markdown por objeto con front matter
> (id estable, PK, FK). Catálogo completo en catalog.json.

## Tablas
- [pedidos](tables/pedidos.md): <comentario>
## Vistas
- …
## Rutinas
- …
## Optional
- [Catálogo JSON](catalog.json): estructura completa (columnas, claves, índices)
- [Documentación completa](llms-full.txt): todas las páginas en un solo fichero
```

`docs/llms-full.txt`:

- portada seguida de cada página de objeto en el orden del índice, sin front matter;
- cada página va precedida de `<!-- <id> · <ruta> -->`, para que la IA conserve el id y el origen;
- se escribe **en streaming**: `StagedWriter.open_stream(rel)` calcula el hash de forma incremental y no guarda el
  texto en memoria.

### C3 · `mkdocs.yml` y Mermaid local

Va en `MARKDOWN/mkdocs.yml` (junto a `manifest.json`) y está listado en el manifiesto:

```yaml
# Generado por util_bbdd 5.3.0 (formato markdown); se reescribe en cada generación.
site_name: "Documentación de <bd>"
docs_dir: docs
theme:
  name: material
markdown_extensions:
  - tables
  - admonition
  - attr_list
  - toc:
      permalink: true
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
extra_javascript:            # solo con markdown.mermaid_js
  - assets/javascripts/mermaid.min.js
```

- `site_name`: valor de la opción o `"Documentación de <bd>"`, escrito con `json.dumps` (cadena JSON = escalar YAML
  entre comillas, a prueba de inyección).
- `mermaid_js`: se copia a `docs/assets/javascripts/mermaid.min.js`, se lista en el manifiesto y se referencia en
  `extra_javascript`. Si no existe o no es fichero: `DocumentationConfigError` al construir `DatabaseDocumentation`,
  validado igual que `plantilla_word`.

### C4 · Limpieza más segura (ajuste del grupo B)

- Un huérfano del manifiesto anterior solo se borra si **su hash actual coincide** con el registrado, es decir, si
  nadie lo ha modificado.
- Si el usuario editó un fichero generado (p. ej. `mkdocs.yml`) y lo desactiva (`mkdocs_yml: False`), su fichero
  se conserva y se avisa en el log.

### Tests

| Fichero | Casos |
|---|---|
| `test_doc_markdown_catalog.py` | Contenido de `catalog.json` en SQLite: columnas con `default`, índices, FK con acciones, `fk_in`, vistas con `definition_hash`, `selection`; `id`/`hash` iguales a los del front matter; determinismo; desactivado → no existe y no está en el manifiesto |
| `test_doc_markdown_llms.py` | Estructura de `llms.txt` (H1, cita, secciones, `Optional`), comentarios escapados; `llms-full.txt` con un marcador por objeto, sin front matter y en el orden del índice; streaming (hash del manifiesto igual al del fichero) |
| `test_doc_markdown_site.py` | `mkdocs.yml` cargable por PyYAML (`yaml.unsafe_load`, por el tag `!!python/name`) con `site_name` hostil (`"`, `:`, `\n`); `mermaid_js` copiado y en `extra_javascript`; ruta inexistente → `DocumentationConfigError`; `zensical build --strict` con el `mkdocs.yml` generado (`integration`) |
| `test_doc_markdown_e2e.py` (ampliado) | Huérfano modificado por el usuario → se conserva |

## AUDIT_PLAN

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| CF1 | El hash del front matter cambia respecto al grupo B (el registro gana campos) | No hay versión publicada; el cambio va en la misma 5.3.0 |
| CF2 | `catalog.json` grande con miles de tablas y muchas columnas (~1 KB por columna en el peor caso) | Sin definiciones completas; aceptable hasta unos miles de tablas; se documenta |
| CF3 | `selection` distinta entre dos generaciones | Lo resolverá E: avisará en lugar de dar por borrados los objetos no pedidos |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| CT1 | Orden de carga: el bundle de Zensical podría pedir Mermaid antes de que `extra_javascript` lo defina | **CC2**: Playwright con la red bloqueada (`route("**/unpkg.com/**", abort)`) sobre el sitio construido; se esperan diagramas dibujados y ninguna petición a unpkg. Si falla, alternativa: `extra_javascript` con un cargador que defina `window.mermaid` de forma síncrona |
| CT2 | `!!python/name:` en el YAML: un lector `safe_load` lo rechaza | Es la sintaxis que documenta Zensical y la del `mkdocs.yml` del repo; el test usa `unsafe_load` solo para verificar la estructura |
| CT3 | Copiar `mermaid.min.js` (unos 3 MB) en cada generación | Solo con la opción; hash en el manifiesto |
| CT4 | Validar `mermaid_js` al construir exige tocar `DocumentationBootstrap` | Mismo mecanismo que `word_template_check` (función inyectada); no cambia la API |

### Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| CS1 | Inyección en `mkdocs.yml` por `site_name` o por el nombre de la base de datos | Escalar JSON entre comillas; test hostil |
| CS2 | `mermaid_js` apuntando a un fichero arbitrario | Se copia tal cual al sitio que publica el usuario, con la ruta que da el propio usuario; se documenta que debe ser el `mermaid.min.js` oficial |
| CS3 | `llms.txt` con texto del catálogo | Escape `md_text` en enlaces y comentarios |

### Simplificaciones

- Sin JSON Schema formal de `catalog.json` en esta versión: el ADR describe los campos y los tests los fijan.
- `llms-full.txt` sin las páginas de base de datos (almacenamiento y condiciones del motor): son operativas, no del
  modelo de datos.

### Veredicto: `GO_CONDICIONAL`

1. **CC1**: ADR-006 escrito y aceptado por el usuario antes de cerrar el grupo.
2. **CC2**: verificación sin red del Mermaid local en Zensical (CT1), con los resultados en la sesión.
