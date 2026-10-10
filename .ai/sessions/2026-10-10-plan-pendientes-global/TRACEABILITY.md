# TRACEABILITY

## Session metadata
- id: 2026-10-10-plan-pendientes-global
- fecha: 2026-10-10
- rama: develop
- skill: PLAN + AUDIT_PLAN (todo lo pendiente)
- fase: PLAN + AUDIT_PLAN; IMPLEMENT (Q0–Q5, decisiones recomendadas D1–D5); Q6 como PLAN

## Prompt issued
```text
PLAN y ADUIT_PLAN de todo lo pendiente
```

## Context supplied
- `.ai/CURRENT_STATE.md`, `docs/roadmap.md`, `TRACEABILITY.md` de 2026-10-05 a 2026-10-10, sesiones
  `2026-10-03-metadata-centralization`, `2026-10-04-api-single-entry-point-audit` y `2026-10-01l-plan-bulk-pending`.
- Banco docker para las sondas de H1 y H2.

## AI output summary
- Inventario de 15 pendientes; 6 descartados por resueltos.
- H1 confirmado con sondas: PostgreSQL `idle in transaction` y MySQL sin ver una tabla nueva tras `clear_cache()`
  (`use_pool=False`).
- H2 no reproducido (directo sobre `SnapshotCache` y vía `AsyncDatabaseManager`).
- Plan Q0–Q6 con decisiones D1–D5.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-10-plan-pendientes-global/PLAN_AUDIT_PLAN.md` | emitido |

## Directrices para Futuras IAs
- **[metadata/transacciones]**: `managers/_catalog_executor.py` solo hace `rollback` cuando la lectura falla; con
  `use_pool=False` la conexión queda en transacción. En MySQL eso congela el catálogo (REPEATABLE READ): una tabla creada
  desde fuera no aparece tras `clear_cache()`. Con pool no pasa (reset al devolver).
- **[metadata/async]**: `SnapshotCache.aget_or_load` funciona en dos `asyncio.run` seguidos con contención;
  `invalidate` parece descartar el lock de la clave.
- **[sondas async]**: un `AsyncDatabaseManager` con aiosqlite que no se cierra deja vivo el hilo del driver y el proceso
  no termina; cerrar siempre el manager en las sondas.
- **[metadata/transacciones]** (IMPLEMENT): con `use_pool=False` el ejecutor de catálogo usa la misma conexión que el
  usuario (`connection_provider=lambda: self._connection`): nunca hacer `rollback` sin comprobar antes que no había
  transacción (`_in_transaction`, por driver). MySQL 8 no marca `SERVER_STATUS_IN_TRANS` al leer `information_schema`.
- **[SQL Server/precarga]**: `metadata/reflection._resolve_requested` resuelve los nombres pedidos contra tablas y vistas
  existentes; con collation sensible a mayúsculas `Users` y `users` son tablas distintas.
- **[CI]**: `integration.yml` no tiene la CA de `build/bench_tls/` (los tests de TLS propio se saltan) y sí el paquete
  `mariadb` (Connector/C por apt). Para simular el CI en local de verdad: ocultar `build/bench_tls/`, quitar las URL de
  MSSQL/Oracle/HSQLDB y contenedores efímeros; sin eso la simulación da por buenos tests que fallan en el CI.
- **[SQL Server/transacciones]**: pymssql abre `BEGIN TRAN` al conectar y tras cada commit/rollback; pyodbc/aioodbc
  también dan `@@TRANCOUNT = 1` antes de leer. No intentes detectar la transacción del usuario por `@@TRANCOUNT`.
- **[puerta de calidad]**: ejecuta `pytest` también **sin** las URL del banco: con ellas cargadas, tests que fallan
  en el CI unitario pueden pasar desapercibidos (pasó en v0.41.2–v0.42.0).
- **[herramientas]**: aquí no hay `gh`: el estado del CI y de las PR de GitHub no se puede comprobar desde la sesión.

## Ejecución (IMPLEMENT, 2026-10-10)
Prompt: `IMPLEMENT` (sin decisiones explícitas: se aplicaron las recomendadas D1–D5; sin push).

| Bloque | Commits | Evidencia |
|---|---|---|
| Q0 | `bf83233a` | docs de `*MetadataProvider`; «Próximos pasos» al día |
| Q1 H1 | `bba64e75`, `047bcfd3` | 4 tests de integración (rojo antes en PostgreSQL y MySQL), 14 unitarios; `tests/integration` 572 pasan. Riesgo del AUDIT_PLAN confirmado: con `use_pool=False` el catálogo usa la conexión del usuario → `rollback` solo si consta que no había transacción |
| Q2 | `06c179ad` (tag `v0.41.2`) | puerta completa, build |
| Q3 F3/F4 | `cd29c422` | sondas en SQL Server (tabla inexistente; base `Latin1_General_CS_AS` con `Users`/`users`); tests de integración rojo → verde |
| Q3 F5 | `a1190d02` | test unitario rojo → verde |
| Q3 H2 | `c2a16ac9` | no reproducido; test que lo fija |
| Release | `1da796d6` (tag `v0.41.3`) | `tests/integration` 577 pasan |
| Q4 | `9f121eb5` | `integration.yml`. **Corregido tras /audit-code (CI-2):** la simulación de entonces no era fiel (en local estaban el paquete `mariadb` y la CA de `build/bench_tls/`); la fiel daba 7 fallos `[mariadb]` (CI-1). Ver «Condiciones de /audit-code» |
| Q5 HPK | `4569c290` | tests de integración HSQLDB (PK de sistema, sin PK, compuesta) |
| Q5 F7 | `fa749104` | 0,91 s → 0,003 s (2000 routines); test de equivalencia |
| Release | `30e0f5d0` (tag `v0.42.0`) | `tests/integration` 577 pasan; puerta completa |
| CI-1 | `b3db8526` | `integration.yml` instala `libmariadb-dev` + extra `mariadb`; `skip_reason()` salta los `[mariadb]` sin el paquete. Simulación fiel (sin CA, solo las 3 URL del CI): con `mariadb` 360 pasan, 0 fallos; sin `mariadb` 281 pasan, 0 fallos |
| H1-MS | `320244ea` | sonda: pymssql/pyodbc/aioodbc con `@@TRANCOUNT = 1` desde que conectan → la detección propuesta no sirve; 4 tests fijan que la lectura no retiene bloqueos, no frena DDL externo y respeta la transacción del usuario |
| Tests sin banco | `e1220d22` | 12 tests unitarios rotos desde v0.41.2/v0.41.3 (Mock en `_in_transaction`; Inspector simulado sin tablas tras F3/F4); las puertas anteriores se pasaron con las URL del banco cargadas. Ahora: sin banco 5512 pasan; con banco 6028 pasan, 7 saltados |
| Release | tag `v0.42.1` | `zensical build --strict`, `python -m build`, mypy (331 ficheros), ruff |
| Q6 | este documento | `Q6_PLAN_API_1_0.md` + `api_inventory.tsv` |

## Condiciones de /audit-code (2026-10-10)
Veredicto de la auditoría: APROBADO CON CONDICIONES (CI-1, H1-MS, CI-2). Las tres resueltas (filas CI-1 y H1-MS;
CI-2 es la corrección de la fila Q4).

## Veredicto final
Veredicto: GO (Q0–Q5 implementados en v0.41.2–v0.42.0; Q6 entregado como PLAN)
Pendientes al cierre:
- Push de `develop` y de los tags `v0.41.2`, `v0.41.3`, `v0.42.0`, `v0.42.1` (no autorizado).
- ~~Decisiones A1–A6 de `Q6_PLAN_API_1_0.md`~~: aceptadas las recomendadas (2026-10-10); IMPLEMENT en sesión propia (0.43.0).
- Comprobar en GitHub la primera ejecución de `integration.yml` (aquí no hay `gh`).
- Externos: PR #18, issue ORA-03106.
