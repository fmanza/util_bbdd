# 02 · BASELINE DE RENDIMIENTO — extracción de metadatos (v0.30.0)

Sesión `2026-10-03-metadata-centralization` · Performance Auditor · medido el 2026-10-03

## Método

- **Arnés**: `bench/md_bench.py` (se promueve a `scripts/bench_metadata.py` en F0). `setup` crea, por motor y volumen,
  un schema aislado con N tablas `t00000…` (6 columnas, PK, UK, FK a la tabla anterior, índice secundario), N/10
  vistas y N/50 funciones + N/50 procedures; `run` mide cada flujo; `teardown` lo borra.
- **Aislamiento**: PostgreSQL `zz_md_<N>` (schemas en la base `bench`), MySQL/MariaDB/SQL Server bases
  `zz_util_bbdd_md_<N>`, Oracle usuarios `ZZ_MD_<N>` (creados con `system`), SQLite un fichero por volumen. Los tres
  volúmenes conviven: en PostgreSQL la base tiene **5624 tablas** en total (los tres schemas + las del banco), lo que
  reproduce una base con varios schemas.
- **Conteo**: cada sentencia se registra en los dos caminos de ejecución de la librería — `SyncQueryExecutor` (managers,
  adaptadores, `migrate`, `doc`, `analysis`; driver nativo) y los eventos `before/after_cursor_execute` de SQLAlchemy
  (`Inspector`, `comparar`, `dump`, `bulk`) — y se clasifica como «de catálogo» por su texto. `tcat` = suma del tiempo
  de ejecución de las sentencias de catálogo.
- **Repeticiones**: mediana de 3 en 50 y 500 tablas; 1 en 5000 (se indica). Memoria: pico de `tracemalloc`.
- **Flujos**:

| Flujo | Qué ejecuta | Representa |
|---|---|---|
| `manager_scan` | `get_tables/views/routines` + por tabla `get_columns/indices/primary_keys/foreign_keys/unique_constraints` | Patrón de acceso de `doc`/`analysis` y de cualquier usuario de los managers |
| `doc_html` | `DatabaseDocumentation(formatos=["html"], grafo desactivado).generate()` | Documentación |
| `comparar` | `SchemaComparator().compare()` del schema contra sí mismo, con routines | Comparación |
| `migrate` | `MigrationPlanner(origen → destino).plan(manager, schema)` | Migración DDL |
| `dump` | `DumpOrchestrator.run()` del schema sobre sí mismo con tablas vacías | Coste de introspección + DDL de constraints del volcado |
| `bulk` | `BulkCrud.bulk_insert_from_df` de 10 filas en una tabla | Coste fijo de introspección por operación |

- **Entorno**: Windows 11, Python del `venv` del repo, contenedores `util_bbdd_bench_*` en el mismo host
  (PostgreSQL 17, MySQL 8.4, MariaDB 11.4, SQL Server 2022, Oracle 23 Free). Los tiempos son indicativos (host
  compartido); el **número de consultas** es determinista y es la métrica principal.

## Fuentes externas (consultadas 2026-10-03)

| Afirmación | Fuente |
|---|---|
| SQLAlchemy 2.0 agrupa la reflexión en PostgreSQL (≈ 3× más rápido) y Oracle (≈ 10×); 250 tablas: PG 8,2 → 3,3 s, Oracle 60,4 → 6,8 s; MySQL/MariaDB y SQLite no se reescribieron; SQL Server podría beneficiarse en el futuro | [What's New in SQLAlchemy 2.0 — reflection](https://docs.sqlalchemy.org/en/20/changelog/whatsnew_20.html) |
| `Inspector` cachea por instancia y `clear_cache()` lo vacía | [SQLAlchemy 2.0 — Reflecting Database Objects](https://docs.sqlalchemy.org/en/20/core/reflection.html) |
| SQLite: los PRAGMA sin efectos laterales se usan como funciones tabla (`pragma_index_list`, …) y se pueden unir a `sqlite_schema` (≥ 3.16.0) | [SQLite PRAGMA — PRAGMA functions](https://www.sqlite.org/pragma.html) |
| MySQL 8.4: `INFORMATION_SCHEMA` sobre el diccionario transaccional; consultar solo metadatos estáticos; estadísticas cacheadas con `information_schema_stats_expiry` (86 400 s) | [MySQL 8.4 — Optimizing INFORMATION_SCHEMA Queries](https://dev.mysql.com/doc/refman/8.4/en/information-schema-optimization.html) |
| MariaDB/MySQL: un `TABLE_SCHEMA`/`TABLE_NAME` constante evita recorrer el directorio de datos (`skip_open_table`, `open_frm_only`) | [MariaDB — EXPLAIN](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/analyze-and-explain-statements/explain), [MySQL 5.7 — Optimizing INFORMATION_SCHEMA Queries](https://dev.mysql.com/doc/refman/5.7/en/information-schema-optimization.html) |
| SQL Server: las vistas `INFORMATION_SCHEMA` son una de varias vías de metadatos, limitada por la visibilidad de metadatos | [System Information Schema Views (Transact-SQL)](https://learn.microsoft.com/en-us/sql/relational-databases/system-information-schema-views/system-information-schema-views-transact-sql) |
| Oracle: `ALL_TAB_COLUMNS` (accesibles) frente a `USER_TAB_COLUMNS` (propias); casos reales de vistas de diccionario muy lentas | [ALL_TAB_COLUMNS](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/ALL_TAB_COLUMNS.html), [Oracle community: query dba_tab_columns super slow](https://community.oracle.com/mosc/discussion/4308881/query-dba-tab-columns-was-super-slow) — **hipótesis**, no medida aún (`USER_*` vs `ALL_*`) |

## Resumen ejecutivo

1. **El coste está en el patrón tabla a tabla, no en el motor.** Para el mismo schema de 500 tablas, recorrer
   columnas, índices, PK, FK y UK con los managers (`manager_scan`, 2503 consultas) cuesta en catálogo **70 s en
   PostgreSQL, 121 s en SQL Server y 365 s en Oracle**; la extracción por schema que ya existe en `metadata/`
   (`migrate_extract`, 9 consultas, que además trae vistas y routines) cuesta **0,16 s, 0,22 s y 0,27 s**: entre
   440× y 1350× menos.
2. **El coste por consulta crece con el catálogo**, así que los flujos tabla a tabla son peor que lineales:
   SQL Server pasa de 9 ms por consulta (50 tablas) a 48 ms (500) y ≈ 55 ms (5000); en PostgreSQL las vistas de
   constraints de `information_schema` cuestan ≈ 95 ms por consulta **sea cual sea el schema**, porque dependen del
   catálogo entero de la base (5624 tablas).
3. **Extrapolado a 5000 tablas** (muestra medida × 50/250), un recorrido completo de los managers costaría ≈ 14 min en
   PostgreSQL, ≈ 23 min en SQL Server y ≈ 75 min en Oracle; la lectura por schema, 1,4 s, 2,4 s y 4,0 s.
4. **Oracle paga sobre todo el hard parse** de SQL con literales (H-12): con las mismas consultas por tabla pero con
   bind variables, 749 → 113 ms por tabla (FK: 540 → 21 ms).
5. Los flujos que ya leen por schema (`migrate`, `comparar` en PostgreSQL/Oracle) son los rápidos; `comparar` en
   SQL Server (columnas tabla a tabla en `get_multi_columns`: 224 s con 5000 tablas) y en SQLite/MySQL/MariaDB
   (11–61 mil consultas) aún no.
6. `dump` lee la misma información **3 veces por tabla** (PK, columnas) y recarga los tipos de PostgreSQL en cada
   reflexión: 68 130 consultas de catálogo (105 s) para volcar 5000 tablas **vacías** en PostgreSQL.
7. `bulk` tiene un coste fijo pequeño por operación (3–14 consultas), salvo SQL Server y Oracle con 5000 tablas
   (≈ 1 s): la reflexión de una tabla no debe arrastrar el tamaño del catálogo.
8. Dos consultas por schema ya existentes son **cuadráticas** en MySQL/MariaDB (FK, H-16) y la transpilación de vistas
   de `migrate` es cuadrática en CPU (H-14): ambas son mejoras rápidas independientes.

## Tablas por flujo

Celda: `consultas de catálogo · tiempo de catálogo / tiempo total`. «muestra N» = `manager_scan` recorre solo N tablas
del schema de 5000 (el listado es completo). «—» = no medido (coste prohibitivo; ver extrapolación). `migrate` en
5000 tablas no se mide por H-14 (transpilación cuadrática); `migrate_extract` mide solo su extracción.

#### `manager_scan`

| Motor | 50 tablas | 500 tablas | 5000 tablas |
|---|---|---|---|
| sqlite | 252 · 0.02 / 0.08 s | 2.502 · 0.16 / 0.74 s | 502 · 0.10 / 0.28 s (muestra 100) |
| postgresql | 253 · 6.83 / 6.96 s | 2.503 · 70.06 / 71.09 s | 503 · 16.69 / 17.13 s (muestra 100) |
| mysql | 253 · 0.26 / 0.36 s | 2.503 · 2.49 / 3.15 s | 503 · 0.67 / 0.95 s (muestra 100) |
| mariadb | 253 · 0.18 / 0.26 s | 2.503 · 1.68 / 2.40 s | 503 · 0.49 / 0.76 s (muestra 100) |
| sqlserver | 253 · 2.35 / 2.46 s | 2.503 · 121.39 / 122.50 s | 503 · 27.91 / 28.20 s (muestra 100) |
| oracle | 253 · 23.64 / 24.60 s | 2.503 · 365.30 / 373.58 s | 103 · 18.03 / 18.69 s (muestra 20) |

#### `doc_html`

| Motor | 50 tablas | 500 tablas | 5000 tablas |
|---|---|---|---|
| sqlite | 57 · 0.01 / 0.36 s | 552 · 0.04 / 1.71 s | — |
| postgresql | 209 · 5.12 / 5.85 s | 2.063 · 53.50 / 57.20 s | — |
| mysql | 59 · 0.08 / 0.54 s | 554 · 0.75 / 2.36 s | — |
| mariadb | 59 · 0.06 / 0.36 s | 554 · 0.62 / 2.09 s | — |
| sqlserver | 61 · 0.08 / 0.42 s | 583 · 2.53 / 4.27 s | — |
| oracle | 210 · 23.27 / 24.59 s | 2.073 · 357.81 / 368.09 s | — |

#### `comparar`

| Motor | 50 tablas | 500 tablas | 5000 tablas |
|---|---|---|---|
| sqlite | 616 · 0.03 / 0.12 s | 6.106 · 0.32 / 1.34 s | 61.006 · 24.66 / 55.87 s |
| postgresql | 32 · 0.14 / 0.30 s | 122 · 0.45 / 1.16 s | 1.026 · 5.17 / 12.21 s |
| mysql | 122 · 0.11 / 0.23 s | 1.148 · 1.30 / 2.17 s | 11.408 · 13.51 / 22.38 s |
| mariadb | 122 · 0.08 / 0.19 s | 1.148 · 0.76 / 1.67 s | 11.408 · 8.35 / 17.05 s |
| sqlserver | 126 · 0.21 / 0.54 s | 1.116 · 1.45 / 4.24 s | 11.016 · 229.41 / 260.97 s |
| oracle | 28 · 0.98 / 1.20 s | 118 · 2.26 / 3.36 s | 1.072 · 9.43 / 18.48 s |

#### `migrate`

| Motor | 50 tablas | 500 tablas | 5000 tablas |
|---|---|---|---|
| sqlite | n/a | n/a | — |
| postgresql | 9 · 0.05 / 0.41 s | 9 · 0.16 / 21.43 s | — |
| mysql | 9 · 0.04 / 0.33 s | 9 · 0.38 / 18.57 s | — |
| mariadb | 9 · 0.31 / 0.56 s | 9 · 0.55 / 18.99 s | — |
| sqlserver | 9 · 0.08 / 0.40 s | 9 · 0.19 / 19.19 s | — |
| oracle | 9 · 0.41 / 0.73 s | 9 · 0.91 / 19.31 s | — |

#### `migrate_extract`

| Motor | 50 tablas | 500 tablas | 5000 tablas |
|---|---|---|---|
| sqlite | — | — | n/a |
| postgresql | 9 · 0.05 / 0.12 s | 9 · 0.16 / 0.45 s | 9 · 1.36 / 4.25 s |
| mysql | 9 · 0.07 / 0.13 s | 9 · 0.38 / 0.73 s | 9 · 17.59 / 20.64 s |
| mariadb | 9 · 0.19 / 0.23 s | 9 · 0.57 / 0.88 s | 9 · 4.94 / 8.15 s |
| sqlserver | 9 · 0.07 / 0.17 s | 9 · 0.22 / 0.57 s | 9 · 2.40 / 5.91 s |
| oracle | 9 · 0.24 / 0.36 s | 9 · 0.27 / 0.66 s | 9 · 3.98 / 7.33 s |

#### `dump`

| Motor | 50 tablas | 500 tablas | 5000 tablas |
|---|---|---|---|
| sqlite | 607 · 0.03 / 0.64 s | 6.007 · 0.38 / 6.87 s | 60.007 · 18.66 / 81.64 s |
| postgresql | 709 · 1.15 / 3.25 s | 7.009 · 11.02 / 28.88 s | 68.130 · 105.22 / 288.69 s |
| mysql | 154 · 0.17 / 3.12 s | 1.504 · 1.32 / 29.23 s | 15.004 · 14.96 / 331.41 s |
| mariadb | 154 · 0.10 / 1.68 s | 1.504 · 1.05 / 17.06 s | 15.004 · 10.53 / 164.43 s |
| sqlserver | 356 · 1.09 / 3.68 s | 3.506 · 22.96 / 44.47 s | — |
| oracle | 702 · 1.45 / 4.65 s | 7.002 · 14.02 / 43.54 s | — |

#### `bulk`

| Motor | 50 tablas | 500 tablas | 5000 tablas |
|---|---|---|---|
| sqlite | 14 · 0.00 / 0.04 s | 14 · 0.00 / 0.03 s | 14 · 0.04 / 0.10 s |
| postgresql | 14 · 0.02 / 0.11 s | 14 · 0.02 / 0.12 s | 14 · 0.02 / 0.11 s |
| mysql | 3 · 0.01 / 0.06 s | 3 · 0.01 / 0.04 s | 3 · 0.01 / 0.05 s |
| mariadb | 3 · 0.00 / 0.03 s | 3 · 0.00 / 0.04 s | 3 · 0.00 / 0.06 s |
| sqlserver | 9 · 0.02 / 0.14 s | 9 · 0.08 / 0.21 s | 9 · 0.95 / 1.05 s |
| oracle | 7 · 0.02 / 0.16 s | 7 · 0.02 / 0.11 s | 7 · 1.24 / 1.70 s |

## Comparación clave: tabla a tabla frente a por schema (tiempo de catálogo)

| Motor | 500 tablas: `manager_scan` | 500 tablas: `migrate_extract` | Factor | 5000 tablas: `manager_scan` extrapolado | 5000 tablas: `migrate_extract` |
|---|---|---|---|---|---|
| PostgreSQL | 70,1 s (2503 consultas) | 0,16 s (9) | ≈ 440× | ≈ 835 s (16,7 s / 100 tablas) | 1,36 s |
| SQL Server | 121,4 s | 0,22 s | ≈ 550× | ≈ 1395 s (27,9 s / 100) | 2,40 s |
| Oracle | 365,3 s | 0,27 s | ≈ 1350× | ≈ 4510 s (18,0 s / 20) | 3,98 s |
| MySQL | 2,5 s | 0,38 s | ≈ 7× | ≈ 34 s | 17,6 s (H-16: FK 15,7 s) |
| MariaDB | 1,7 s | 0,57 s | ≈ 3× | ≈ 25 s | 4,9 s (H-16: FK 4,5 s) |
| SQLite | 0,16 s | n/a | — | ≈ 5 s | n/a |

Notas: `migrate_extract` incluye además vistas y routines, que `manager_scan` no lee. En MySQL/MariaDB el coste tabla a
tabla es bajo (≈ 1 ms por consulta) gracias al diccionario transaccional; aun así, la lectura por schema gana en cuanto
se corrige H-16.

## Micro-benchmarks (causas)

### PostgreSQL — `information_schema` frente a consultas por schema (`bench/micro_pg_catalog.py`)

Base con 5624 tablas. Mediana de 5 (50) / 3 (5000) ejecuciones.

| Consulta | Schema de 50 tablas | Schema de 5000 tablas |
|---|---|---|
| registry `columnas_tabla` (1 tabla) | 3,0 ms | 3,3 ms |
| registry `claves_primarias` (1 tabla) | 3,5 ms | 36,1 ms |
| registry `claves_foraneas` (1 tabla) | **95,2 ms** | **94,1 ms** |
| registry `claves_unicas` (1 tabla) | 32,6 ms | 32,1 ms |
| registry `indices` (1 tabla, `pg_catalog`) | 1,8 ms | 4,4 ms |
| `metadata` `fetch_columns_for_schema_sql` (todo el schema) | 9,9 ms (315 filas) | 593,8 ms (31 500 filas) |
| `metadata` `fetch_pk_for_schema_sql` | 2,6 ms | 31,9 ms |
| `metadata` `fetch_fk_for_schema_sql` | 5,5 ms | 89,0 ms (4999 FK) |
| `metadata` `fetch_indexes_for_schema_sql` | 3,1 ms | 50,6 ms |

Las FK de **una** tabla por `information_schema` cuestan lo mismo que las 4999 FK del schema por `pg_catalog`. Las
columnas por schema pagan `col_description(…::regclass)` por fila (riesgo P2 del AUDIT_PLAN).

### Oracle — literales frente a bind variables (`bench/micro_oracle_binds.py`, H-12)

30 tablas distintas por variante (cada literal es un texto SQL nuevo), schema de 500 tablas, servidor sin carga.

| Consulta del registry | Literal (hoy) | Bind variables |
|---|---|---|
| `columnas_tabla` | 70,7 ms/tabla | 4,0 ms/tabla |
| `claves_primarias` | 36,2 | 38,8 |
| `claves_foraneas` | **539,8** | **21,1** |
| `claves_unicas` | 34,7 | 37,8 |
| `indices` | 67,1 | 11,0 |
| **Total por tabla** | **748,5** | **112,7** |

### Oracle — `ALL_*` frente a `USER_*` (`bench/micro_oracle_catalog.py`, H-ORA1)

Schema de 500 tablas, owner = usuario conectado, mediana de 3: columnas 32,7 vs 45,3 ms; constraints 44,5 vs 41,0 ms;
índices 42,7 vs 33,1 ms. **Sin diferencia significativa: H-ORA1 descartada**; se mantiene `ALL_*` filtrado por
`OWNER` (sirve también cuando owner ≠ usuario). Con 50 tablas y el banco cargado las consultas de constraints por owner
fueron mucho más lentas (FK 1,8 s): H-ORA2 (estadísticas de diccionario del contenedor) queda abierta para F, con
permiso del usuario porque cambia el estado del banco.

### MySQL / MariaDB — FK por schema (`bench/micro_mysql_fk.py`, H-16)

| Variante | MySQL 500 | MySQL 5000 | MariaDB 5000 |
|---|---|---|---|
| Actual (`KEY_COLUMN_USAGE` ⋈ `REFERENTIAL_CONSTRAINTS`) | 162 ms | **15 744 ms** | **4468 ms** |
| Join con `rc.CONSTRAINT_SCHEMA` constante + `TABLE_NAME` | 7,9 ms | 71,7 ms | 3680 ms |
| Dos consultas sin join (kcu + rc), unidas en Python | 4,7 + 3,3 ms | 33 + 19 ms | 98 + 85 ms |

### `migrate` — perfil de CPU (H-14)

PostgreSQL, 500 tablas / 50 vistas: `MigrationPlanner.plan()` 20,4 s, de ellos 19,6 s en `transpile_views` y 17,7 s en
`_schema_for_sqlglot` (`migrate/views/transpiler.py:92`), que construye 150 000 tipos de sqlglot (3000 columnas × 50
vistas). Catálogo: 0,16 s.

## Huellas dominantes por flujo (5000 tablas)

| Flujo / motor | Sentencia dominante | Veces | Tiempo |
|---|---|---|---|
| `manager_scan` PostgreSQL (muestra 100) | FK por `information_schema` (registry) | 100 | 9,35 s de 16,7 |
| `manager_scan` SQL Server (muestra 100) | FK (`sys.foreign_keys` + `INFORMATION_SCHEMA`) | 100 | 8,50 s de 27,9 |
| `comparar` SQL Server | `get_columns` de SQLAlchemy (`sys.columns`), dos lados | 10 000 | 223,8 s de 229,4 |
| `dump` PostgreSQL | `get_columns` / `get_pk_constraint` (×3 por tabla) + tipos `pg_type` por reflexión | 15 000 / 15 000 / 10 004 | 28,4 / 21,9 / 24,0 s |

## Memoria

Pico de `tracemalloc` del flujo completo con 5000 tablas: `migrate_extract` 30–43 MB (filas + IR), `comparar`
93–126 MB, `dump` 138–214 MB. Un snapshot del schema de 5000 tablas cabe holgadamente; se medirá su tamaño propio en A1
(objetivo: ≤ 50 MB para 5000 tablas × 6 columnas).

## Condiciones de la medición

- Tanda de MySQL/MariaDB (50/500) y de 5000 tablas ejecutada en paralelo con la de Oracle (contenedores distintos,
  mismo host): los tiempos de esas tandas pueden estar inflados hasta un ≈ 20 % (estimado); el número de consultas no.
- Oracle 5000 (`manager_scan`) con muestra de 20 tablas; PostgreSQL/SQL Server/MySQL/MariaDB/SQLite con 100.
- Resultados crudos: `bench/results/<motor>_<volumen>_<flujo>.json` (incluyen las 8 huellas más frecuentes y las 5 más
  lentas); tablas regenerables con `python bench/report_baseline.py`.
- Los schemas `zz_*` del banco siguen creados para medir el «después» de cada grupo; se borran con
  `python bench/md_bench.py teardown --engines all --volumes 50,500,5000`.
