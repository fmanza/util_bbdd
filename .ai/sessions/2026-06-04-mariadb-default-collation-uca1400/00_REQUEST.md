# REQUEST

## Session metadata
- id: 2026-06-04-mariadb-default-collation-uca1400
- fecha: 2026-06-04
- rama: develop
- skill: hotfix (cambio de valor por defecto)
- fase solicitada: PROMPT → IMPLEMENT → docs → trazabilidad

## Solicitud original saneada

1. Cambiar en `src/util_bbdd/migrate` los valores por defecto para MariaDB:
   - Charset: `utf8mb4`
   - Collation: `utf8mb4_uca1400_ai_ci`
2. Actualizar la documentación pública afectada por el nuevo default.
3. Actualizar `.ai/sessions` y preparar mensaje para subir código a GitHub.

## Objetivo operativo de esta sesión

- Establecer `utf8mb4_uca1400_ai_ci` como collation por defecto del módulo `migrate`
  (charset por defecto `utf8mb4` ya estaba vigente).
- Garantizar que el nuevo default supere la validación interna
  (`validate_collation`, `validate_charset_collation_pair`).
- Reflejar el cambio en README, guías y ejemplos.

## Restricciones explícitas

- Cambio acotado: solo valor por defecto + validación + documentación.
- No eliminar `utf8mb4_unicode_ci` como opción válida (sigue disponible si se pasa explícito).
- No romper la suite de tests existente.

## Resultado esperado

- Carpeta `.ai/sessions/2026-06-04-mariadb-default-collation-uca1400/` con trazabilidad.
- Tests verdes.
- Mensaje de commit Conventional Commits listo para subir a GitHub.
