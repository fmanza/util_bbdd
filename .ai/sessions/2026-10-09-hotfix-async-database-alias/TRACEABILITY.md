# TRACEABILITY

## Session metadata
- id: 2026-10-09-hotfix-async-database-alias
- fecha: 2026-10-09
- rama: develop
- skill: hotfix
- fase: PLAN + IMPLEMENT (RCA + fix) + AUDIT_CODE + VERSION

## Prompt issued
```text
/hotfix

Bug: F1 de FASE 5 — AsyncDatabaseManager.database se calcula de los conn_params originales y no de los validados: con el alias filepath de SQLite queda "" (sync: ruta correcta); afecta a get_connection_info()["database"] y al id de caché del catálogo
Rutas: src/util_bbdd/managers/async_mgr.py:79
Evidencia: .ai/sessions/2026-10-09-drivers-connections-audit-fase5/audit_phase_5.md (F1, reproducido)
Prioridad: P3 (cosmético; caché por instancia)
Incluir además F2: test unitario de que SyncDatabaseManager pasa catalog_charset_mode al ManagerCatalogExecutor
Versión: 0.39.1. Commit + versión al cerrar.
```
Origen: el usuario aceptó («si») la propuesta de FASE 5 (hotfix F1 + test F2; F3–F5 como deuda en FASE 6).

## Context supplied
- `.ai/sessions/2026-10-09-drivers-connections-audit-fase5/audit_phase_5.md`

## AI output summary
- RCA: desde B1 (v0.37.0) el constructor async valida y normaliza en `self.conn_params`, pero `self.database` seguía leyendo el argumento original.
- Test-first: `test_async_manager_database_comes_from_validated_params` fallaba (`'' == 'x.db'`). F2: `test_sync_manager_builds_executor_with_mode` (cobertura; el comportamiento ya era correcto).
- Fix (1 línea): `self.database` desde `self.conn_params`.
- `ruff`/`mypy` OK; `pytest` 5397 passed, 497 skipped (`build/logs/hotfix_async_database_alias_suite.txt`); `tests/integration` 552 passed, 10 skipped (`build/logs/hotfix_async_database_alias_integration.txt`).
- Versión 0.39.1.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/managers/async_mgr.py` | 1 línea |
| Tests | `tests/unit/test_async_conn_params_validation.py`, `tests/unit/metadata/test_catalog_charset_mode.py` | 2 tests nuevos |
| VERSION | ficheros de versión | 0.39.1 |

## Directrices para Futuras IAs
- **[managers/async]**: tras validar, todo lo derivado de `conn_params` sale de `self.conn_params` (ver F1).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- FASE 6 (`/version-closure`) con F3–F5 como deuda registrada.
- Push y tag `v0.39.1` pendientes; commit de FASE 5 (`6dab3e2b`) sin push.
