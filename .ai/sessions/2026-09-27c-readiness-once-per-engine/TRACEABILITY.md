# TRACEABILITY

## Session metadata
- id: 2026-09-27c-readiness-once-per-engine
- fecha: 2026-09-27
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
En la verificación de condiciones por motor, esta se debe hacer una sola vez, se detecta que cuando
obtiene una conexión por el POOL Vuelve hacer la comprobación, revisar la arquitectura para identificar
la actual implementación es la correcta para esta acción. Revisa .ai, src\util_bbdd\connection
→ «PLAN y AUDIT_PLAN»

## Context supplied
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`
- `.ai/sessions/2026-09-27-engine-readiness-advisor/TRACEABILITY.md`, `.ai/CURRENT_STATE.md`, `.ai/architecture.md`
- `src/util_bbdd/connection/performance_advisor.py`, `src/util_bbdd/bulk/crud.py`
- `src/util_bbdd/bulk/_execution/parallel_loader.py`, `src/util_bbdd/dump/orchestrator.py`

## AI output summary
- Localizado el disparador en `BulkCrud.__init__` → `__validate_engine_config` (checkout + consultas + informe por instancia).
- Inventariados los puntos que crean varias `BulkCrud` por engine (`ParallelBulkLoader`, `dump`).
- Verificado que `Engine` admite `weakref` (SQLAlchemy 2.0.50) y que ningún test depende de un informe por instancia.
- Emitido PLAN v1 (registro `WeakSet` + `Lock` en `EngineReadinessAdvisor.claim_first_report`, guarda en `crud.py`) y AUDIT_PLAN con veredicto GO.
- El usuario pide aplicar la recomendación completa. PLAN v2 sustituye a v1: `EngineReadinessAdvisor.report_once(engine)` y traslado de `conn_params` (URL/pool/driver) de `bulk/crud.py` a `connection/`; eliminado el `try/except ImportError` muerto. AUDIT_PLAN v2: GO.
- Commit previo de cambios pendientes del usuario (`9bd9ea6`, refactor de análisis estático); corregidos antes 2 errores de mypy (`level` sin `Literal` en `postgresql/_variables.py`, `values` redefinida en `bulk/normalize.py`) y formato.
- IMPLEMENT: `EngineReadinessAdvisor.report_once(engine)` + `_conn_params_from_engine` (`connection/performance_advisor.py`); `BulkCrud.__validate_engine_config` reducido a 1 línea con import en cabecera (sin ciclo). Driver mssql derivado de `url.drivername`.
- Tests nuevos: `tests/unit/connection/test_performance_advisor_once.py` (16) y `tests/unit/bulk/test_engine_readiness_once.py` (2). El test de liberación usa `weakref.ref` (contar el `WeakSet` era frágil por `gc.collect()` de engines de otros tests); contraseña ficticia vía `URL.create` (Sonar S6698).
- Validación: ruff check/format OK, mypy OK (362 ficheros), pytest 5248 passed / 199 skipped, `gen_arquitectura_capas.py --edges` OK.
- AUDIT_CODE: 1 hallazgo corregido — si el informe con conexión se emitía y fallaba el cierre (`__exit__`), el `except` emitía un segundo informe estático (preexistente en v0.18.1). Bandera `reported`; test `test_close_failure_after_report_does_not_report_twice`. Revisado sin hallazgo: engine registrado antes de verificar y excepción en `_conn_params_from_engine` (propaga como antes, el engine queda marcado: aceptado, mismo comportamiento que v0.18.1 en `BulkCrud.__init__`); `AsyncEngine` (no pasa por `BulkCrud`; caería al informe estático). Suite: 5249 passed / 199 skipped. Veredicto: APROBADO.
- VERSION: 0.18.2 en `pyproject.toml`; `CHANGELOG.md` `[0.18.2]` (Fixed/Added/Changed/Rollback); `.ai/CURRENT_STATE.md`, `.ai/sessions/INDEX.md`, `.ai/DECISIONS_LOG.md`; build de documentación en modo estricto OK. Sin tag ni push.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | .ai/sessions/2026-09-27c-readiness-once-per-engine/00_REQUEST.md | emitido |
| PLAN + AUDIT_PLAN | .ai/sessions/2026-09-27c-readiness-once-per-engine/01_PLAN.md | emitido (v2) |
| IMPLEMENT | src/util_bbdd/connection/performance_advisor.py, src/util_bbdd/bulk/crud.py | completado |
| Tests | tests/unit/connection/test_performance_advisor_once.py (17), tests/unit/bulk/test_engine_readiness_once.py (2) | completado |
| VERSION | CHANGELOG.md, pyproject.toml, .ai/CURRENT_STATE.md, .ai/DECISIONS_LOG.md, .ai/sessions/INDEX.md | completado |

## Directrices para Futuras IAs
- **[connection/performance_advisor]**: `EngineReadinessAdvisor.report_once(engine)` es el punto canónico para verificar un engine una vez por proceso (registro `WeakSet` + `Lock` en la clase, clave = objeto `Engine`). La lectura de URL/pool para el advisor vive en `_conn_params_from_engine`; `bulk/` no debe volver a leer atributos privados del pool.
- **[tests/registro compartido]**: no contar elementos del `WeakSet` en tests (otros tests liberan engines en `gc.collect()`); comprobar con `weakref.ref(engine)() is None`.
- **[bulk/crud]**: `BulkCrud` se instancia muchas veces sobre el mismo engine (una por partición/hilo en `ParallelBulkLoader` y `dump`); cualquier trabajo «de engine» en su `__init__` debe ser idempotente por engine.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Tag `v0.18.2` y push: pendientes de decisión del usuario.
