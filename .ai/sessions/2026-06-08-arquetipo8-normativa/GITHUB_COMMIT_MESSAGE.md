# GitHub Commit Message

## Rama
`develop`

## Archivos a incluir en el commit

```
.github/DOCUMENTATION_STANDARD.md
.github/agents/documentation-generator.agent.md
.github/agents/documentation-reviewer.agent.md
.github/prompts/normative_traceability.prompt.md
.ai/sessions/2026-06-08-arquetipo8-normativa/TRACEABILITY.md
.ai/sessions/2026-06-08-arquetipo8-normativa/GITHUB_COMMIT_MESSAGE.md
.ai/sessions/INDEX.md
```

## Mensaje de commit

```
docs(standard): añadir Arquetipo 8 — Trazabilidad Normativa (condicional)

Introduce el Arquetipo 8 en DOCUMENTATION_STANDARD.md (§3.8) para proyectos
con normativa de referencia (leyes, decretos, directivas UE, normas UNE).
El arquetipo es condicional: solo aplica si el proyecto declara normativa
de obligado cumplimiento en product.md o README; util_bbdd queda exento.

Cambios:
- DOCUMENTATION_STANDARD.md §3.8: estructura Arquetipo 8, leyenda cobertura
  (✅/⚠️/❌/🔍), sección MkDocs "Normativa", cuándo crear/actualizar,
  restricciones estrictas; §3.8 Guías renumerado a §3.9; fila "Normativa"
  añadida a tabla de páginas opcionales (§4.2).
- documentation-generator.agent.md: paso 0 (detección normativa previa) +
  sección "4. Documentación normativa" con flujo condicional.
- documentation-reviewer.agent.md: ítem 10 para revisión normativa condicional.
- normative_traceability.prompt.md (nuevo): prompt de generación/actualización
  de docs/normativa/<codigo>_traceability.md con proceso en 5 pasos.
```

## Comando git sugerido

```bash
git add .github/DOCUMENTATION_STANDARD.md \
        .github/agents/documentation-generator.agent.md \
        .github/agents/documentation-reviewer.agent.md \
        .github/prompts/normative_traceability.prompt.md \
        .ai/sessions/2026-06-08-arquetipo8-normativa/ \
        .ai/sessions/INDEX.md

git commit -m "docs(standard): añadir Arquetipo 8 — Trazabilidad Normativa (condicional)

Introduce el Arquetipo 8 en DOCUMENTATION_STANDARD.md (§3.8) para proyectos
con normativa de referencia (leyes, decretos, directivas UE, normas UNE).
El arquetipo es condicional: solo aplica si el proyecto declara normativa
de obligado cumplimiento en product.md o README; util_bbdd queda exento.

Cambios:
- DOCUMENTATION_STANDARD.md §3.8: estructura Arquetipo 8, leyenda cobertura
  (✅/⚠️/❌/🔍), sección MkDocs Normativa, cuándo crear/actualizar,
  restricciones estrictas; §3.8 Guías renumerado a §3.9; fila Normativa
  añadida a tabla de páginas opcionales (§4.2).
- documentation-generator.agent.md: paso 0 (detección normativa previa) +
  sección 4 Documentación normativa con flujo condicional.
- documentation-reviewer.agent.md: ítem 10 para revisión normativa condicional.
- normative_traceability.prompt.md (nuevo): prompt de generación/actualización
  de docs/normativa/<codigo>_traceability.md con proceso en 5 pasos."
```
