# TRACEABILITY

## Session metadata
- id: 2026-06-08-arquetipo8-normativa
- fecha: 2026-06-08
- rama: develop
- skill: documentation
- fase: IMPLEMENT

## Prompt issued
Actualizar `.ai/sessions`. Preparar mensaje para subir código a GitHub. Solo de este proyecto.

## Context supplied
- `.github/DOCUMENTATION_STANDARD.md` — diff HEAD (añadido §3.8 Arquetipo 8 + fila tabla §4.2)
- `.github/agents/documentation-generator.agent.md` — diff HEAD (paso 0 normativa + sección 4)
- `.github/agents/documentation-reviewer.agent.md` — diff HEAD (item 10 normativa condicional)
- `.github/prompts/normative_traceability.prompt.md` — fichero nuevo (sin trazar en git)

## AI output summary
- Revisado `git diff HEAD` sobre los 3 archivos modificados y el nuevo prompt.
- Identificados 4 artefactos: 1 nuevo (`normative_traceability.prompt.md`) + 3 actualizaciones.
- Creado directorio de sesión `.ai/sessions/2026-06-08-arquetipo8-normativa/`.
- Creado `TRACEABILITY.md` (este fichero) con resumen de la sesión.
- Actualizado `INDEX.md` con entrada de la sesión.
- Preparado `GITHUB_COMMIT_MESSAGE.md` con mensaje conventional commit.

## Artefactos generados

| Artefacto                               | Ruta                                                              | Estado     |
|-----------------------------------------|-------------------------------------------------------------------|------------|
| Arquetipo 8 (§3.8)                      | `.github/DOCUMENTATION_STANDARD.md`                              | modificado |
| Detección normativa (paso 0 + §4)       | `.github/agents/documentation-generator.agent.md`                | modificado |
| Revisión normativa (item 10)            | `.github/agents/documentation-reviewer.agent.md`                 | modificado |
| Prompt trazabilidad normativa           | `.github/prompts/normative_traceability.prompt.md`               | nuevo      |
| TRACEABILITY sesión                     | `.ai/sessions/2026-06-08-arquetipo8-normativa/TRACEABILITY.md`   | nuevo      |
| GITHUB_COMMIT_MESSAGE                   | `.ai/sessions/2026-06-08-arquetipo8-normativa/GITHUB_COMMIT_MESSAGE.md` | nuevo |

## Directrices para Futuras IAs

- **[docs/normativa]**: El Arquetipo 8 es **condicional** — solo aplica si el proyecto referencia normativa de obligado cumplimiento. util_bbdd actualmente no lo requiere. No crear `docs/normativa/` salvo que se incorpore normativa real (RGPD, LOPD-GDD, etc.).
- **[DOCUMENTATION_STANDARD]**: §3.8 es Arquetipo 8 (Trazabilidad Normativa); §3.9 es el estándar de sección Guías. El renumerado fue deliberado para mantener arquetipos agrupados (1-8) antes del §3.9 de convenciones.
- **[prompts]**: `normative_traceability.prompt.md` existe en `.github/prompts/` pero NO está documentado en `mkdocs.yml` (es un prompt de agente, no un documento público del sitio). No añadirlo a nav.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. Los 4 artefactos son ficheros de gobernanza IA/docs; no requieren tests ni build.
