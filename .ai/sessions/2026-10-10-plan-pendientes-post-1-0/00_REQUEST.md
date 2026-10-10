# REQUEST

## Session metadata
- id: 2026-10-10-plan-pendientes-post-1-0
- fecha: 2026-10-10
- rama: develop
- skill: planificación (PLAN + AUDIT_PLAN de pendientes; sin IMPLEMENT)
- fase solicitada: PLAN + AUDIT_PLAN; detenerse y esperar aprobación

## Solicitud original saneada
PLAN + AUDIT_PLAN de los pendientes de util_bbdd tras v1.0.0. Base: `develop` @ v1.0.0 (`158903b6`), subido a origin
con tag; `main` en v0.42.1 (10 commits por detrás, fast-forward posible). API pública estable bajo SemVer desde 1.0.0.

Pendientes conocidos, a verificar contra el código y el repo antes de planificar:

1. Release en `main`: fusionar `develop` → `main` (fast-forward). Acción remota: pedir autorización.
2. A5 de Q6 (aceptada): SRP de `BulkCrud` por dentro, sin cambiar su API pública. Flujo `/refactor`. `DumpOrchestrator`
   no se parte.
3. `BulkCrud(audit_csv_path="audit.csv")` con `str` falla con `AuditConfigError`. Aceptar `str | Path` sería aditivo
   (1.1.0). Decidir si se hace y con qué flujo.
4. Deuda de tests: ~340 `ResourceWarning` «unclosed database» con `pytest --cov` (localizar si la fuga es del test o del
   código) y 3 `SADeprecationWarning` por `create_engine(strategy="mock")` en `tests/_core/test_batching.py`.
5. Documentación no revisada página a página en la sesión de 1.0 (guías de rendimiento, auditoría de constraints,
   páginas funcionales por motor, `docs/api/migrate_*`). Reutilizar el método de `02_DOC_REVIEW.md`.
6. `.ai/CURRENT_STATE.md` «Próximos pasos»: rehacer la lista.
7. Externos (sin `gh`; los comprueba el usuario): PR #18, issue del ORA-03106, ejecuciones de `docs-release.yml` de los
   tags v0.43.0, v0.44.0 y v1.0.0, e `integration.yml`.

Aparcados (no reabrir): S-1 (bulk con procesos) y las dos limitaciones de driver de `docs/roadmap.md`.

## Objetivo operativo de esta sesión
- Inventario verificado (ID, pendiente, estado comprobado hoy con evidencia, severidad).
- Bloques ordenados con flujo y versión destino.
- Decisiones para el usuario con recomendación.
- AUDIT_PLAN con riesgos y mitigaciones.

## Restricciones explícitas
- Detenerse tras AUDIT_PLAN y esperar aprobación.
- Puerta de calidad en cada IMPLEMENT/VERSION: pytest completo dos veces (sin y con las URL del banco +
  `JAVA_HOME="C:/Program Files/Java/jdk-25"`), ruff, ruff format, mypy, `zensical build --strict`, `python -m build`.
- Commits locales con Conventional Commits; nada de `git add -A`.
- Sin push, tags ni merge a `main` sin autorización explícita.
- Logs y salidas en `build/logs/`.

## Resultado esperado
`.ai/sessions/2026-10-10-plan-pendientes-post-1-0/` con `00_REQUEST.md`, `00_CONTEXT_SNAPSHOT.md`,
`PLAN_AUDIT_PLAN.md` y `TRACEABILITY.md`.
