# PLAN + AUDIT_PLAN — todo lo pendiente del proyecto (tras v0.41.1)

Fecha: 2026-10-10 · Base: `develop` @ `cd049fb0` (0.41.1 + `[Unreleased]`) · Solo lectura (sondas temporales fuera del
repo contra el banco docker)

## 0. Fuentes revisadas

`.ai/CURRENT_STATE.md` («Próximos pasos»), `docs/roadmap.md`, «Pendientes al cierre» de todos los `TRACEABILITY.md` de
2026-10-05 a 2026-10-10, `2026-10-03-metadata-centralization` (hallazgos F3–F7, H1–H2), `2026-10-04-api-single-entry-point-audit`,
`2026-10-01l-plan-bulk-pending` (S-1), `CHANGELOG.md` `[Unreleased]`, TODO/FIXME de `src/`, `.github/workflows/`.

## 1. Inventario verificado

| ID | Pendiente | Estado verificado hoy | Severidad |
|---|---|---|---|
| **H1** | Lecturas de catálogo sin fin de transacción con `autocommit=False` (`metadata-centralization`, «pendiente de verificar en banco») | **Confirmado.** `managers/_catalog_executor.py` solo hace `rollback` si la lectura falla. Con `use_pool=False`: PostgreSQL deja la conexión `idle in transaction`; **MySQL no ve una tabla creada desde fuera tras `clear_cache()`** (la transacción REPEATABLE READ congela el catálogo). MariaDB sí la ve. Con pool no ocurre (el pool hace reset al devolver la conexión) | **Alta** (metadatos obsoletos en MySQL) |
| REL | `[Unreleased]`: P5–P7 + `security(analysis)` S-04 en matplotlib | En `develop`, sin versión | — |
| H2 | `asyncio.Lock` por clave reutilizado entre bucles (`SnapshotCache`) | **No reproducido**: dos `asyncio.run` con 3–5 tareas en contención (directo sobre `SnapshotCache` y vía `AsyncDatabaseManager`) funcionan; `invalidate` parece descartar el lock de la clave | Baja |
| F3 | Precarga de SQL Server (`metadata/reflection.prefetch_table_metadata`, usada por `comparar`) da PK/FK vacías a tablas inexistentes | Código sin cambios desde el hallazgo; sin verificar | Baja |
| F4 | `_as_requested` (`metadata/reflection.py:223`) no detecta filas ambiguas con collation sensible a mayúsculas | Código presente; sin verificar | Baja |
| F5 | Schema por defecto sin `normalize_name` frente a la invalidación (usuarios Oracle/HSQLDB entrecomillados en minúsculas) | `CatalogSource.current_schema()` sigue sin normalizar | Baja |
| F7 | `SchemaSnapshot.routine_parameters`/rutinas/vistas con búsqueda lineal | `routine_parameters` recorre todos los parámetros en cada rutina (O(R·P)) | Baja (rendimiento) |
| HPK | DDL de tabla de HSQLDB sin `PRIMARY KEY` | Confirmado (v0.41.1, fuera del hotfix) | Baja (mejora) |
| DOC | `docs/index.md:20` y `docs/architecture.md:52` describen `SyncMetadataProvider`/`AsyncMetadataProvider` «con caché de sesión»; desde ADR-003 son `Protocol` y la caché es del manager | Confirmado | Baja |
| STATE | `CURRENT_STATE.md` «Próximos pasos» arrastra pendientes ya resueltos u obsoletos (fallback de charset de MariaDB del 2026-10-06, sustituido por la «Opción E» y `catalog_charset_mode`; lista de v0.31.0 sin estado) | Confirmado | — |
| CI | El CI (`tests.yml`) solo ejecuta tests unitarios en 3 Python × SO; la integración con motores reales solo corre en local | Confirmado | Media (riesgo de regresión entre motores) |
| API | Auditoría de API (v0.30): «Opción A» hecha (`_core/validation`); quedan B (consolidar factories, decidir si `SyncMetadataProvider` es público) y C (SRP de `BulkCrud`/`DumpOrchestrator`, para 1.0). `util_bbdd.__all__` ha pasado de 33 a **56** símbolos | Confirmado | Media (deuda de diseño, sin fallo) |
| S-1 | `bulk` con procesos: NO_GO; reabrir con cargas ≥ 10M filas por tabla | Sin cambios | — (aparcado) |
| EXT | PR #18 (cerrar si sigue abierta), issue del ORA-03106 (`2026-10-01y-ora03106-repro/ISSUE_DRAFT.md`), estado del CI en GitHub | **No verificable aquí** (sin `gh`) | — (acción del usuario) |
| — | Limitaciones de drivers (ADR-005), 9 `no-untyped-call` de python-docx, `zz_md_*` del banco | No corregibles desde la librería o conservados a propósito | — |

Descartados por estar resueltos: fallback de charset de MariaDB y su versión mínima de driver (2026-10-06), dorado
`test_snapshot_golden[oracle]` (pasa), `encoding_errors` (retirado en 0.35.7), anclas rotas de `connection_guide.md`
(`zensical build --strict` limpio), `SKILL.md` de drivers (v1.0.5).

## 2. Decisiones pendientes

| # | Tema | Opciones | Recomendación |
|---|---|---|---|
| D1 | H1 | (a) terminar la transacción (`rollback`) tras **toda** lectura de catálogo en conexiones sin autocommit, sync y async; (b) abrir las conexiones de catálogo en autocommit | **(a)**: no cambia cómo se abren las conexiones del usuario y las lecturas de catálogo nunca escriben |
| D2 | CI de integración | (a) job con contenedores de servicio PostgreSQL, MySQL y MariaDB en cada push a `develop`; (b) igual, pero solo manual/nocturno (`workflow_dispatch` + `schedule`); (c) nada | **(b)**: cubre los motores ligeros sin alargar cada push; SQL Server y Oracle siguen en el banco local |
| D3 | API 1.0 (B/C) | (a) sesión de PLAN solo (`/tech-debt` o `/refactor` PLAN) para decidir el alcance de 1.0; (b) aplazar | **(a)**: decidir antes de que la API siga creciendo |
| D4 | Mejoras menores (HPK, F7) | (a) incluirlas en 0.42.0; (b) aplazar | **(a)**, F7 solo si una medición con muchas rutinas lo justifica |
| D5 | S-1 | mantener aparcado / reabrir | **Mantener** |

## 3. PLAN por bloques

| # | Bloque | Contenido | Flujo | Versión |
|---|---|---|---|---|
| Q0 | Estado y docs | `CURRENT_STATE` «Próximos pasos» al día (resueltos tachados, abiertos con estado verificado); `docs/index.md`/`architecture.md` sobre `*MetadataProvider` | `docs` | — |
| Q1 | H1 | `_catalog_executor`: `rollback` antes de liberar la conexión también tras una lectura correcta, si la conexión no está en autocommit (sync y async). Tests de integración que hoy fallan: PostgreSQL sin `idle in transaction` tras `get_schema_metadata()` y MySQL viendo una tabla creada desde fuera tras `clear_cache()`, ambos con `use_pool=False` | `/hotfix` | 0.41.2 |
| Q2 | Release | `[Unreleased]` (P5–P7, S-04 matplotlib) + Q1 → 0.41.2, tag y push | `/version-closure` | 0.41.2 |
| Q3 | Verificación F3/F4/F5 + H2 | Sondas contra el banco: F3 (SQL Server, tabla inexistente en `prefetch_table_metadata`), F4 (MySQL/SQL Server con collation sensible a mayúsculas y nombres que solo difieren en mayúsculas), F5 (usuario Oracle entrecomillado en minúsculas + `clear_cache`); H2 se cierra con un test unitario que fije el comportamiento actual. Cada hallazgo confirmado → `fix` con su test; los no reproducibles se cierran con evidencia | `fix` | 0.41.3 si hay correcciones |
| Q4 | CI (según D2) | `.github/workflows/integration.yml`: servicios `postgres:17`, `mysql:8.4`, `mariadb:11.4`; `UTIL_BBDD_TEST_*_URL` construidas en el job; `pytest tests/integration -m integration -k "postgresql or mysql or mariadb"` | `chore(ci)` | — |
| Q5 | Mejoras (según D4) | HPK: `CONSTRAINT … PRIMARY KEY (…)` en el DDL de HSQLDB desde `INFORMATION_SCHEMA.TABLE_CONSTRAINTS`/`KEY_COLUMN_USAGE`. F7: índice por rutina en `SchemaSnapshot.routine_parameters` tras medir con ≥ 1000 rutinas | `/new-feature` / `perf` | 0.42.0 |
| Q6 | API 1.0 (según D3) | Sesión de PLAN: inventario de los 56 símbolos (quién los usa en `docs/`, `examples/`, `tests/`), propuesta de superficie 1.0, decisión sobre `SyncMetadataProvider` y sobre partir `BulkCrud`/`DumpOrchestrator` | PLAN | — |
| — | Externos | PR #18, issue ORA-03106, revisar el estado del CI en GitHub | usuario | — |

Orden: Q0 → Q1 → Q2 (publica lo hecho y el arreglo de mayor severidad), Q3, Q4, Q5, Q6.

## 4. AUDIT_PLAN

### Riesgos funcionales

| Bloque | Riesgo | Mitigación |
|---|---|---|
| Q1 | Un `rollback` tras leer el catálogo deshace trabajo sin confirmar **del usuario** si el catálogo usa la misma conexión que sus escrituras | Comprobar en IMPLEMENT de dónde salen las conexiones del ejecutor de catálogo (`_get_sync_query_executor().connection_provider()`): si pueden compartirse con una transacción del usuario, limitar el `rollback` a conexiones propias del catálogo o usar `commit` solo de lectura. Test que lo cubra |
| Q1 | Coste de un `rollback` extra por consulta | Una por consulta de catálogo (12 con 500 tablas, ADR-003): despreciable |
| Q1 | Async (asyncpg, aiomysql, aiosqlite) | Mismo cambio en `afetch_all`; probar con `AsyncDatabaseManager(use_pool=False)` en PostgreSQL y MySQL |
| Q3 | Corregir F4 cambia qué filas se devuelven con nombres que solo difieren en mayúsculas | Solo con evidencia de una sonda; test por motor |
| Q4 | CI más lento o inestable (arranque de contenedores) | Solo manual/nocturno (D2-b); `--wait`/healthchecks; sin SQL Server ni Oracle |
| Q5 | El DDL de HSQLDB con PK cambia el texto | Mejora en minor (0.42.0); test de integración actualizado |

### Riesgos técnicos

- **Q1 toca el camino de todos los motores**: ejecutar `tests/integration` completa (5 servidores + HSQLDB con
  `JAVA_HOME`) y los dorados de caracterización antes de cerrar.
- **Barras invertidas**: editar con Write/Edit (memoria del proyecto).
- **Q4**: credenciales del CI solo como variables del job (contraseñas de prueba de los contenedores efímeros), nunca
  las del banco local.

### Riesgos de seguridad

- Q1 reduce riesgo: una transacción abierta retiene locks/snapshots y puede bloquear DDL de otros procesos.
- Q4: sin secretos reales en el workflow.

### Verificación

| Bloque | Evidencia |
|---|---|
| Q1 | Las dos sondas de § 1 convertidas en tests de integración: rojo antes, verde después; `tests/integration` completa |
| Q2 | Puerta completa (`ruff`, `mypy`, `pytest`, `zensical build --strict`, `python -m build`), tag y push |
| Q3 | Una sonda por hallazgo con resultado registrado; tests de los que se corrijan |
| Q4 | Una ejecución verde del workflow (la comprueba el usuario en GitHub; aquí no hay `gh`) |
| Q5 | Test de integración de HSQLDB con PK; medición de F7 antes/después |
| Q6 | Documento de PLAN con la superficie propuesta |

### Veredicto AUDIT_PLAN

**GO_CONDICIONAL**: Q0–Q2 pueden empezar ya (Q1 con D1); Q3 sin decisiones; Q4–Q6 dependen de D2–D4.
