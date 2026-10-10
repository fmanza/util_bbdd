# PLAN + AUDIT_PLAN — `__module__` público de las excepciones (v0.44.0)

Fecha: 2026-10-10 · Base: `develop` @ v0.43.0 (`f8ba6edc`) · Skill: refactor · Origen: pendiente «1.0.0» de
`../2026-10-10-api-1-0/02_AUDIT_CODE.md`. Aprobado por el usuario en el chat («Si» a la propuesta, 2026-10-10).

## PLAN

- **Objetivo**: que las 40 excepciones muestren `util_bbdd.exceptions` (su ruta pública desde 0.43.0) en trazas, `repr`,
  logs y pickles, en vez de `util_bbdd._core.exceptions`. Sin cambio de API: mismas clases, mismos imports.
- **Rutas**: `src/util_bbdd/_core/exceptions.py` (bucle final que fija `__module__`, patrón `set_module` de NumPy);
  `tests/unit/test_exceptions_public_module.py` (nuevo); `docs/architecture.md` (una línea); CHANGELOG y campos de versión.
- **Componentes**: solo la jerarquía de excepciones. La implementación sigue en `_core`; la fachada `exceptions.py` no
  cambia.
- **Riesgos de regresión**: código o herramientas que dependan del texto `util_bbdd._core.exceptions` (agrupación de
  errores tipo Sentry, comparaciones de `type(e).__module__`).

## AUDIT_PLAN

| Riesgo | Evidencia | Mitigación |
|---|---|---|
| Pickles creados con ≤ 0.43 (`util_bbdd._core.exceptions.X`) | Simulado: se cargan, porque `_core.exceptions` sigue definiendo las clases | Test con un pickle en bytes con la ruta antigua |
| Pickles creados con ≥ 0.44 leídos por ≤ 0.43 | `util_bbdd.exceptions` no existe en ≤ 0.42; en 0.43 sí existe y resuelve | Documentado en CHANGELOG (`Changed`); caso raro (bajar de versión o procesos con versiones mezcladas) |
| `pickle.dumps` exige que `util_bbdd.exceptions.X is X` | `util_bbdd/__init__.py` importa `.exceptions`; cualquier import de `util_bbdd._core…` importa antes el paquete | Test de ida y vuelta de las 40 clases en subproceso que importa solo `util_bbdd._core.exceptions` |
| Excepción nueva que olvide el bucle | El bucle recorre `globals()` del módulo: cubre cualquier subclase de `DatabaseException` definida allí | Test que exige `__module__` público en todas las subclases encontradas |
| Uso en `src/`/tests del nombre de módulo | `grep`: ningún test comprueba el `__module__` de las excepciones; `src/` no usa `pickle` ni `multiprocessing` | — |
| mkdocstrings | Ya documenta en `util_bbdd.exceptions` (v0.43.0) | `zensical build --strict` |
| Seguridad | No cambia SQL, credenciales ni recursos | — |

**Veredicto**: GO.
