# Instrucciones para Gemini Code Assist — util_bbdd

Este fichero proporciona especialización para Gemini Code Assist al trabajar con el repositorio `util_bbdd`.

---

## ⚠️ Contexto previo obligatorio

- **`.github/SHARED_INSTRUCTIONS.md`** — Fuente canónica: arquitectura de util_bbdd, SOLID, calidad,
  comandos, documentación, flujo de trabajo, Conventional Commits. **Esta es la base** y se importa:

@./.github/SHARED_INSTRUCTIONS.md

- **Este fichero** — Especialización para Gemini Code Assist únicamente.

---

## Flujo de Trabajo Recomendado

Para cambios estructurados, sigue el ciclo de vida definido en el proyecto:

1. **PLAN**: Analizar el objetivo, alcance y riesgos. Contrastar con el código real antes de proponer cambios.
2. **AUDIT_PLAN**: Verificar la viabilidad del plan y detectar expansiones de alcance no deseadas.
3. **IMPLEMENT**: Ejecutar los cambios aplicando los estándares de calidad del proyecto.
4. **AUDIT_CODE**: Revisión técnica independiente (bugs, edge cases, contratos, cobertura).
5. **VERSION**: Cierre de versión, actualización de CHANGELOG y documentación de rollback.

Los prompts de cada flujo están en `.github/prompts/` (`new_feature`, `hotfix`, `refactor`,
`audit_code`, `version_closure`…) y los roles en `.github/AGENTS.md`.

---

## Reglas específicas para Gemini

- **Tipado**: type hints en las funciones y métodos públicos nuevos; el código debe pasar `mypy` con la
  configuración de `pyproject.toml` (no uses `--strict`: no es el perfil del proyecto).
- **Estilo, logging, f-strings y excepciones**: aplica `SHARED_INSTRUCTIONS.md` § «Principios de diseño»
  y la jerarquía de `util_bbdd._core.exceptions`.
- **Comandos**: usa exactamente los de `SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo».
- Si una instrucción contradice `pyproject.toml` o el código real, prioriza el código y explicita el supuesto.

---

## Sincronización y bootstrap

- Cambios en reglas comunes: sigue `SHARED_INSTRUCTIONS.md` § «Gobernanza de plataformas IA».
- Trasladar esta configuración a otro proyecto: [`bootstrap_ai_config.prompt.md`](.github/prompts/bootstrap_ai_config.prompt.md)
  (modelo PULL, se invoca desde el proyecto destino).

---

*Actualizado: 2026-09-25*
