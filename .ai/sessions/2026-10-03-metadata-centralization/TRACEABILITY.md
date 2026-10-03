# TRACEABILITY

## Session metadata
- id: 2026-10-03-metadata-centralization
- fecha: 2026-10-03
- rama: develop
- skill: metadata_centralization_audit_and_refactor (`/metadata-centralization`) — Plan Architect + Performance Auditor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (HF, QW, A0; A1 en adelante pendiente)

## Prompt issued

```text
/metadata-centralization

Módulo destino: metadata/ ampliado
Ejes: ambos
Motores: todos
Baseline: no (capturar en PLAN)
Volumen de catálogo: 50 / 500 / 5000 tablas
Banco: sí (docker-compose.bench.yml)
Fases autorizadas: PLAN + AUDIT_PLAN
```

## Context supplied
- `.github/prompts/metadata_centralization_audit_and_refactor.prompt.md` (v2.0), `.github/instructions/architecture.instructions.md`
- `.github/agents/plan-architect.agent.md`, `.github/agents/performance-auditor.agent.md`
- `.ai/architecture.md`, `.ai/runtime.md`, `.ai/CURRENT_STATE.md`; código de `src/util_bbdd/` (solo lectura)
- Banco `util_bbdd_bench_*` (5 contenedores) + SQLite local
- Web (2026-10-03): SQLAlchemy 2.0 reflection/whatsnew, SQLite PRAGMA functions, MySQL 8.4 y MariaDB INFORMATION_SCHEMA, SQL Server INFORMATION_SCHEMA, Oracle ALL_TAB_COLUMNS

## AI output summary
- Revalidado el §2 del prompt (medido sobre v0.29.0) contra v0.30.0: `comparar/_routine_fetchers.py` ya no tiene SQL inline; resto confirmado o ampliado.
- Inventario con escaneo `ast` (`bench/scan_catalog.py`): 4 mecanismos de lectura (registry JSON, constructores `metadata/`, adaptadores sin uso, `Inspector`), 174 constructores de SQL, 34 llamadas a `Inspector` fuera de `metadata/`, 18 ficheros que importan `metadata.<motor>`, 2 violaciones directas de la Regla #1 (S-1, S-2); Redshift/Snowflake inalcanzables.
- Arnés de medición `bench/md_bench.py`: schemas `zz_*` de 50/500/5000 tablas en 6 motores; 110 mediciones de 7 flujos (`results/*.json`).
- Micro-benchmarks: PostgreSQL `information_schema` vs `pg_catalog`; Oracle literales vs binds y `ALL_*` vs `USER_*`; MySQL/MariaDB FK por schema; perfil de `migrate`.
- Hallazgos colaterales reproducidos: H-10 (`get_routine_ddl` PG siempre falla), H-17 (`get_routine_parameters` SQL Server siempre falla), H-16 (FK MySQL/MariaDB cuadrática), H-14 (`migrate` cuadrático en CPU), H-12 (literales → hard parse en Oracle, 6,6×), H-11, H-13, H-15.
- Diseño (`03_DISENO.md`), borrador ADR-003, plan por grupos (`04_PLAN.md`) y AUDIT_PLAN (`05_AUDIT_PLAN.md`): **GO_CONDICIONAL**.
- (PLAN) Sin cambios en `src/`, `tests/`, `docs/` ni configuración.
- Usuario: «IMPLEMENT, acepto recomendación» → D9-1 = retirar Redshift/Snowflake; D9-2 = `get_*` con modelos tipados.
- IMPLEMENT · HF (`/hotfix`): H-10 (`managers/_metadata_context.py`: `esquema` también en PostgreSQL/HSQLDB) y H-17
  (`data/sql_queries.json`: `parametros_rutina` de SQL Server sin `PARAMETER_DEFAULT`). Test unitario
  `tests/unit/test_metadata_request_params_resolve.py` (falla sin el fix en PG/HSQLDB) e integración
  `tests/integration/metadata/test_routine_and_view_ddl_engines.py` (falla sin el fix en PG y SQL Server).
- IMPLEMENT · QW (`perf:`): H-16 (`metadata/mariadb/tables.py` FK en dos consultas + `fetch_fk_rules_for_schema_sql`;
  `migrate/extractors/mariadb.py` las une) — 499 FK idénticas en MySQL y MariaDB; `migrate_extract` 5000 tablas MySQL
  20,6 → 5,1 s, MariaDB 8,2 → 3,7 s. H-14 (`migrate/views/transpiler.py`: esquema sqlglot una vez por plan) — DDL
  idéntico en 4 planes de 500 tablas; `plan()` ≈ 6 s → ≈ 1 s.
- IMPLEMENT · A0: dorados por motor (`tests/integration/metadata/characterization/`, `tests/fixtures/metadata_golden/`;
  deterministas en 3 ejecuciones, Oracle sin `doc` por schema no aislado), guarda G1 con trinquete
  (`tests/unit/test_architecture_metadata_rules.py`), conteo de consultas (`tests/unit/metadata/test_query_counts.py`,
  5 `xfail` estrictos verificados con `--runxfail`: p. ej. `manager_scan` 51 → 501, `dump` 127 → 1207 consultas con
  10 → 100 tablas), F0 `scripts/bench_metadata.py` (+ `tests/unit/test_bench_metadata_script.py`, sección en
  `docs/guides/benchmarks.md`).
- Verificación: `ruff check`/`format`, `mypy` (408 ficheros), unitarios 6066 passed + 5 xfailed, integración 590 (tras
  HF/QW) y 101 de `tests/integration/metadata` (tras A0), `gen_arquitectura_capas.py` sin cambios, `mkdocs build --strict`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST / CONTEXT | `00_REQUEST.md`, `00_CONTEXT_SNAPSHOT.md` | emitido |
| PLAN · inventario | `01_INVENTARIO.md` | emitido |
| PLAN · baseline | `02_BASELINE_RENDIMIENTO.md` | emitido |
| PLAN · diseño | `03_DISENO.md`, `ADR-003-borrador.md` | emitido (ADR PROPUESTO) |
| PLAN · plan incremental | `04_PLAN.md` | emitido |
| AUDIT_PLAN | `05_AUDIT_PLAN.md` | GO_CONDICIONAL |
| Arnés y micro-benchmarks | `bench/md_bench.py`, `bench/scan_catalog.py`, `bench/report_baseline.py`, `bench/micro_*.py` | listos para el «después» |
| Resultados crudos | `bench/results/*.json`, `bench/scan_inventory.json` | 110 mediciones |

## Directrices para Futuras IAs
- **[metadata · caminos]**: los managers leen el catálogo con `data/sql_queries.json` (registry, capa 4) en todos los motores salvo MariaDB/MySQL (`managers/_manager_metadata_runtime.py:195-198`); `metadata/<motor>/*_for_schema_sql` solo lo usan `migrate`, `comparar`, `dump` y `bulk`; los adaptadores `fetch_*_sync`/`_async` de `metadata/<motor>/` no tienen ninguna llamada en `src/`.
- **[metadata · motores]**: `metadata/redshift` y `metadata/snowflake` no son alcanzables: `get_supported_db_types()` no los incluye.
- **[metadata · parámetros]**: el SQL de `metadata/` está escrito en el `paramstyle` del driver nativo (`%(schema)s` en psycopg/pymysql, `:owner` en oracledb) porque los managers lo pasan tal cual a `cursor.execute`; para ejecutarlo con SQLAlchemy `text()` hay que traducirlo (o usar `exec_driver_sql`).
- **[rendimiento · catálogo]**: el coste está en el patrón tabla a tabla, no en el motor: con 500 tablas, 70/121/365 s (PG/SQL Server/Oracle) frente a 0,16/0,22/0,27 s leyendo por schema. En PostgreSQL las vistas de constraints de `information_schema` cuestan ≈ 95 ms por consulta según el catálogo **entero** de la base.
- **[rendimiento · Oracle]**: el SQL con literales fuerza hard parse por tabla (FK 540 ms → 21 ms con binds); `USER_*` no mejora a `ALL_*` filtrado por `OWNER` (medido).
- **[rendimiento · MySQL/MariaDB]**: no unir vistas de `information_schema` entre sí (`KEY_COLUMN_USAGE` ⋈ `REFERENTIAL_CONSTRAINTS` es cuadrático: 15,7 s con 5000 tablas); dos consultas unidas en Python.
- **[rendimiento · SQLAlchemy]**: `get_multi_*` solo agrupa en PostgreSQL y Oracle; en SQL Server `get_multi_columns` va tabla a tabla (224 s en `comparar` con 5000 tablas).
- **[medición]**: para contar consultas de los managers hay que parchear `SyncQueryExecutor._execute_sql_with_optional_params` (driver nativo, no pasa por SQLAlchemy) además de escuchar `before_cursor_execute`; lo hace `bench/md_bench.py`.
- **[banco]**: los schemas `zz_md_*` / `zz_util_bbdd_md_*` / usuarios `ZZ_MD_*` siguen creados en el banco para medir el «después»; `md_bench.py teardown` los borra. Oracle necesita `system` (`ORACLE_PASSWORD` del contenedor) para crear usuarios.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- Decisiones del usuario D9-1 (Redshift/Snowflake) y D9-2 (forma pública de `get_*`).
- `/hotfix` de H-10 + H-17 y PRs `perf:` de H-16 + H-14 antes de A0.
- IMPLEMENT por grupos, empezando por A0 → A1, cada uno con aprobación explícita.
