# REQUEST

## Session metadata
- id: 2026-06-05-verify-docs
- fecha: 2026-06-05
- rama: develop
- skill: new_feature
- fase solicitada: PLAN → IMPLEMENT

## Solicitud original saneada

1. ¿Se puede incluir descargar del sitio Web con mkdocs y zensical como opción `--verify-tools`?
   Preparar PLAN para su actualización e incorporación a las instrucciones IA.
2. ¿Se puede incluir descargar del sitio Web **generado** con mkdocs y/o zensical (`--verify-build`)?
   Preparar PLAN.
3. Ambos modos (`build` / `serve`) coexistan desde el inicio.
4. Añadir guía de uso a la documentación en `docs/`.

## Objetivo operativo de esta sesión

- Incorporar opción `--verify-tools` (fetch webs oficiales MkDocs, Material, Zensical) en las instrucciones IA de documentación.
- Incorporar opción `--verify-build` con Modo A (`zensical build --strict` → leer `site/`) y Modo B (`zensical serve` → WebFetch localhost) en las instrucciones IA de documentación.
- Actualizar todos los ficheros IA de documentación relevantes para reflejar ambas opciones.
- Crear guía de usuario en `docs/` registrada en `mkdocs.yml`.

## Restricciones explícitas

- Las opciones son siempre opt-in; ninguna se activa automáticamente.
- El agente no modifica ficheros basándose solo en hallazgos del HTML; propone cambios y espera confirmación.
- No delegar generación de contenido a LLMs o APIs de IA externas (solo consulta de referencia).
- Modo B requiere confirmación del usuario antes de arrancar el servidor.

## Resultado esperado

- `CLAUDE.md` con Fase 7 en flujo de fases y §6 de contrato documental actualizado.
- `.github/agents/documentation-generator.agent.md` con Paso 0 (`--verify-tools`) y Paso 7 (`--verify-build`).
- `.github/instructions/docs.instructions.md` con sección completa para ambas opciones.
- `.github/DOCUMENTATION_STANDARD.md` con URLs de referencia en §2.1 y tabla §5 actualizada.
- `docs/doc_verification_guide.md` (nueva guía Arquetipo 3) registrada en `mkdocs.yml`.
