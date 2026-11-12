# TRACEABILITY

## Session metadata
- id: 2026-11-12-doc-filtro-relaciones
- fecha: 2026-11-12
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (L1, L2, L3, L5) + AUDIT_CODE + VERSION (v5.5.0)

## Prompt issued
Ver [00_REQUEST.md](00_REQUEST.md): comentarios de util_bbdd_web sobre la documentación Markdown y cuatro mejoras
propuestas para util_bbdd.

## Context supplied
- Código de `doc/` (orquestador, renderers Markdown, `PrintConfigManager`) y `analysis/mermaid_er.py`.
- util_bbdd_web: `backend/app/integrations/util_bbdd/documentation.py`, `domain/runs/operations.py` y el visor
  `frontend/src/features/runs/documentation/`.

## AI output summary
- Diagnóstico verificado (ver [PLAN.md](PLAN.md)): la profundidad era correcta; faltaban las FK entrantes, el README
  y el filtro; la 5.4.0 ya estaba publicada; la comparación entre entornos ya existía.
- `4517d7e8` feat(doc): `imprimir["filtro"]` con frontera, «Referenciada por», `README.md` y «Niveles por sentido»;
  21 tests en `tests/unit/test_doc_table_filter.py`; API, guía (§3.8, §3.9), ADR-006 y CHANGELOG.
- AUDIT_CODE: APROBADO ([AUDIT_CODE.md](AUDIT_CODE.md)).
- VERSION: release v5.5.0, wheel en `dist/`, tag anotado local `v5.5.0`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN / AUDIT_PLAN | `.ai/sessions/2026-11-12-doc-filtro-relaciones/` | aprobados |
| Funcionalidad | `4517d7e8` | completado |
| AUDIT_CODE | `AUDIT_CODE.md` | APROBADO |
| Release | `release: v5.5.0` + tag local | pendiente de push (usuario) |

## Traspaso a util_bbdd_web

- `imprimir["filtro"] = {"incluir": [...], "excluir": [...], "frontera": bool}`; patrón no válido →
  `DocumentationConfigError` al construir `DatabaseDocumentation` (validar también en el formulario).
- `DocumentationResult.frontier` (tupla) y `manifest.json` → `filter` (`include`, `exclude`, `frontier`) cuando hay
  filtro.
- `README.md` en la raíz de `MARKDOWN/`: está en `manifest.files`, no en `pages` (el árbol del visor no cambia).
- El resumen de los diagramas dice «Niveles por sentido».

## Directrices para Futuras IAs
- **[doc]**: el filtro de tablas se aplica solo en `DocumentationBootstrap.build`; un formato nuevo no debe volver a
  filtrar. `TableFilter` (`doc/domain/table_filter.py`) es la única implementación de la coincidencia de patrones.
- **[doc/markdown]**: `catalog.json`/`manifest.json` solo escriben `filter`/`frontier` con filtro, para que las
  salidas sin filtro sigan idénticas byte a byte a las de 5.4.0.
- **[doc/markdown]**: `README.md` va fuera de `docs/`; `test_pages_list_every_markdown_page_once` compara solo los
  `.md` de `docs/`.
- **[herramientas]**: el `egg-info` de la instalación editable puede quedarse en una versión antigua (salía 0.32.2 en
  `mkdocs.yml` y README): `pip install -e . --no-deps` antes de generar ejemplos.
- **[herramientas]**: el heredoc de bash quita un nivel de `\` en scripts de Python; para cadenas con barras, usar
  Edit/Write.

## Veredicto final
Veredicto: CLOSED (v5.5.0)
Pendientes al cierre:
- Push de `develop`, del tag `v5.5.0` y ff de `main`; release en GitHub con el wheel y el `.sha256` (usuario).
- L4 (datos de referencia, 5.6.0), L6 (especificación + JSON Schema) y comparación offline entre catálogos.
