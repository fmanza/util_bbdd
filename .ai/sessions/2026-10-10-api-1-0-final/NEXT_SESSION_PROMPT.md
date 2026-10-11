# Prompt para la siguiente sesión (tras v1.0.0)

Copiar el bloque en una sesión nueva de Claude Code abierta en la raíz del repositorio.

````text
Sesión nueva: PLAN + AUDIT_PLAN de los pendientes de util_bbdd tras v1.0.0.

Base: develop @ v1.0.0 (158903b6), subido a origin con tag. main sigue en v0.42.1 (10 commits por detrás,
fast-forward posible). Python 3.12+, API pública estable bajo SemVer desde 1.0.0: la raíz util_bbdd (13 símbolos)
y los submódulos públicos (exceptions, audit, metadata, connection, factory, async_utils, analysis) solo cambian de
forma incompatible en una MAJOR.

Lee primero:
- .ai/CURRENT_STATE.md y docs/roadmap.md
- .ai/sessions/2026-10-10-api-1-0-final/TRACEABILITY.md y 02_DOC_REVIEW.md (hallazgos fuera de alcance)
- .ai/sessions/2026-10-10-plan-pendientes-global/PLAN_AUDIT_PLAN.md y Q6_PLAN_API_1_0.md (decisión A5)

Pendientes conocidos (verifica cada uno contra el código y el repo antes de planificar; no los des por ciertos):
1. Release en main: fusionar develop → main (fast-forward v0.42.1 → v1.0.0). Acción remota: pide autorización.
2. A5 de Q6 (aceptada): SRP de BulkCrud por dentro, sin cambiar su API pública (bulk/crud.py, ~1750 líneas,
   62 métodos; separar auditoría y rechazos en objetos propios). Flujo /refactor. DumpOrchestrator NO se parte.
3. BulkCrud(audit_csv_path="audit.csv") con str falla con AuditConfigError «'str' object has no attribute
   'parent'» (la firma es Path | None). Aceptar str | Path sería aditivo → 1.1.0. Decide si se hace y con qué flujo.
4. Deuda de tests: ~340 ResourceWarning «unclosed database» (SQLite) que solo aparecen con pytest --cov, en
   tests/unit/bulk/test_parallel_loader*.py, test_performance_advisor_once.py, test_reflect_fk_chain.py,
   tests/comparar/test_comparator.py (localiza si la fuga es del test o del código); y 3 SADeprecationWarning
   por create_engine(strategy="mock") en tests/_core/test_batching.py (usar create_mock_engine).
5. Documentación no revisada página a página en la sesión de 1.0 (solo comprobaciones automáticas de imports y
   métodos): guías de rendimiento, auditoría de constraints, páginas funcionales por motor (docs/functional/,
   docs/api/migrate_*). Reutiliza el método de 02_DOC_REVIEW.md.
6. .ai/CURRENT_STATE.md «Próximos pasos»: rehacer la lista con estos pendientes (la actual solo tiene ítems tachados).
7. Externos (sin gh aquí; los comprueba el usuario): PR #18 (cerrarla si sigue abierta), issue del ORA-03106
   (.ai/sessions/2026-10-01y-ora03106-repro/ISSUE_DRAFT.md), ejecuciones de docs-release.yml de los tags v0.43.0,
   v0.44.0 y v1.0.0, e integration.yml.
Aparcados (no reabrir salvo que lo pida): S-1 bulk con procesos (NO_GO hasta cargas ≥ 10M filas/tabla) y las dos
limitaciones de driver de docs/roadmap.md (MariaDB sin ssl_verify_identity, trust_cert con pymssql).

Qué quiero:
- Inventario verificado (ID, pendiente, estado comprobado hoy con evidencia, severidad) y propuesta de bloques
  ordenados con flujo (/refactor, /hotfix, /new-feature, docs, chore) y versión destino.
- Decisiones que necesites de mí, con tu recomendación.
- AUDIT_PLAN con riesgos y mitigaciones. Detente ahí y espera mi aprobación.

Sesión en .ai/sessions/<fecha>-plan-pendientes-post-1-0/ desde .ai/sessions/TEMPLATE/.

Restricciones:
- Puerta de calidad en cada IMPLEMENT/VERSION: pytest completo DOS veces, sin las URL del banco y con ellas
  (scripts/bench_env.example.sh + JAVA_HOME="C:/Program Files/Java/jdk-25"); ruff, ruff format, mypy,
  zensical build --strict, python -m build.
- Commits locales con Conventional Commits; nada de git add -A (añade solo tus rutas).
- Sin push, tags ni merge a main hasta que lo autorice de forma explícita.
- Logs y salidas en build/logs/.
````
