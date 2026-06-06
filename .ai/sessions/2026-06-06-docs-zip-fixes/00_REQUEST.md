# REQUEST

## Session metadata
- id: 2026-06-06-docs-zip-fixes
- fecha: 2026-06-06
- rama: develop
- skill: IMPLEMENT + AUDIT_CODE → VERSION
- fase: Corrección y validación de plugin MkDocs

## Solicitud original

El usuario reporta **error de Pylance** en `docs_build_plugin.py`:
```
reportIncompatibleMethodOverride: El método "on_post_build" sobrescribe 
la clase "BasePlugin" de forma incompatible
```

Contexto:
- Plugin implementado en sesión anterior (`2026-06-05-docs-offline-zip`)
- Plugin **funciona correctamente** en tiempo de ejecución (`mkdocs build` genera ZIP sin errores)
- Error es **falso positivo** de Pylance due a type stubs de mkdocs

Solicitudes adicionales:
1. Actualizar `.ai\sessions` con la sesión actual
2. Preparar mensaje para subir código a GitHub (commit message)

## Objetivo operativo

1. **Resolver todos los errores de Pylance** en `docs_build_plugin.py`
2. **Validar que plugin funciona** tras correcciones
3. **Integrar plugin en bootstrap** (`.github/prompts/bootstrap_ai_config.prompt.md`)
4. **Sincronizar documentación IA** (SHARED_INSTRUCTIONS.md, CLAUDE.md, copilot-instructions.md, GEMINI.md)
5. **Registrar sesión** en `.ai/sessions/`
6. **Preparar commit message** Conventional Commits para GitHub

## Restricciones explícitas

- Mantener funcionalidad: plugin debe seguir generando ZIP tras correcciones
- Compatibilidad: emojis reemplazados para soportar Windows cp1252
- DRY: documentación sincronizada sin duplicación
- Type safety: Pylance sin errores o warnings innecesarios

## Resultado esperado

- ✅ `docs_build_plugin.py` sin errores de Pylance
- ✅ `.github/prompts/bootstrap_ai_config.prompt.md` actualizado (Capa B + matriz multi-lenguaje)
- ✅ Docs IA sincronizadas: `.github/SHARED_INSTRUCTIONS.md`, `CLAUDE.md`, `copilot-instructions.md`, `GEMINI.md`
- ✅ Sesión registrada con trazabilidad
- ✅ Commit message preparado (Conventional Commits)
- ✅ ZIP validado localmente (~2.15 MB)

## Status
- IMPLEMENT: ✅ Completado
- AUDIT_CODE: ✅ Completado (sin errores)
- VERSION: ⏳ Pendiente (commit message + push)
