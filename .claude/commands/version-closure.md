# version_closure

Cierre de versión o de sesión de trabajo.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/agents/version-closer.agent.md` — rol, restricciones y ficheros que puede editar
2. `.github/prompts/version_closure.prompt.md` — contrato de salida (orden y contenido)
3. `.github/instructions/sync.instructions.md` — checklist de sincronización de VERSION

## Inputs requeridos (OBLIGATORIO completar TODOS)

- [ ] **Cambios resumidos**: qué se implementó (feature, fix, refactor, etc.)
- [ ] **Versión objetivo**: `vX.Y.Z`
- [ ] **Archivos modificados**: módulos o componentes que cambiaron
- [ ] **Sesión**: carpeta `.ai/sessions/<fecha>-<slug>/` a cerrar

**⚠️ VALIDACIÓN**: Si falta alguno, decláralo como supuesto explícito antes de continuar.

## Reglas de ejecución

- Edita solo `CHANGELOG.md` y el `TRACEABILITY.md` de la sesión; el commit se propone.
- No cierres sin poblar `## Directrices para Futuras IAs`.

## Ejemplo de entrada

```text
/version-closure

Cambios: exportación de informes robusta en dump, bulk, comparar y doc
Versión: v0.18.3
Archivos: src/util_bbdd/dump/, src/util_bbdd/bulk/, src/util_bbdd/_core/export_safety.py
Sesión: .ai/sessions/2026-09-27d-export-safety/
```
