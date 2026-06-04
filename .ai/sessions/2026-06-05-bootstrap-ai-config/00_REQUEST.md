# REQUEST

## Session metadata
- id: 2026-06-05-bootstrap-ai-config
- fecha: 2026-06-05
- rama: develop
- skill: new_feature
- fase solicitada: PLAN + AUDIT_PLAN → IMPLEMENT → VERSION (commit)

## Solicitud original saneada

El usuario pide recomendar el mejor método para copiar las instrucciones IA completas
(prompt, agentes, o lo que proceda) de este proyecto VS Code a **otro proyecto VS Code**,
teniendo en cuenta:

- Proponer el mejor método de invocación (origen → destino o viceversa) indicando las rutas.
- El contexto del nuevo proyecto debe ser obligatorio: definir partes mínimas y opcionales.
- Las plataformas en uso son **Gemini, Copilot y Claude Code** (más tarde se confirma **Cursor**: "Todo").
- El destino puede ser de **otro lenguaje y arquitectura**; al copiar debe analizarse el contenido
  para actualizar la información.
- Fuente fiable para la copia: este proyecto (`util_bbdd`).
- Primero proponer PLAN y AUDIT_PLAN sin ejecutar nada.

Respuestas del usuario a las condiciones del AUDIT_PLAN:
1. Confirmar lenguaje/arquitectura del destino → SÍ (pasa a ser parámetro de entrada del prompt).
2. Plataformas activas → **Todo** (Claude, Gemini, Copilot, Cursor).
3. Aceptar que prompts/commands con comandos embebidos se revisan (no verbatim puro) → Aceptado.
4. ¿Crear el prompt `bootstrap_ai_config` en este repo? → **Sí, copiar en este repo.**
- Indicación adicional: "Actualizar la documentación, sobre todo incluir Método y dirección de la llamada."
- Orden final: **IMPLEMENT** y luego **preparar commit** y **actualizar documentación con los datos de esta conversación**.

## Objetivo operativo de esta sesión
- Crear un prompt reutilizable de bootstrap de configuración IA multiplataforma en el origen.
- Documentar el **Método y dirección de la llamada** (modelo PULL) en los entry points de las 4 plataformas.
- Definir contexto obligatorio vs. opcional para el proyecto destino.
- Registrar la sesión con artefactos de trazabilidad.

## Restricciones explícitas
- No ejecutar la copia a ningún proyecto destino en esta sesión (solo crear el instalador + docs).
- El lenguaje/arquitectura del destino no se fija: es parámetro de entrada del prompt.
- Mantener DRY: el detalle largo vive solo en el prompt; los entry points llevan punteros breves.

## Resultado esperado
- `.github/prompts/bootstrap_ai_config.prompt.md` creado.
- Documentación sincronizada en CLAUDE.md, GEMINI.md, copilot-instructions.md, .cursorrules,
  AGENTS.md y la tabla de gobernanza de SHARED_INSTRUCTIONS.md.
- Commit en `develop` con los 7 ficheros.
- Carpeta `.ai/sessions/2026-06-05-bootstrap-ai-config/` con artefactos mínimos de trazabilidad.
