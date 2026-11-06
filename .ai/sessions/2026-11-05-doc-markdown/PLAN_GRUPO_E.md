# PLAN + AUDIT_PLAN — Grupo E (`CHANGES.md` respecto de una generación anterior)

`/new-feature` sobre la sesión `2026-11-05-doc-markdown` (PLAN §4.8 y §7, grupo E). Se apoya en el grupo D
(`db1e6b7b`). Queda fuera F (documentación, web y versión).

## Inputs

| Input | Valor |
|---|---|
| Objetivo | Con `imprimir["markdown"]["previous"]`, comparar el `catalog.json` de una generación anterior con el actual y publicar los cambios de esquema en `docs/changes.md` (personas) y `docs/changes.json` (máquinas) |
| Módulos | `doc/infrastructure/renderers/markdown/_changes.py` (nuevo); `markdown_generator.py`, `_catalog.py`, `_site.py`, `_writer.py` (enganche); `print_config_manager.py` (clave `previous`); `database_documentation.py` (validación al construir); `scripts/gen_arquitectura_capas.py` (arista nueva `doc → comparar`) |
| API pública | Clave nueva `markdown.previous`: carpeta de una generación anterior (`MARKDOWN` o su `docs/`) o la ruta de su `catalog.json`. `changes.json` usa el formato público `util_bbdd.schema_diff` v1 (`SchemaDiff.to_dict()`). MINOR |
| Contrato de entrada | `catalog.json` de formato `util_bbdd.doc.catalog` v1 (ADR-006) |
| Contrato de salida | Determinista dados los dos catálogos; sin conexión a la base de datos |
| Restricciones | Sin dependencias nuevas; reutiliza los modelos de `comparar` (`SchemaDiff`, `TableDiff`…) |
| Migraciones | No |

## Hechos verificados

- `SchemaComparator.compare` exige dos `Inspector` vivos (`comparar/comparator.py:95`). No sirve para comparar con
  una generación pasada.
- `SchemaDiff` (`comparar/models.py`) es un modelo puro, con `to_dict()`/`from_dict()` y formato público
  `util_bbdd.schema_diff` v1. **util_bbdd_web ya muestra ese JSON** en su visor de diferencias
  (`backend/app/domain/runs/diff.py`, `DIFF_PATH = outputs/diff/schema_diff.json`), así que puede reutilizarlo para
  los cambios entre generaciones.
- `MarkdownDiffReporter` (`comparar/reporters/markdown_reporter.py:144-290`) **no es seguro para un sitio
  publicado**:
  - nombres, valores, tipos y defaults van entre backticks sin tratar backticks ni `|` (un nombre con un backtick
    cierra el *code span* y deja pasar HTML; un `|` parte la fila de la tabla);
  - los comentarios pasan por `escape_markdown_table_cell`, que no escapa HTML;
  - las definiciones van en `<details>` con Markdown dentro, que Zensical solo interpreta con `md_in_html`.
- `RoutineDiff.routine_type` es `Literal["PROCEDURE", "FUNCTION"]`: un `PACKAGE` de Oracle no cabe.

## Decisiones (a confirmar)

| # | Decisión | Opciones | Recomendación |
|---|---|---|---|
| E-A | Cómo se escribe `changes.md` | (1) Reutilizar `MarkdownDiffReporter` tal cual; (2) renderer propio en `markdown/` sobre el mismo `SchemaDiff`, con el escape de `_text.py` y **enlaces a las páginas** de los objetos añadidos o modificados | **(2)**: seguro para publicar, coherente con el resto del sitio y navegable. `changes.json` sigue siendo el formato estándar |
| E-B | El defecto de escape de `MarkdownDiffReporter` | (1) Corregirlo ahora en un `fix(comparar)` aparte, antes de E: *code spans* seguros y HTML escapado en comentarios; (2) solo registrarlo como deuda | **(1)**: afecta a los informes de comparación actuales y a su vista previa en la web. Cambio acotado con tests propios |
| E-C | Generaciones con schema distinto (p. ej. `desarrollo` frente a `produccion`) | (1) Error; (2) permitir con aviso en la cabecera | **(2)**: comparar entornos es un caso real. Un **motor** distinto sí es error: los tipos no son comparables sin el normalizador de `SchemaComparator` |

## PLAN (con las recomendaciones)

### E1 · Entrada `markdown.previous`

- Ruta a `catalog.json`, o a una carpeta. Se busca en `docs/catalog.json` y después en `catalog.json`.
- **Al construir** (`DocumentationConfigError`, en la fachada como el mapa de trazabilidad): el fichero existe, es
  JSON, tiene `format == "util_bbdd.doc.catalog"` y una `format_version` que esta librería sabe leer (1), y su tamaño
  es razonable (50 MB como máximo).
- **Al generar**, con el motor ya conocido: si el motor es distinto, `DocumentationConfigError`; si el schema es
  distinto, aviso en la cabecera.
- Si junto al catálogo anterior hay un `manifest.json` (`../manifest.json`), se toma de él `generated_at` y
  `util_bbdd_version` para la etiqueta.

### E2 · Comparación (`_changes.py`, sin E/S)

| Objeto | Clave | Diferencias |
|---|---|---|
| Tabla | `name` (sin el schema, para comparar entre schemas) | `added`/`removed`; `modified` si cambia algo de lo de abajo. Con el mismo `hash`, se salta sin comparar |
| Columna (`ColumnDiff`) | `name` | `existence` (añadida o eliminada), `type`, `nullable`, `primary_key`, `default` |
| Índice (`IndexDiff`) | `name` | `added`/`removed`/`modified` (columnas o `unique`) |
| FK (`ForeignKeyDiff`) | `name`; si no tiene nombre (SQLite), columnas → tabla referenciada | Columnas, tabla y columnas referenciadas |
| Comentario (`CommentDiff`) | Tabla o columna | Texto distinto |
| Vista (`ViewDiff`) | `name` | `added`/`removed`; `modified` si cambia `definition_hash` (sin texto: el catálogo solo guarda el hash) |
| Rutina (`RoutineDiff`) | `kind` + `name` | Igual que las vistas, por `definition_hash` o `signatures`. Los tipos que no son `PROCEDURE` ni `FUNCTION` (`PACKAGE`) se listan aparte en `changes.md` y no entran en `changes.json` |

- `selection`: un tipo de objeto solo se compara si se documentó en **las dos** generaciones. Si no, se avisa
  («No se comparan las vistas: no se documentaron en la generación anterior»), y así nada aparece como eliminado
  por no haberse pedido.
- La traza del grupo D (`trace`) no interviene: queda fuera de `hash` y de la comparación.
- Orden estable: tipo y nombre (`sort_key`). `source_label` es la generación anterior y `target_label` la actual,
  sin rutas absolutas, para mantener el determinismo.

### E3 · Salida

| Fichero | Contenido |
|---|---|
| `docs/changes.md` | Cabecera (anterior y actual, avisos de schema y `selection`); resumen (añadidas, eliminadas y modificadas por tipo); secciones por tipo con enlace a la página de cada objeto añadido o modificado (los eliminados, como texto); tablas de columnas, índices, FK y comentarios con el escape de `_text.py`. Sin diagrama Mermaid ni `<details>` |
| `docs/changes.json` | `SchemaDiff.to_dict()` (`util_bbdd.schema_diff` v1): lo puede mostrar el visor de la web |
| `llms.txt` / `nav` | Entrada «Cambios» |
| `manifest.json` | `previous: {"catalog_sha256": …, "generated_at": …, "util_bbdd_version": …}` |

Sin `previous` no cambia nada.

### E0 · `fix(comparar)` previo (decisión E-B)

- `markdown_reporter.py`: los *code spans* usan un helper que cuenta backticks y escapa `|` dentro de tablas; los
  comentarios escapan `&`, `<` y `>`.
- Para no crear una dependencia `comparar → doc`, el helper va a `_core` como texto Markdown común
  (`_core/markdown.py`), o se duplica de forma mínima en `comparar`. **Recomendación**: `_core/markdown.py`
  (`code_span`), que usarán `comparar` y `doc`.
- Tests: nombre con backtick, valor con `|`, comentario con `<script>`.
- Commit aparte y entrada en el CHANGELOG (`Fixed`).

### Tests (grupo E)

| Fichero | Casos |
|---|---|
| `test_doc_markdown_changes.py` | Generar → alterar SQLite (añadir columna, cambiar nulabilidad y default, añadir índice, borrar tabla, crear tabla, cambiar vista) → generar con `previous` → contenido de `changes.md` y de `changes.json`, que se lee con `SchemaDiff.from_dict`. También: `previous` como carpeta `MARKDOWN`, como `docs/` y como fichero; motor distinto → error al generar; schema distinto → aviso; `selection` distinta → aviso sin falsos eliminados; FK sin nombre de SQLite; determinismo; catálogo inválido o versión desconocida → error al construir; sin `previous` no hay `changes.*`; enlaces válidos con `zensical build --strict` (`integration`) |
| `tests/comparar/test_markdown_reporter_escape.py` (E0) | Escape de *code spans* y de comentarios en el informe de comparación |

## AUDIT_PLAN

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| EF1 | Diferencias que `SchemaComparator` normaliza (tipos equivalentes, defaults con formato distinto) aparecen aquí como cambios | Se compara dentro del mismo motor y con lo que escribe el catálogo: dos generaciones del mismo motor dan el mismo texto. Se documenta la diferencia con `SchemaComparator` |
| EF2 | FK sin nombre que cambia de columnas aparece como eliminada y añadida | Comportamiento correcto para una FK sin identidad. Se documenta |
| EF3 | Vistas y rutinas modificadas sin ver el texto | Se enlaza su página actual. El texto anterior solo está en la carpeta anterior, y se documenta |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| ET1 | Arista nueva `doc → comparar` (capa 7 → 6, permitida) | Añadirla a `DRAWN` y regenerar la figura con `gen_arquitectura_capas.py`. `test_architecture_import_rules.py` la valida |
| ET2 | `routine_type` limitado a `PROCEDURE`/`FUNCTION` | Los demás tipos se listan aparte, sin forzar el modelo |
| ET3 | Catálogo anterior grande (miles de tablas) | Lectura única y salto rápido por `hash` igual; límite de 50 MB |
| ET4 | Una versión futura de util_bbdd tendrá que leer catálogos v1 | ADR-006 ya lo exige; el lector comprueba `format_version` |

### Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| ES1 | El catálogo anterior lo controla quien lo aporta: nombres o comentarios maliciosos | Mismo escape que las páginas (`_text.py`), *code spans* seguros y enlaces solo a slugs propios |
| ES2 | Ruta de `previous` | Solo se lee el `catalog.json` (y el `manifest.json` vecino); nada se ejecuta ni se resuelve |
| ES3 | Escape del informe de `comparar` (hallazgo) | E0 |

### Veredicto: `GO_CONDICIONAL`

Condición: el usuario confirma E-A, E-B y E-C. Si E-B es «sí», E0 va primero, en su commit.
