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
- **[release]**: El agente Version Closer solo puede editar `CHANGELOG.md` y el `TRACEABILITY.md`, pero el checklist de
  `sync.instructions.md` exige la versión en `pyproject.toml`, `README.md` (2 sitios), `docs/index.md`,
  `docs/roadmap.md` y el pie de figura de `docs/architecture.md`; el commit `release: v0.28.0` (`f04d87f`) los tocó
  todos, más `.ai/CURRENT_STATE.md` y `.ai/sessions/SESSIONS_DIGEST.md`. Pedir autorización al usuario para esas
  ediciones en cada cierre (o corregir el contrato del agente).
- **[release]**: `tests/unit/test_docs_version.py` compara `pyproject.toml` con README/docs, **no** con el CHANGELOG: un
  CHANGELOG cerrado con `pyproject.toml` sin subir no rompe ningún test.
- **[tests]**: La integración completa con las URLs de `scripts/bench_env.example.sh` (contraseña de los contenedores
  con `docker inspect`) da 537 tests en `tests/integration` (= los marcados `integration`). El cierre de v0.28.0 anotó
  «582 passed»; `tests/integration` no cambió desde v0.28.0 (`git diff 12d055c HEAD -- tests/integration` vacío): la
  diferencia no está explicada.
- **[build]**: Fuera de pytest, `import util_bbdd` carga la copia de site-packages; `python -m build` sí empaqueta
  `src/` (comprobado: `util_bbdd/audit/*` y los tres `_audit_events.py` están en el wheel).

## Cierre de versión v0.29.0 (`/version-closure`)

- Versión: **v0.29.0** (MINOR: API pública nueva sin cambios incompatibles). Commits incluidos: `8467053`
  (feat(audit)), `fb0bf80` (docs(ai)), `032c4e3` (fix(audit)).
- CHANGELOG: `[Unreleased]` → `## [0.29.0] - 2026-10-02` (Added / Changed / Removed); `[Unreleased]` vacío.
- Evidencia ejecutada en el cierre: `pytest` completo sin URLs de servidor **5973 passed, 422 skipped**; integración
  contra los 5 servidores del banco **536 passed, 1 skipped**; `python -m build` correcto (wheel y sdist, aún con
  número 0.28.0 porque `pyproject.toml` no se ha subido); antes en la sesión: ruff limpio, mypy sin errores nuevos (12
  previos), `mkdocs build --strict` sin avisos.
- Con autorización del usuario: versión 0.29.0 en `pyproject.toml`, `README.md` (2), `docs/index.md`, `docs/roadmap.md`,
  pie de figura de `docs/architecture.md`, `.ai/CURRENT_STATE.md` (fila, tests, próximos pasos) y
  `.ai/sessions/SESSIONS_DIGEST.md`. Verificado: `test_docs_version.py` y `test_docs_links.py` en verde,
  `mkdocs build --strict` sin avisos, `python -m build` → `util_bbdd-0.29.0` (wheel y sdist). Commit `release: v0.29.0`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Push de `develop` y tag `v0.29.0` (decisión del usuario).
