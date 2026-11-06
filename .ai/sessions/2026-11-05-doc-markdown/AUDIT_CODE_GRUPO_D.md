# AUDIT_CODE — Grupo D (mapa de trazabilidad)

Revisión contra `PLAN_GRUPO_D.md`. Decisiones del usuario: trazabilidad por columna incluida y validación estricta.

## Puertas

| Comando | Resultado |
|---|---|
| `ruff format` / `ruff check src tests` | Limpio |
| `mypy src tests/unit/test_protocol_conformance.py` | Sin errores (369 ficheros) |
| `pytest` (shell sin variables del banco) | **7039 passed, 618 skipped** (`build/logs/grupo_d_pytest.txt`) |
| `zensical build --strict` con mapa (anclas de columna, `traceability.md` en la `nav`) | Sin incidencias (`test_zensical_strict_build_with_trace_map`, `integration`) |

## Hallazgos

| # | Tipo | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|
| D-1 | Calidad | `_trace.py` `traceability_page` | «Sin trazar» comparaba dataclasses con `in` sobre una lista: O(n²) con miles de objetos | **Corregido**: conjunto de `id()` |
| D-2 | Claridad | `_trace.py` `match_columns` | El motivo de una columna sin casar decía «no se documenta ningún objeto» | **Corregido**: «la tabla no tiene ninguna columna con ese nombre» |
| D-3 | Diseño | `markdown_generator.py` `_Tracer` | `trace` se añade al registro **después** de calcular `hash`: cambiar una traza no cambia el hash (test `test_trace_does_not_change_hash_and_without_map_nothing_changes`) | Conforme al plan (DT2) |
| D-4 | Diseño | `database_documentation.py` | Validación en la fachada tras `settings()` con `TraceMap.load`, sin tocar `DocumentationBootstrap` (DT1) | Conforme al plan |
| D-5 | Seguridad | `_trace.py` `reference` | Solo `http(s)` sin espacios se enlaza (con paréntesis codificados); `javascript:`, `data:` y rutas, como *code span*; `\|` escapado en tablas | Tests `test_reference_only_links_http_urls`, `test_code_span_with_backticks_and_pipes` |
| D-6 | Diseño | Anclas de columna | Solo se enlazan si la sección «Columnas» y `column_anchors` están activas; si no, el nombre va como texto (sin enlaces rotos en `--strict`) | Conforme |

## Veredicto

**APROBADO.**
