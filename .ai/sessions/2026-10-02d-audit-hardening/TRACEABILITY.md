# TRACEABILITY

## Session metadata
- id: 2026-10-02d-audit-hardening
- fecha: 2026-10-02
- rama: develop
- skill: fix (robustez) + tests, con el contrato PLAN/AUDIT_PLAN de `new_feature`
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + commit

## Prompt issued
«PLAN y AUDIT_PLAN de: la hipótesis 5 (los eventos de dump se construyen fuera del bloque que captura los fallos del
destino) y tests de los eventos de update/delete en paralelo.» Después: «si» (C1: los cuatro sitios).

## Context supplied
- `.ai/sessions/2026-10-02c-audit-module/02_IMPLEMENT_AUDIT_CODE_VERSION.md` § AUDIT_CODE independiente (hipótesis 5, test 5)
- `src/util_bbdd/dump/orchestrator.py`, `dump/_audit_events.py`, `bulk/_execution/parallel_loader.py`,
  `bulk/_support/persistence.py`, `migrate/_audit_events.py`, `migrate/ir/models.py`, `bulk/crud.py` (`__stream_operation`)

## AI output summary
- PLAN: la construcción fuera del `try` se repite en 4 sitios (cierre de `dump`, cierre de `ParallelBulkLoader`,
  `MigrationAuditRecorder`, `persistence._emit`). No es alcanzable hoy con entradas reales; efecto si ocurre: pérdida
  del resultado tras una operación correcta o excepción original tapada.
- AUDIT_PLAN: GO_CONDICIONAL (C1 alcance, C2 alternativa si el test de reintento no fuera determinista). Usuario: «si».
- IMPLEMENT: `DumpAuditWriter.write(build)` y `MigrationAuditRecorder.write(build)` reciben una función de construcción
  y la ejecutan dentro del `try`; `ParallelBulkLoader._write_load_events` y `persistence._emit` construyen dentro del
  `try` existente (en `_emit`, misma política que un fallo del destino: `audit_failures` o `AuditError`).
- Tests: `tests/unit/audit/test_event_build_failures.py` (7, inyección con `monkeypatch`; **los 7 fallan sin la
  corrección**, comprobado con `git stash` de `src/`, incluida la excepción tapada de `MigrationPlan.execute`);
  `tests/unit/bulk/test_audit_sink.py`: `update`/`delete` paralelos con destino (parametrizado) y reintento de
  `update` sin eventos duplicados (C2 no fue necesario: determinista con SQLite).
- Docs: `docs/api/audit.md` (fila de errores), CHANGELOG `[Unreleased]`.
- Verificación: 5827 passed, 32 skipped; ruff limpio; mypy sin errores nuevos (12 previos); `mkdocs build --strict` OK.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Código | 6 ficheros de `src/` (ver arriba) | completado |
| Tests | `tests/unit/audit/test_event_build_failures.py`, `tests/unit/bulk/test_audit_sink.py` | completado |

## Directrices para Futuras IAs
- **[auditoría]**: Todo emisor de eventos construye **y** escribe dentro del mismo `try` (`DumpAuditWriter.write` y
  `MigrationAuditRecorder.write` reciben una función `build`, no la lista ya construida). Un emisor nuevo debe seguir el
  patrón: un fallo de auditoría no puede hacer fallar una operación terminada ni tapar su excepción.
- **[tests]**: Para probar fallos de construcción, `monkeypatch.setattr(<Adaptador>, "<método>", staticmethod(f))` sobre
  `BulkAuditEvents`, `DumpAuditEvents` o `MigrationAuditEvents`.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Ninguno de esta sesión (commit hecho a petición del usuario, sin push). `/version-closure` sigue pendiente para numerar la versión.
