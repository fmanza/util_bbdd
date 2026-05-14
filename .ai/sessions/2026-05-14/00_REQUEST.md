# REQUEST

## Session metadata
- id: 2026-05-14
- fecha: 2026-05-14
- rama: develop
- skill: config_review
- fase solicitada: ANÁLISIS + IMPLEMENT (correcciones directas en ficheros de instrucciones IA)

## Solicitud original saneada
Revisar las instrucciones IA usando `config_review.prompt.md` y actualizar inconsistencias.
Preparar mensaje de commit para subir código a GitHub.

## Objetivo operativo de esta sesión
- Detectar y corregir referencias heredadas de `project_copy` en instrucciones IA
- Corregir dato incorrecto de versión Python (`>=3.11` → `>=3.12`) en `SHARED_INSTRUCTIONS.md`
- Crear `sync.instructions.md` (referenciado en 4 ficheros pero inexistente)
- Completar slash commands faltantes en `CLAUDE.md` (`/tech-debt`, `/maturity-assessment`, `/version-closure`)
- Actualizar `.ai/sessions` y preparar commit

## Restricciones explícitas
- No modificar código Python de `src/`
- No crear documentación de producto; solo corregir instrucciones IA
- Aplicar solo cambios directamente necesarios (sin over-engineering)

## Resultado esperado
- 5 ficheros modificados: `SHARED_INSTRUCTIONS.md`, `copilot-instructions.md`, `DOCUMENTATION_STANDARD.md`, `CLAUDE.md`, `technical_doc.prompt.md`
- 1 fichero creado: `.github/instructions/sync.instructions.md`
- `.ai/sessions/2026-05-14/` con artefactos mínimos de trazabilidad
- Mensaje de commit listo para `git commit`
