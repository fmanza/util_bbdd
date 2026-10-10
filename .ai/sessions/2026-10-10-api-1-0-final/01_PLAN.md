# PLAN + AUDIT_PLAN — v1.0.0: retirada de los alias + revisión de documentación

Fecha: 2026-10-10 · Base: `develop` @ v0.44.0 (`920a5748`) · Skill: refactor (ruptura de API autorizada)

## Solicitud

«Hazlo ahora, no necesito versión de avisos. Luego revisar documentación y actualizar.» El usuario renuncia de forma
explícita a la ventana de avisos prevista en A6 (0.43 → al menos una versión → 1.0.0).

## PLAN

- **Objetivo**: cerrar la API 1.0 retirando lo deprecado en 0.43.0, y revisar la documentación para que describa 1.0.
- **Código**: `src/util_bbdd/__init__.py` (fuera `_DEPRECATED` y su rama de `__getattr__`; quedan `_LAZY` y
  `_SUBMODULES`); `managers/sync_mgr.py` (fuera `close_connection()` y el import de `warnings`).
- **Tests**: `test_top_level_exports.py` (los 46 nombres no existen en la raíz y sí en su submódulo; `from util_bbdd
  import QueryError` da `ImportError`); `test_manager_symmetry.py` (sin `close_connection` en ningún manager).
- **Documentación**: guía de migración en pasado, CHANGELOG `Removed`, SHARED_INSTRUCTIONS, managers, roadmap, README y
  revisión del resto de `docs/` (ver `02_DOC_REVIEW.md`).
- **Versión**: 1.0.0 (MAJOR por SemVer: se retira API pública).

## AUDIT_PLAN

| Riesgo | Mitigación |
|---|---|
| Código de usuario con imports antiguos rompe sin aviso previo | Decisión explícita del usuario; guía de migración con la tabla completa; CHANGELOG `Removed` |
| Mensaje de error útil al fallar el import | Probado: `from util_bbdd import X` convierte cualquier `AttributeError` en `ImportError` genérico; una tabla con mensajes solo serviría para `util_bbdd.X`. No se mantiene (la guía es la referencia) |
| Criterio de 1.0.0 en `docs/roadmap.md` (cobertura ≥ 85 %) | Se mide en la puerta y se informa; no bloquea porque el usuario pide 1.0.0 ahora |
| Uso residual en el repo | `grep` de `_DEPRECATED` y `close_connection` sobre managers: solo el método interno de `SyncSessionManager` (privado) |

**Veredicto**: GO.
