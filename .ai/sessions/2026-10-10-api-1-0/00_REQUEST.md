# REQUEST

## Session metadata
- id: 2026-10-10-api-1-0
- fecha: 2026-10-10
- rama: develop (base v0.42.1, `676ee482`)
- skill: refactor
- fase solicitada: PLAN → AUDIT_PLAN → (aprobación) → IMPLEMENT → AUDIT_CODE → VERSION (v0.43.0)

## Solicitud original saneada
Implementar la API pública 1.0 de util_bbdd, fase 0.43.0 (nueva superficie + alias deprecados), partiendo de
`.ai/sessions/2026-10-10-plan-pendientes-global/Q6_PLAN_API_1_0.md` y `api_inventory.tsv` (56 símbolos), con las
decisiones A1–A6 aceptadas:

- A1 (a): raíz con 13 símbolos (managers, BulkCrud, ParallelBulkLoader, DumpOrchestrator/Config/Result,
  MigrationPlanner/Plan, SchemaComparator/Diff, DatabaseDocumentation, DatabaseException); submódulos públicos
  estables `exceptions`, `audit`, `metadata`, `connection`, `analysis`.
- A2 (a): módulo público `util_bbdd.exceptions`; en la raíz solo `DatabaseException`; resto con `DeprecationWarning`.
- A3 (a): `Sync/AsyncMetadataProvider` solo en `util_bbdd.metadata` (alias deprecado en la raíz).
- A4 (a): simetría sync/async de los managers (`init`, `release_connection`/`close_connection`) con alias deprecados.
- A5 (a): SRP de `BulkCrud` fuera de esta sesión; `DumpOrchestrator` no se parte.
- A6: esta sesión llega a 0.43.0; los alias se retiran en 1.0.0.

## Objetivo operativo de esta sesión
- Raíz reducida a 13 símbolos con exportación perezosa y alias deprecados para los 43 restantes.
- `util_bbdd.exceptions` público.
- Managers simétricos en `init` y `release_connection`.
- Tests que fijan `__all__` y cada `DeprecationWarning`; guía de migración; v0.43.0 local.

## Restricciones explícitas
- Puerta: pytest completo dos veces (sin y con URL del banco + `JAVA_HOME` jdk-25), ruff, ruff format, mypy, build.
- Commits locales Conventional Commits; sin `git add -A`; sin push ni tags remotos sin autorización explícita.
- Logs en `build/logs/`.

## Resultado esperado
- `.ai/sessions/2026-10-10-api-1-0/` con PLAN, AUDIT_PLAN y TRACEABILITY; commits locales hasta `release: v0.43.0`.
