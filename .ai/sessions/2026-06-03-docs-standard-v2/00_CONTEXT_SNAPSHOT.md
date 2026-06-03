# CONTEXT SNAPSHOT

## Estado del repositorio al inicio
- rama: `develop`
- último commit: `8964630 feat(bulk): corregir y reforzar paralelismo en ParallelBulkLoader y añadir HashPartitioner`
- versión `pyproject.toml`: 0.10.0
- working tree: limpio (sin cambios sin commitear al inicio de la sesión)

## Inventario documental al inicio
| Categoría | Ruta | Archivos | Arquetipo previo |
|---|---|---|---|
| Funcional | `docs/functional/` | 19 | v1 (4 secciones) |
| Técnica manual | `docs/api/` | 24 | v1 (4 secciones) |
| Autodoc | `docs/api/` | 6 (`index`, `managers`, `comparator`, `reporters`, `bulk`, `exceptions`) | mkdocstrings |
| Ejemplos | `docs/examples/` | 18 .md + 18 .py | v1 (4 secciones) |
| Guías | `docs/` raíz | 18 | v1 (4 secciones) |
| ADR | `docs/adr/` | 1 | estructura libre |

## Lenguaje detectado (Gate G0)
- Python: 337 archivos `.py` en `src/`
- Java: 0
- TypeScript: 0
- **Conclusión**: proyecto Python-only; handler `mkdocstrings.python` (Google Style) ya configurado.

## Build inicial
- `mkdocs build --strict`: **99 warnings** (todos por links a `.github/` en las 4 guías IA
  ubicadas en `docs/examples/` — se resolvieron al mover esas guías a `docs/` raíz).

## Gate G0
- **Veredicto: GO** — el estándar v2 es implementable; lenguaje confirmado Python-only;
  los 99 warnings iniciales tienen causa identificada (guías IA mal ubicadas).
