# VERSION_MANAGEMENT

## Estado
- version objetivo: 0.6.2
- fecha de cierre: 2026-03-26
- rama de trabajo observada: develop
- alcance excluido: docs/v0.6.3

## Artefactos actualizados
- pyproject.toml -> `0.6.2`
- CHANGELOG.md -> entrada `0.6.2`
- README.md -> versión pública, resumen de release y roadmap
- docs/MIGRATION_GUIDE.md -> guía acumulada hacia `0.6.2`
- docs/v0.6.2/RELEASE_NOTES_v0.6.2.md -> notas de release
- .ai/product.md
- .ai/architecture.md
- .ai/glossary.md
- .ai/runtime.md

## Resumen de cambios de release
- cierre documental de la UX HTML offline con SVG inline
- payloads compartidos de resumen y leyenda para Word/HTML
- assets SVG locales para exportación y paginación offline
- ejemplo completo del contrato `imprimir_config`
- hotfix integrado para tooltips de exportación en `Ver todo`

## Commit sugerido
- `docs(release): close v0.6.2 documentation and metadata`

## PR sugerido
- base: `main`
- compare: rama de release con los cambios de v0.6.2
- exclusiones explícitas: `docs/v0.6.3`, `dist_verify/`

## Rollback
- revertir el commit de cierre de release
- restaurar `pyproject.toml`, `CHANGELOG.md`, `README.md` y `docs/v0.6.2/`

## Validación sugerida
- `pytest tests/unit/test_html_generator_offline_assets.py`
- `pytest tests/unit/test_html_generator_diagrams.py`
- `pytest tests/unit/test_doc_generators_helpers.py`
- `pytest tests/unit/test_print_config_manager.py`
- `python -m build`
