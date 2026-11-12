# AUDIT_CODE — 2026-11-12-doc-filtro-relaciones

Commit revisado: `4517d7e8` (feat(doc)).

## Verificación

| Comprobación | Resultado |
|---|---|
| `python -m pytest` | 7118 passed, 618 skipped, 0 failed (`build/logs/doc_filter_5_5_0_pytest.txt`) |
| `ruff check` / `ruff format` | limpios |
| `mypy src tests/unit/test_protocol_conformance.py` | sin errores (373 ficheros) |
| `zensical build --strict` (proyecto) | sin avisos |
| Salida Markdown filtrada | `zensical build --strict` sin avisos; 13 enlaces, 0 rotos |
| `scripts/gen_arquitectura_capas.py` | coincide con el código (solo cambios de fin de línea, descartados) |

## Revisión

- **Punto único de filtrado**: `DocumentationBootstrap.build`; los renderers solo ven lo documentado. La frontera se
  calcula con una consulta de FK por lotes (ADR-003) solo si hay filtro con `frontera`.
- **Compatibilidad**: sin filtro, `catalog.json` y `manifest.json` no cambian; `DocumentationResult.frontier`,
  `DocumentationBootstrapState`/`DocumentationSession` y `PageContext` reciben campos con valor por defecto.
- **Cambio visible**: el texto del resumen de niveles (Word, HTML, Markdown) y la nueva lista «Referenciada por»
  cambian el contenido de las páginas, no los `hash` de los objetos.
- **Limitación aceptada**: una FK a una tabla de otro schema, con filtro activo, se marca «excluida por el filtro».
- **Limitación aceptada**: `filtro.frontera` se convierte con `bool()`, como el resto de banderas de `imprimir`.

Veredicto: **APROBADO**.
