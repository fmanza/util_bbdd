# AUDIT_CODE — U-11.1 (`a3025d3c`) y U-11.2 (`5b443659`)

## Condiciones del AUDIT_PLAN

| Condición | Estado | Evidencia |
|---|---|---|
| T2 `keep` en `publish` | Cumplida | `test_switching_from_copy_to_ref_keeps_the_copied_file`; con URL la copia sí se borra (`test_switching_to_https_ref_removes_the_old_copy`) |
| T5 títulos en texto plano | Cumplida | `test_titles_are_plain_text_and_match_the_h1`: nombres `ACM_AGENDA`, `_raro_`, `b\|c*d`, `<e&f>`; cada `title` == H1 desescapado de su página |
| T6 manifiesto v1 | Cumplida | `test_regenerating_over_a_v1_manifest_still_removes_orphans` |
| T3/T4 documentados | Cumplida | `docs/api/database_documentation.md` § «Mermaid referenciado»; docstring de `_site.py` |
| Comandos de desarrollo | Cumplida | ruff, `ruff format`, mypy (371 ficheros), pytest 7097 passed / 618 skipped, `zensical build --strict`, `gen_arquitectura_capas.py` sin cambios de contenido |

## Bugs potenciales

- Ninguno abierto. Revisado: el orden de `pages` es un `sorted` estable por (sección, papel), así que dentro de cada
  papel se conserva el de escritura (letras en el orden del índice, objetos en orden alfabético de la librería).

## Edge cases

- `mermaid_js_ref` vacío o solo espacios → `None` (se normaliza como `site_name`); test.
- `mermaid_js_ref` con otro formato que no sea Markdown → no se valida (como `mermaid_js`); test.
- `mkdocs_yml=False` + ref → aviso, sin error; test.
- Rutinas: SQLite no tiene rutinas, así que su entrada en `pages` (`"<Tipo>: nombre"`, `kind` en minúsculas) no
  tiene test de extremo a extremo; el título usa la misma expresión que el H1 (`routine_type.title()`), y `kind`/`id`
  salen del registro, como en tablas y vistas. **Deuda menor**: cubrirlo con el banco (PostgreSQL) si se toca.
- `database/storage.md` y `engine-conditions.md`: título = el de `extra_pages`, igual que su H1 (verificado leyendo
  `_site_pages.py`); el test de H1 solo cubre `database/info.md` (SQLite).

## Performance

- Una `PageEntry` por página en memoria y ~150 B por página en el manifiesto. `index_page_titles` repite la
  paginación (barata: agrupa nombres ya ordenados).

## Seguridad

- `mermaid_js_ref`: lista blanca (https con host o ruta relativa sin `..`/`:`/`\\`), YAML con `json.dumps`; 16 casos
  de rechazo en test.
- `title` es texto no confiable sin escapar por diseño; el contrato lo dice. El fichero es JSON (`json.dumps`).
- `keep` no puede borrar nada: solo excluye rutas de la limpieza.

## Tipado

- mypy limpio. `PageEntry` frozen; `publish(..., keep: frozenset[str], pages: Sequence[PageEntry])`.

## Deuda técnica

- `gen_arquitectura_capas.py` reescribe sus tres ficheros con LF en Windows (solo finales de línea): se restauran
  con `git checkout` tras ejecutarlo. Preexistente.

## Veredicto

**APROBADO**.
