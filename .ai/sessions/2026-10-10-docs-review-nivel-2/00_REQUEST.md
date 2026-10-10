# REQUEST

## Session metadata
- id: 2026-10-10-docs-review-nivel-2
- fecha: 2026-10-10
- rama: develop (= main = v1.1.0, `e4467d25`; HEAD `fbcf63ff`)
- skill: documentation (revisión página a página, nivel 2; pendiente D2)
- fase solicitada: PLAN + AUDIT_PLAN; esperar aprobación

## Solicitud original saneada
Revisión página a página de las 82 páginas de `03_DOCS_PENDIENTES.txt` (incluye `docs/examples/migrate_*`), con el
método de las dos sesiones anteriores (`2026-10-10-api-1-0-final/02_DOC_REVIEW.md` y
`2026-10-10-plan-pendientes-post-1-0/02_DOC_REVIEW.md`): comprobador automático de imports y métodos, lectura completa,
verificación de cada afirmación contra el código, ejecución de los ejemplos tocados, cifras de rendimiento solo con
fuente. Cuatro tandas con un commit `docs:` cada una y registro en `02_DOC_REVIEW.md`.

## Objetivo operativo de esta sesión
- Las 82 páginas leídas enteras y corregidas contra el código de v1.1.0.
- Los 17 ejemplos de `docs/examples/` del alcance ejecutados (SQLite en el scratchpad; motores reales con el banco).
- Consolidación de páginas repetidas, propuesta antes de corregirlas.
- Registro de hallazgos y correcciones en `02_DOC_REVIEW.md`.

## Restricciones explícitas
- Fallo de la librería al ejecutar un ejemplo → DETENERSE y preguntar (`/hotfix` aparte).
- Fuera de alcance: `driver_name` por defecto de SQL Server (ODBC Driver 17).
- Puerta por tanda: `zensical build --strict` + comprobador sin hallazgos. Puerta de cierre: además ruff, ruff format,
  mypy, pytest completo dos veces (sin y con las URL del banco + `JAVA_HOME="C:/Program Files/Java/jdk-25"`),
  `python -m build`.
- Commits locales Conventional Commits, sin `git add -A`; sin push, tags ni merge sin autorización explícita.
- Scripts con regex o `\|` con Write; logs en `build/logs/`.

## Resultado esperado
- `.ai/sessions/2026-10-10-docs-review-nivel-2/` con `PLAN_AUDIT_PLAN.md`, `02_DOC_REVIEW.md`, `TRACEABILITY.md`.
- 4 commits `docs:` (uno por tanda) + los de consolidación si se aprueban.
