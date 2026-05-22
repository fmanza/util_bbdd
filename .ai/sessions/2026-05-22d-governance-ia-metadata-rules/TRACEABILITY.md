# TRACEABILITY

## Session metadata
- id: 2026-05-22d-governance-ia-metadata-rules
- fecha: 2026-05-22
- rama: develop
- skill: config_review
- fase: AUDIT_CODE + VERSION (exploración + formalización + propagación de gobernanza)

## Prompt issued
> "Revisar el módulo `src\util_bbdd\doc` y decirme de donde salen las consultas para documentar"
> "Incluir las instrucciones IA de la FASE 2 — Directrices para Futuras IAs"
> "buscar el mejor sitio para incluir [REGLAS #1–#6 de metadata access]"
> "Completar el body de REGLA #6 — JERARQUÍA DE DEPENDENCIAS (sin inversiones)"
> "Actualizar .ai\sessions / Preparar mensaje para subir código a GitHub"

## Context supplied
- Conversación activa con historial comprimido de sesiones anteriores del día
- `.github/instructions/architecture.instructions.md` (selección activa)
- `.ai/sessions/TEMPLATE/TRACEABILITY.md`
- `.ai/sessions/2026-05-22-metadata-sql-canonical/TRACEABILITY.md`
- `.github/SHARED_INSTRUCTIONS.md`

## AI output summary
1. Explorado `src/util_bbdd/doc/` — cadena de acceso a queries identificada:
   `data/sql_queries.json` → `QueryRegistry.load()` → `SyncDatabaseManager` →
   `SyncDatabaseManagerAdapter` → módulo `doc/`
2. Confirmado que `doc/` y `migrate/` usan query sets completamente distintos
   (`{var}` f-string vs. `%(name)s` DB-API 2.0); no hay solapamiento.
3. Añadida sección `## Directrices para Futuras IAs` (con placeholder + instrucción)
   a `TEMPLATE/TRACEABILITY.md`.
4. Poblada la sección en `2026-05-22-metadata-sql-canonical/TRACEABILITY.md`
   con 6 directivas verificables de esa sesión.
5. Propagado el concepto a 7 ficheros de gobernanza IA:
   - `SHARED_INSTRUCTIONS.md`: subsección en flujo VERSION + fila `.ai/sessions/TEMPLATE/` en tabla gobernanza
   - `sync.instructions.md`: sección §6 con checklist TRACEABILITY al cierre
   - `CLAUDE.md`: `/version-closure` Fase 3 menciona poblar directrices
   - `.github/agents/version-closer.agent.md`: paso 4 nuevo + sección en formato de salida
   - `.github/copilot-instructions.md`: tabla de agentes, Version Closer actualizado
   - `.github/prompts/version_closure.prompt.md`: item directrices añadido
6. Añadidas REGLAS #1–#6 de metadata access a `architecture.instructions.md`
   (punto único de acceso, consumir `SyncMetadataProvider`, prohibir duplicar SQL,
   contratos antes que implementaciones, validar antes de crear, jerarquía de dependencias).
7. Completado el body de REGLA #6 con diagrama ASCII de 3 niveles y 6 reglas
   explícitas de dirección de imports.
8. Creado TRACEABILITY de esta sesión + actualizado INDEX.md.

## Artefactos generados

| Artefacto                                         | Ruta                                                                      | Estado     |
|---------------------------------------------------|---------------------------------------------------------------------------|------------|
| TEMPLATE actualizado                              | `.ai/sessions/TEMPLATE/TRACEABILITY.md`                                   | modificado |
| Directrices sesión anterior                       | `.ai/sessions/2026-05-22-metadata-sql-canonical/TRACEABILITY.md`          | modificado |
| Subsección Directrices IAs + gobernanza           | `.github/SHARED_INSTRUCTIONS.md`                                          | modificado |
| Checklist §6 TRACEABILITY                         | `.github/instructions/sync.instructions.md`                               | modificado |
| /version-closure Fase 3                           | `CLAUDE.md`                                                               | modificado |
| Paso 4 + sección output format                    | `.github/agents/version-closer.agent.md`                                  | modificado |
| Tabla agentes Version Closer                      | `.github/copilot-instructions.md`                                         | modificado |
| Item directrices                                  | `.github/prompts/version_closure.prompt.md`                               | modificado |
| REGLAS #1–#6 metadata access                      | `.github/instructions/architecture.instructions.md`                       | modificado |
| TRACEABILITY sesión 2026-05-22d                   | `.ai/sessions/2026-05-22d-governance-ia-metadata-rules/TRACEABILITY.md`   | creado     |
| INDEX.md actualizado                              | `.ai/sessions/INDEX.md`                                                   | modificado |

## Directrices para Futuras IAs

**[doc/ — SQL canónico]**: Las queries de `doc/` provienen exclusivamente de
`data/sql_queries.json` cargado por `QueryRegistry`. NO están en `metadata/`.
No unificar los query sets de `doc/` y `migrate/`.

**[parámetros SQL]**: `doc/` usa placeholders `{var}` (interpolación tipo f-string
en `QueryRegistry`); `migrate/extractors/` usa `%(name)s` (DB-API 2.0). Son formatos
incompatibles — no intercambiar.

**[Directrices para Futuras IAs — template]**: La sección `## Directrices para Futuras IAs`
es obligatoria en todo TRACEABILITY. El checklist de cierre está en
`.github/instructions/sync.instructions.md` §6. El agente Version Closer es responsable
de poblarla antes del commit de cierre.

**[metadata access — reglas canónicas]**: REGLAS #1–#6 en
`.github/instructions/architecture.instructions.md` § "Reglas de acceso a metadatos".
Aplican a cualquier módulo de `src/util_bbdd/` que necesite metadatos de esquema.
REGLA #3 falla AUDIT_CODE si `INFORMATION_SCHEMA`/`all_tables` aparecen fuera de `metadata/`.

**[jerarquía de dependencias]**: 3 niveles — Foundation (Level 1), Core Services (Level 2),
Domain Logic (Level 3). Imports solo hacia abajo. Level 2 NUNCA importa de Level 3.
AUDIT_CODE rechaza cualquier inversión. Ver REGLA #6.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit pendiente con todos los ficheros modificados (ver artefactos generados)
