# TRACEABILITY

## Session metadata
- id: 2026-11-13b-plan-pendientes-post-5-6
- fecha: 2026-11-13
- rama: develop
- skill: new_feature (G49, A2) + chore (CI, deps) + documentation (estado)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
«Que queda pendiente en el proyecto» → «PLAN y AUDIT_PLANT de todo por fases. Esto ya se está ejecutando no poner en
PLAN: util_bbdd_web: subir el commit de G55 (8f876c6) y adaptar la web a la 5.6.0…» → «IMPLEMENT» (D1–D6 con las
opciones recomendadas del plan).

## Context supplied
- `PLAN_AUDIT_PLAN.md` de esta sesión; `.ai/CURRENT_STATE.md`; GitHub (`gh`: PR #26, runs); G49 de
  `util_bbdd_web/docs/plan/UTIL_BBDD_GAPS.md`.

## AI output summary
- F0 `94a507f0`: CURRENT_STATE (R6, R8, D3.3 cerrados; filas F0–F5) y «En curso» del roadmap.
- F1 `55f9ef0d`: acciones a checkout@v7, setup-python@v7, upload-artifact@v7, codecov@v7, action-gh-release@v3. Notas
  revisadas (Node 24; setup-python@v7 sin `pip-install`, no usado; codecov con `fail_ci_if_error: false`). Desvío de D5:
  aplicadas a mano en vez de pedir rebase (evita escribir en la PR); Dependabot cerró la PR #26 solo. Push de `develop`
  y CI en verde (CI, Docs, Build and Publish Docs ZIP).
- F4 `3608b050`: `hsqldb` en `dev-full` (JPype1 1.7.1 con wheels 3.12–3.14); venv limpio 7114 passed / 618 skipped.
- F2 `9b59847d`: `util_bbdd.doc.validate_trace_map(path) -> None` (`doc/validation.py`, reutiliza `TraceMap.load`);
  mensajes del mapa y de `markdown.previous` sin rutas (`error_reason` usa `strerror`); 16 tests nuevos; API, autodoc,
  guía.
- F3 `f865c6da`: `connection/sqlserver/_odbc_driver.py` (driver ODBC por defecto = el más reciente de
  `pyodbc.drivers()`; 17 si no hay, sin pyodbc o con error) usado en `from_params`, `build_conn_params`, la cadena sync
  y el DSN async; 24 tests con pyodbc simulado.
- AUDIT_CODE: test de API de `util_bbdd.doc` (congelaba `__all__`) actualizado; regresión propia corregida en
  `a9e5689d` (con pymssql, `from_params` perdía un `driver_name` explícito). Sin más hallazgos.
- Banco: `util_bbdd_bench_mssql` no arrancaba (puerto 51833 en el rango excluido 51773–51872 de Windows). Con
  permiso del usuario, recreado con compose en el puerto por defecto 51433 (libre de nuevo). A2 verificado contra
  SQL Server 2022 con solo el ODBC Driver 18 y sin `driver_name`: sync (pyodbc) y async (aioodbc), con y sin pool.
  Integración `-k "mssql or sqlserver"` con solo la URL de SQL Server: 104 passed, 33 skipped (otros motores).
- VERSION 5.7.0: campos de `sync.instructions.md` § 4, 19 pines `@v5.7.0`, CHANGELOG fechado, estado.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-11-13b-plan-pendientes-post-5-6/PLAN_AUDIT_PLAN.md` | aprobado (D1–D6) |
| Validador público | `src/util_bbdd/doc/validation.py` | nuevo |
| Driver ODBC | `src/util_bbdd/connection/sqlserver/_odbc_driver.py` | nuevo |

## Pruebas
- pytest local (Windows, 3.14): 7152 passed, 619 skipped (+1 salto: test de permisos POSIX).
- Venv limpio `.[dev-full]`: 7151 passed, 619 skipped.
- ruff, `ruff format --check`, mypy (375) limpios; `zensical build --strict` sin incidencias; diagrama de capas: 374
  ficheros; `python -m build` 5.7.0 y wheel probado en venv nuevo (versión, `validate_trace_map`, fallback ODBC 17).

## Directrices para Futuras IAs
- **[doc]**: `util_bbdd.doc.validate_trace_map` es el validador público del mapa; delega en
  `TraceMap.load` (`_trace.py`): un único juego de reglas. `tests/unit/test_database_documentation.py` congela el
  `__all__` de `util_bbdd.doc`.
- **[doc]**: en mensajes de error de ficheros no uses `str(OSError)` (lleva la ruta): `_trace.error_reason()`.
- **[connection]**: el driver ODBC por defecto vive solo en `connection/sqlserver/_odbc_driver.py`
  (`resolve_odbc_driver`); `default_odbc_driver` está en caché por proceso (los tests hacen `cache_clear()`). Con
  pymssql no se consulta pyodbc y un `driver_name` explícito se conserva.
- **[ci]**: Dependabot cierra su PR si las acciones ya están actualizadas en `develop`; aplicar los saltos a mano evita
  escribir en la PR.
- **[banco]**: Hyper-V cambia los rangos de puertos excluidos tras reiniciar; antes de `docker start` del banco,
  `netsh interface ipv4 show excludedportrange protocol=tcp`. Desde 2026-11-13 SQL Server vuelve a 51433.
- **[banco]**: `-k "mssql or sqlserver"` también selecciona tests de otros motores con «mssql» en el nombre; con sus
  contenedores parados esperan al timeout de conexión. Quitar del entorno las URL de los motores parados.

## Veredicto final
Veredicto: CLOSED — v5.7.0 (commits y tag anotado `v5.7.0` en local; push y release, a cargo del usuario).
Pendientes al cierre:
- Push de `develop` y del tag, ff de `main` y release de GitHub con el wheel y el `.sha256` (`release_guide` §5–7).
- util_bbdd_web: G49 se marca «Resuelto en 5.7.0» cuando la web adopte esa versión.
