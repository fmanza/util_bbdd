# AUDIT_CODE — Grupo B (renderer Markdown)

Revisión del grupo B contra `PLAN_GRUPO_B.md`. Estructura confirmada por el usuario (BC3): `MARKDOWN/{manifest.json, docs/}`.

## Puertas

| Comando | Resultado |
|---|---|
| `ruff format` / `ruff check src tests` | Limpio |
| `mypy src tests/unit/test_protocol_conformance.py` | Sin errores (366 ficheros) |
| `pytest` (shell sin variables del banco) | **7011 passed, 618 skipped** (`build/logs/grupo_b_pytest.txt`); ningún test existente modificado |
| `scripts/gen_arquitectura_capas.py` | Pasa; sin aristas nuevas (`doc → analysis` ya existía) |
| `zensical build --strict` sobre la salida (BC2) | Sin incidencias (a mano y en `test_zensical_strict_build`, `integration`) |

## Condiciones del AUDIT_PLAN

- **BC1** ✅ `test_output_is_byte_identical_between_generations`, `test_regeneration_removes_orphans_and_keeps_foreign_files`
  y `test_foreign_manifest_deletes_nothing` (manifiesto ajeno o con rutas fuera de la carpeta: no borra nada fuera).
- **BC2** ✅ Ver arriba.
- **BC3** ✅ Confirmada por el usuario.

## Hallazgos

| # | Tipo | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|
| B-1 | Calidad | `_text.py`, `_core/mermaid.py` | La herramienta de escritura convirtió ` `/` ` de las regex en caracteres reales, invisibles y que parten líneas en algunas herramientas (el original de `comparar` ya los tenía así) | **Corregido**: secuencias de escape en el código fuente |
| B-2 | Legibilidad para IA | `_text.py` | `_` escapado siempre (`cliente\_id`): ruido en el Markdown en crudo | **Corregido**: solo en extremo de palabra (CommonMark no abre énfasis entre letras) |
| B-3 | Diseño | `markdown_generator.py` `_write_routines` | Dos rutinas con el mismo tipo y nombre (sobrecargas de PostgreSQL) llegan como filas indistinguibles (`nombre, tipo, comentario`): comparten página, como en Word y HTML | Aceptado; anotar en la guía (grupo F) |
| B-4 | Diseño | `_site_pages.py` `ER_LEGEND_ROWS` | La leyenda del Markdown es la de la notación de Mermaid (pata de gallo), no la compartida de Graphviz (colores y direcciones que aquí no existen) | Aceptado (deliberado) |
| B-5 | Integración | util_bbdd_web | `_FORMAT_DIRS` de la web no conoce `markdown` | Pendiente (web, PLAN §6) |
| B-6 | Rendimiento | `generate_document` | Un `render_er` por tabla sobre el snapshot y el `GraphDocument` cacheados; humo de paginación con 450 entradas | Aceptado; medir con el banco en el cierre |

## Veredicto

**APROBADO.**
