# REQUEST

## Session metadata
- id: 2026-05-02
- fecha: 2026-05-02
- rama: develop
- skill: new_feature (documentation)
- fase solicitada: Fases 1-6 de documentación estructurada (Documentation Generator)

## Solicitud original saneada

Completar documentación pública del proyecto util_bbdd siguiendo el flujo 6-fases del agente Documentation Generator especificado en copilot-instructions.md (líneas 146-157):

1. Inventariar módulos reales en src/util_bbdd/ y clasificarlos
2. Mapeo funcional con functional_doc.prompt.md por módulo sin doc o desactualizado
3. Documentación técnica con technical_doc.prompt.md y Mermaid apropiado
4. Ejemplos verificables en docs/examples/ para módulos sin ejemplo reproducible
5. Sincronizar mkdocs.yml
6. Revisión final: Markdown, enlaces y Mermaid; recomendar mkdocs build

Restricción: No inventar módulos ni capacidades; no usar APIs externas.

## Objetivo operativo de esta sesión

- **Objetivo 1**: Completar Fases 1-6 para módulo piloto SyncDatabaseManager (managers/sync_mgr.py)
- **Objetivo 2**: Generar documentación funcional, técnica y ejemplos verificables
- **Objetivo 3**: Sincronizar mkdocs.yml con nuevas referencias
- **Objetivo 4**: Validar con mkdocs build que documentación compila sin errores

## Restricciones explícitas

- Solo módulos que existen realmente en src/util_bbdd/
- Ejemplos con código Python verificable, sin APIs externas
- Diagramas Mermaid válidos y renderizables
- Documentación debe consistir con estructura canónica (functional_doc.prompt.md, technical_doc.prompt.md)
- No inventar drivers o capacidades; validar contra código real

## Resultado esperado

- 3 archivos nuevos de documentación:
  - `docs/functional/managers-sync-session-lifecycle.md`
  - `docs/api/managers-sync-technical.md`
  - `docs/examples/example-connect-introspect.md`
- 1 archivo actualizado:
  - `mkdocs.yml` (3 nuevas entradas de navegación)
- 1 reporte de auditoría final:
  - `docs/FASE6_FINAL_AUDIT_REPORT.md`
- mkdocs build exitoso sin errores fatales
