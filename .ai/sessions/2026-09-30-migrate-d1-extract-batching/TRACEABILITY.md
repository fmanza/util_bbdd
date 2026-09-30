# TRACEABILITY

## Session metadata
- id: 2026-09-30-migrate-d1-extract-batching
- fecha: 2026-09-30
- rama: develop
- skill: refactor (D1 de la deuda de `migrate/`) + hotfix (FK compuestas de Oracle)
- fase: paso 0 (medición) → IMPLEMENT → AUDIT_CODE → VERSION (commit sin push)

## Prompt issued
- «Empezar la 0.21.0 por D1» + «Hazlo»: D1 del PLAN de deuda de la sesión `2026-09-29d-migrate-audit` (N+1 en los
  extractores de `migrate`), condicionado a que el paso 0 midiera una ganancia clara (> 50 % de `plan()` con 200 tablas).

## Context supplied
- PLAN/AUDIT_PLAN de D1 en `2026-09-29d-migrate-audit/TRACEABILITY.md`; banco de 5 motores
  (`scripts/bench_env.example.sh`); `.github/prompts/refactor.prompt.md`, `hotfix.prompt.md`.

## AI output summary
- **Paso 0** (`v0/d1_baseline.py`, `v0/results_200.json`): origen de 200 tablas (PK, FK, índice, 5 columnas) y 20 vistas
  por motor; `plan()` lanzaba 823 consultas (4 por tabla + 1 por vista + las de schema). Coste agrupado medido con las
  mismas consultas de la librería sin el filtro por objeto: 8 consultas. Antes → agrupado: SQL Server 20,0 s → 0,26 s;
  Oracle 7,3 → 0,18; MariaDB 1,06 → 0,03; MySQL 0,84 → 0,07; PostgreSQL 2,94 → 1,56 (`v0/d1_pg_breakdown.py`: la FK
  por `INFORMATION_SCHEMA` tarda 1,37 s y la PK 0,15 s → se reescriben sobre `pg_catalog`). Condición cumplida: GO.
- **Referencia de equivalencia** (`v0/d1_golden.py`): IR de los 7 extractores (MySQL y MariaDB en sus 2 variantes)
  sobre un schema con PK/FK compuestas, índice único de varias columnas, DEFAULT/NOT NULL, cadena de FK, vistas y una
  rutina. Determinista salvo los nombres `SYS_Cnnnn` de Oracle (normalizados).
- **Refactor** (una consulta por schema y tipo de objeto, primera columna = nombre del objeto, agrupadas con
  `extractors/_schema_rows.group_by_object`; los `_extract_*` reciben las filas en vez de consultar):
  - PostgreSQL: `fetch_{columns,indexes,pk,fk}_for_schema_sql` (PK/FK sobre `pg_catalog`, reglas con los textos de
    `INFORMATION_SCHEMA`); se retiran las funciones por tabla que solo usaba `migrate`.
  - Oracle: 6 consultas nuevas (`*_for_schema_sql`, cuerpos de rutina en una sola consulta a `ALL_SOURCE`); las
    consultas por tabla se mantienen porque las usan los adaptadores de metadatos.
  - SQL Server: 5 consultas nuevas (incl. cuerpos desde `sys.sql_modules`); se retiran las por tabla.
  - MariaDB/MySQL: 4 + 1 (`fetch_columns_with_type_for_schema_sql`); MySQL elige la consulta de columnas con
    `_columns_for_schema_sql`. Columnas de vistas desde la misma consulta de columnas (PG, SQL Server, MariaDB/MySQL).
  - Tests: los helpers de simulación anteponen el nombre de cada tabla/vista del test a sus filas (misma semántica
    que antes); tests nuevos de 2 consultas para rutinas (Oracle, SQL Server).
- **Bloqueos del entorno**: Docker Desktop parado (arrancado por el usuario); el Oracle del banco no abría la PDB
  (`ORA-12954`: `users01.dbf` 12,5 GB > límite de 12 GB de Oracle Free) → recreado con autorización del usuario
  (`docker compose -f docker-compose.bench.yml up -d --wait --force-recreate oracle`; sin volúmenes).
- **Hotfix `c16702e`** (destapado por la referencia): `metadata/oracle/tables.fetch_fk_constraint_sql` no emparejaba
  las posiciones de FK y clave referenciada → una FK de N columnas salía con N×N, en orden variable. Flujo: D1 aparcado
  con `git stash`, test de integración `tests/integration/test_oracle_composite_fk.py` (9 columnas → 3), fix
  `rcc.position = cc.position`, commit, `stash pop`, misma condición en `fetch_fk_for_schema_sql`, referencia de Oracle
  regenerada con el código corregido.
- **Verificación final**: IR idéntico en los 7 extractores; `plan()` con 200 tablas: SQL Server 0,33 s, Oracle 0,13 s,
  PostgreSQL 0,09 s, MariaDB 0,07 s, MySQL 0,11 s (8 consultas en todos; `v0/results_200_after*.json`); ruff, format,
  mypy (385 ficheros), pytest 5664/226, integración 365; diagrama de capas sin cambios.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Medición paso 0 y final | `v0/d1_baseline.py`, `v0/d1_pg_breakdown.py`, `v0/results_*.json` | completado |
| Referencia de equivalencia | `v0/d1_golden.py`, `v0/golden_before.json`, `v0/golden_after.json` | completado |
| Refactor D1 | `src/util_bbdd/migrate/extractors/{_schema_rows,postgresql,oracle,sqlserver,mariadb,mysql}.py`, `src/util_bbdd/metadata/{postgresql,oracle,sqlserver,mariadb,mysql}/tables.py` | completado |
| Tests D1 | `tests/unit/migrate/test_*extractor*.py`, `test_planner*.py`, `test_mysql_migration.py`, `test_view_strategy.py` | completado |
| Hotfix FK Oracle | `c16702e` | completado |

## Directrices para Futuras IAs
- **[migrate/extractors]**: los extractores leen por schema: una consulta por tipo de objeto con el nombre del
  objeto en la primera columna y el resto en el orden de la antigua consulta por tabla; `group_by_object` agrupa por
  nombre exacto. No reintroducir consultas por tabla: 200 tablas eran 823 consultas.
- **[migrate/tests]**: los helpers `_make_manager` de los tests de extractores simulan las consultas por schema
  repitiendo las filas del test para cada tabla (`per_object`); un test nuevo debe dar las filas SIN el nombre y dejar
  que el helper lo anteponga.
- **[metadata/postgresql]**: en PostgreSQL, las FK y PK por `INFORMATION_SCHEMA` son muy lentas por schema (1,4 s con
  200 tablas); `pg_catalog` (`pg_constraint` + `unnest(conkey, confkey) WITH ORDINALITY`) da lo mismo en ms.
- **[metadata/oracle]**: al unir `all_cons_columns` de una FK con los de la constraint referenciada hay que emparejar
  `position`; sin ello una FK de N columnas sale N×N.
- **[herramientas]**: comparar el IR antes/después (`v0/d1_golden.py`) contra el banco es lo que destapó el bug de las
  FK de Oracle: vale para cualquier refactor de extractores. Oracle cambia en cada creación los nombres `SYS_Cnnnn`.
- **[banco]**: Oracle Free limita la PDB a 12 GB; si `users01.dbf` los supera, la PDB no abre (`ORA-12954`) y no se
  puede limpiar desde dentro: se recrea el contenedor (sin volúmenes; `APP_USER=bench` se vuelve a crear solo).

## Veredicto final
Veredicto: GO — D1 implementado y verificado (IR idéntico, −87 % a −98 % en `plan()`), commit sin push. Siguiente de
la 0.21.0: D2 (`oracle_type` → `source_type` + `category`) y D3 (comentarios PostgreSQL/SQL Server).
