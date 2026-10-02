# Prompt: version_closure (Python library)

Cierre de versión o de sesión de trabajo. Agente ejecutor: `.github/agents/version-closer.agent.md`.

## Inputs requeridos
- **Cambios resumidos**: qué se implementó (feature, fix, refactor…)
- **Versión objetivo**: `vX.Y.Z` (consultar `pyproject.toml` y `CHANGELOG.md`)
- **Archivos modificados**: módulos o componentes que cambiaron
- **Sesión**: carpeta `.ai/sessions/<fecha>-<slug>/` cuyo `TRACEABILITY.md` se cierra

Si falta alguno, decláralo como supuesto explícito antes de continuar.

## Devuelve en este orden
1. **Commit message** — Conventional Commits con los tipos de `SHARED_INSTRUCTIONS.md` § «Formato de commits»;
   para releases, `release: vX.Y.Z - <descripción breve>`.
2. **Changelog** — cambios por módulo (`Added` / `Changed` / `Fixed` / `Removed` / `Deprecated`), con archivos o clases afectadas.
3. **Impacto en API pública** — cambios de firma, parámetros o comportamiento observable; deprecaciones.
4. **Migraciones** — cambios de esquema, configuración o contratos que requieren acción del consumidor.
5. **Compatibilidad** — motores afectados y versiones de Python (rango de `pyproject.toml`).
6. **Rollback** — pasos concretos para revertir y riesgos del rollback.
7. **Checklist final**:
   - [ ] Comandos de `SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo» en verde (`ruff`, `mypy`, `pytest`, `python -m build`)
   - [ ] Checklist de `.github/instructions/sync.instructions.md` completo (CHANGELOG ↔ `pyproject.toml`, `zensical build --strict`)
   - [ ] `## Directrices para Futuras IAs` del `TRACEABILITY.md` de la sesión poblada
8. **Pruebas ejecutadas o sugeridas** — solo las realmente ejecutadas cuentan como ejecutadas.
9. **Directrices para futuras IAs** — hechos descubiertos durante la sesión (puntos canónicos,
   decisiones de diseño, patrones nombrados, lecciones de herramientas) que pueblan la
   sección `## Directrices para Futuras IAs` del `TRACEABILITY.md` de la sesión.
   Formato: `**[área]**: <hecho verificable>`.

## Reglas
- No inventes pruebas ejecutadas ni archivos modificados.
- El agente solo escribe `CHANGELOG.md`, el `TRACEABILITY.md` de la sesión y los campos de versión de
  `.github/instructions/sync.instructions.md` § 4; el commit se propone, no se ejecuta.
