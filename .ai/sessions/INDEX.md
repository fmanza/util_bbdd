# SESSION INDEX

Inventario de sesiones de trabajo controlado en `.ai/sessions/`.
Cada sesión sigue la estructura de artefactos definida en `TEMPLATE/`.

## Convención de nomenclatura
```
.ai/sessions/YYYY-MM-DD/
  00_REQUEST.md           ← solicitud saneada y restricciones
  00_CONTEXT_SNAPSHOT.md  ← estado del repo y Gate G0
  NN_<FASE>.md            ← artefactos por fase (PLAN, IMPLEMENT, etc.)
  TRACEABILITY.md         ← resumen de lo ejecutado y veredicto final
```

## Sesiones

| Fecha       | Objetivo breve                                      | Rama                  | Skill          | Estado   | Trazabilidad                          |
|-------------|-----------------------------------------------------|-----------------------|----------------|----------|---------------------------------------|
| 2026-03-22  | Refactorización v0.6.0: relaciones N niveles        | develop → main (v0.6.0) | refactor     | CLOSED   | `2026-03-22/REFACTOR_v0.6.0_SESSION.md` |
| 2026-03-24  | Aplicar metodología IA + primera slice v0.6.1 HTML  | develop               | new_feature    | CLOSED   | `2026-03-24/TRACEABILITY.md`          |
| 2026-03-25  | Aplicar metodología IA + features v0.6.2            | develop               | new_feature    | CLOSED   | `2026-03-25/TRACEABILITY.md`          |

## Crear nueva sesión

1. Copia `TEMPLATE/` con nombre `YYYY-MM-DD/`.
2. Rellena `00_REQUEST.md` antes de invocar cualquier agente.
3. Rellena `00_CONTEXT_SNAPSHOT.md` y obtén veredicto Gate G0.
4. Añade esta sesión al índice anterior con estado `IN_PROGRESS`.
5. Al cerrar, actualiza el estado a `CLOSED` y completa `TRACEABILITY.md`.

## Estados válidos
| Estado       | Significado                                        |
|--------------|----------------------------------------------------|
| `IN_PROGRESS`| Sesión activa; al menos una fase en ejecución      |
| `CLOSED`     | Sesión cerrada con trazabilidad completa            |
| `ABANDONED`  | Sesión interrumpida; puede tener artefactos parciales |
