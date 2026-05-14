# REQUEST

## Session metadata
- id: 2026-05-14-docs-audit
- fecha: 2026-05-14
- rama: develop
- skill: maturity_assessment → version_closure
- fase solicitada: AUDIT (Documentation Reviewer) + IMPLEMENT (todos los hallazgos)

## Solicitud original saneada
1. `@Documentation Reviewer` — auditar toda la documentación del proyecto util_bbdd.
2. `Implementamos todos` — implementar los 23 hallazgos retornados por el auditor.
3. Actualizar `.ai/sessions` y preparar mensaje de commit.

## Objetivo operativo de esta sesión
- Auditar coherencia entre docs/ y el código real en src/util_bbdd/
- Corregir los 5 hallazgos críticos (Nivel 1) detectados por Documentation Reviewer
- Corregir los hallazgos importantes (Nivel 2) sobre referencias rotas y contenido inexacto
- Actualizar mkdocs.yml para excluir páginas huérfanas
- Registrar trazabilidad completa y preparar commit message

## Restricciones explícitas
- No modificar código Python en src/
- No crear documentación de producto nueva (solo corregir la existente)
- No hacer over-engineering ni refactors de estructura docs/

## Resultado esperado
- 11 artefactos modificados: INSTALLATION.md, EXCEPTIONS.md, API_REFERENCE.md,
  api/exceptions.md, api/index.md, examples/example-connect-introspect.md,
  functional/managers-sync.md, TROUBLESHOOTING.md, legacy-versions.md,
  mkdocs.yml, pyproject.toml + README.md (versión)
- 1 artefacto modificado fuera de docs/: .github/SHARED_INSTRUCTIONS.md
- `.ai/sessions/2026-05-14-docs-audit/` con artefactos de trazabilidad
- Mensaje de commit listo para `git commit`
