# TRACEABILITY

## Session metadata
- id: 2026-10-02g-comparar-audit
- fecha: 2026-10-02 / 2026-10-03
- rama: develop
- skill: audit_code → PLAN + AUDIT_PLAN → IMPLEMENT por entregas (fix / perf / refactor) → audit_code de cada entrega;
  hotfix; version_closure
- fase: AUDIT_CODE + PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (cierre de sesión, sin release)

## Prompt issued
`/audit-code src\util_bbdd\comparar todo, poner enfasis en el rendimiento, mirar en el proyecto si se puede reutilizar
funcionalidad`. Después, aprobaciones sucesivas: «PLAN y AUDIT-PLAN», entrega 1 (fix), `/audit-code` de la entrega 1
(A1–A3), entrega 2 (perf), su `/audit-code` (D1), entrega 3 (refactor + B8), `/hotfix` de
`metadata/postgresql/routines.py`, FKs e índices con nombre generado, perf de SQL Server, `scripts/bench_compare.py` y
`/version-closure`.

## Context supplied
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md`; `.github/prompts/audit_code|hotfix|version_closure.prompt.md` y sus
  agentes; `.github/instructions/architecture.instructions.md` (REGLA #1 y #2), `sync.instructions.md`.
- `scripts/gen_arquitectura_capas.py` (capas de la Regla #6: `comparar` 6, `metadata` 5, `dump` 7).
- Banco `docker-compose.bench.yml` (PostgreSQL 17, MySQL 8.4, MariaDB 11.4, SQL Server 2022, Oracle 23 Free) con
  `scripts/bench_env.example.sh`; contraseña leída de los contenedores (autorizado), nunca mostrada.

## AI output summary
- **AUDIT_CODE inicial de `comparar/`** (RECHAZADO): B1 routines PG vacías tras un agregado (transacción abortada),
  B2 SQL de SQLite no ejecutable, B3 sintaxis T-SQL inválida, B4 vistas/routines/columnas de índices y FKs sensibles a
  mayúsculas entre motores, B5 `SHOW CREATE` sin schema en MariaDB, B6 contador Mermaid, B7 `WINDOW`/sobrecargas PG,
  B8 orden de `CREATE TABLE`, S1 inyección por `\` en comentarios MariaDB; P1–P3 N+1 de reflexión y routines.
  Benchmark inicial: 1.202 consultas por lado con 200 tablas en SQLite.
- **Entrega 1** `0f1c6b3 fix(comparar)`: B1–B7 y S1; fetchers lanzan `MetadataIntrospectionError` y el comparador
  omite las routines (cambio de contrato documentado); MySQL con comparación de routines; consulta nueva
  `metadata/postgresql/routines.fetch_routines_with_definition_for_schema_sql`. Verificado en PG 17 (agregado,
  sobrecargas), MariaDB 11.4 y MySQL 8.4 (schema distinto, S1 ida y vuelta) y SQL Server 2022 (T-SQL ejecutado).
  Su `/audit-code`: A1 (regresión propia: firma PG impedía emparejar con otros motores), A2, A3 corregidos.
- **Entrega 2** `a7f2938 perf(comparar)`: `comparar/_prefetch.py` con `Inspector.get_multi_*`; FKs de SQL Server por
  schema; routines de SQL Server y Oracle en una consulta. Destapó y corrigió: SQL Server solo comparaba la primera
  routine (pymssql descartaba el listado) y Oracle marcaba todas las routines como modificadas (`DBMS_METADATA` con
  owner). Paridad con la reflexión tabla a tabla en los 5 motores (`tests/integration/test_comparar_prefetch_engines.py`).
  Su `/audit-code`: APROBADO, D1 (cifras mezcladas) corregido.
- **Entrega 3** `2ff6a3b refactor(comparar)`: `DdlNormalizer` → `comparar/_ddl.py` (reexportado en
  `reporters/_base.py`); SQL de MariaDB → `metadata/mariadb/tables.py`; `Any` → `Reflected*` de SQLAlchemy. R2
  (unificar resúmenes) descartado. `8a9f0b0 fix(comparar)`: B8, orden de `CREATE TABLE` por FKs (Kahn por niveles).
- **Hotfix** `bcdd0e9 hotfix(metadata)`: `fetch_routines_sql` de PostgreSQL fallaba entera con un agregado; `CASE` sobre
  `prokind`, mismas columnas y filas. Test de integración escrito primero (falló con psycopg 3) y después en verde.
- `fcd5452` / `252872e fix(comparar)`: FKs e índices con nombre generado por el motor se emparejan por estructura
  (`_match_by_structure`); patrones verificados en el banco. SQL Server y Oracle: 200 → 20 tablas con diferencias.
- `1ea0579 perf(comparar)`: PK, índices y comentarios de SQL Server con consultas por schema (formato exacto de
  `MSDialect`, comparado con dict completo contra SQL Server real, con `INCLUDE` e índice filtrado).
- `5b9319f chore(scripts)`: `scripts/bench_compare.py` + `tests/unit/test_bench_compare_script.py` + guía.
- Archivos (29, +3231/−818): `src/util_bbdd/comparar/{_ddl,_prefetch,_routine_fetchers,comparator}.py`,
  `comparar/reporters/{_base,markdown_reporter,sql_reporter}.py`, `metadata/{mariadb/tables,oracle/tables,
  postgresql/routines,sqlserver/constraints,sqlserver/tables}.py`, 10 ficheros de tests, `scripts/bench_compare.py`,
  `scripts/gen_arquitectura_capas.py`, `docs/{api/schema_comparator,architecture,guides/benchmarks}.md`, SVG de capas,
  `CHANGELOG.md`.

## Tests and evidence (ejecutado en esta sesión)
- Cierre sobre `HEAD` (`5b9319f`): `ruff check src tests scripts` limpio; `mypy src tests/unit/test_protocol_conformance.py`
  sin errores (408 ficheros); `pytest` **6188 passed, 442 skipped**; `zensical build --strict` sin avisos;
  `python -m build` correcto (en el scratchpad); `tests/unit/test_docs_version.py` 6 passed.
- Entorno de referencia (`pip install -e ".[dev,docs]"`, reinstalado al cerrar): mismos **6188 passed, 442 skipped**,
  ya sin el aviso de `tests/conftest.py`. El aviso de la sesión era por los nombres de distribución (`psycopg2-binary`,
  `types-openpyxl`): el módulo `psycopg2` sí estaba instalado, así que los recuentos de la sesión eran comparables.
  Frente a la referencia de la 0.29.0 (6101/436): +87 tests y +6 saltos de esta sesión y de la anterior.
- **Integración completa** contra los 5 servidores del banco (`tests/integration`, URLs de `scripts/bench_env.example.sh`):
  **588 passed** (582 de la referencia + 5 de `test_comparar_prefetch_engines.py` + 1 de
  `test_postgresql_routines_aggregates.py`).
- Benchmark (`scripts/bench_compare.py`, 200 tablas, con routines): PostgreSQL 4,23 → 0,18 s (2.450 → 62 sentencias);
  Oracle 5,18 → 0,26 s (2.086 → 58); SQL Server 12,23 → 0,88 s (2.852 → 456; pyodbc 1,08 s); MariaDB 1,24 → 0,35 s;
  MySQL 1,37 → 0,43 s. Mismas diferencias encontradas antes y después salvo las corregidas a propósito.

## Known limitations
- Columnas de SQL Server siguen tabla a tabla (`get_multi_columns` no nativo): el comparador compara tipos de
  SQLAlchemy, que no se reconstruyen desde SQL propio.
- Vistas: una consulta por vista (sin `get_multi` de definiciones). MariaDB/MySQL: un `SHOW CREATE` por routine.
- Comparar dos schemas de la misma BD da vistas/routines «modificadas» si su DDL lleva el nombre del schema (PG
  `pg_get_functiondef`, SQL Server `sql_modules`).
- `SqlDiffReporter`: `DROP TABLE` de tablas eliminadas sin orden por FKs (no tiene inspector destino); `DROP FUNCTION`
  de una sobrecarga PG cita `"f(integer)"` como un único identificador; sin schema en el SQL de SQL Server.
- Regla columnstore de índices de SQL Server solo cubierta por test unitario (el banco no tiene columnstore).
- Índices con nombre generado en MySQL/MariaDB (nombre = columna) no se reconocen como generados (estables dentro del
  motor).

## Directrices para Futuras IAs
- **[comparar]**: La reflexión de tablas pasa por `comparar/_prefetch.py` (`prefetch_table_metadata` +
  `TableMetadata.get(kind, tabla)`): `get_multi_*` y, en SQL Server, `_MSSQL_QUERIES` (PK, índices, FKs, comentarios por
  schema con el formato exacto de `MSDialect`). Lo no precargado vuelve a la llamada tabla a tabla: los errores se
  propagan igual que sin precarga.
- **[comparar]**: `get_multi_*` es nativo (una consulta por schema) solo en PostgreSQL y Oracle; en MySQL, MSSQL y
  SQLite SQLAlchemy itera tabla a tabla, pero con **una** conexión (`Inspector._operation_context`): por eso MariaDB/MySQL
  bajaron de 1,2 s a 0,35 s con el mismo número de consultas. Oracle reparte `filter_names` en lotes de 500.
- **[comparar]**: `SchemaComparator._GENERATED_FK_NAME_PATTERNS` / `_GENERATED_INDEX_NAME_PATTERNS` +
  `_match_by_structure`: FKs/índices sin pareja por nombre se emparejan por estructura solo si **ambos** nombres son
  generados. Nombres reales del banco: SQL Server `FK__t__col__<hex8>` / `UQ__t__<hex16>`, Oracle `SYS_C\d+` (SQLAlchemy
  lo devuelve en minúsculas), PG `_fkey`/`_key`/`_idx`, MySQL `_ibfk_N` (índices: nombre de la columna).
- **[comparar]**: Routines: `_routine_key` usa `signature` (sobrecargas PG) solo si **todas** las routines de ambos
  lados la traen; si no, por nombre (comparación PG ↔ otros motores). Un fetcher que no puede listar lanza
  `MetadataIntrospectionError` y `_compare_routines` omite la comparación (no comparar contra lista vacía/parcial).
- **[postgresql]**: `pg_get_functiondef` falla con agregados (`prokind = 'a'`) y dentro de una transacción la deja
  abortada: todas las llamadas siguientes de la conexión fallan. Protegerlo siempre con `CASE WHEN prokind ...` (o
  excluir `'a'`); PostgreSQL no evalúa la rama no tomada del `CASE` (comprobado en PG 17).
- **[sqlserver]**: pymssql no admite varios resultados abiertos: ejecutar una consulta dentro del bucle de otra descarta
  el resto del primer listado sin error. Materializar (`.all()`) antes de ejecutar más o usar una sola consulta.
- **[sqlserver]**: `EXEC(...)` no admite llamadas a funciones (`QUOTENAME`) en su argumento: componer la sentencia en
  una variable (`DECLARE @x nvarchar(max) = ...; EXEC(@x)`). Variables T-SQL únicas por bloque (`@df_N`) si van en el
  mismo lote. Un `CASE`/subconsulta por schema sustituye a `fn_listextendedproperty` por tabla.
- **[sqlserver]**: `MSDialect.get_foreign_keys` pone `referred_schema=None` cuando se pide `schema=None` y la FK apunta
  al schema por defecto; un schema de varias partes (`bd.owner`) no lo resuelve `SCHEMA_ID` (devuelve NULL: cero filas
  sin error) → usar el camino de SQLAlchemy.
- **[oracle]**: `ALL_SOURCE` (concatenado por `line`) + `CREATE OR REPLACE ` sustituye a `DBMS_METADATA.GET_DDL`: una
  consulta por schema y DDL sin owner (`DBMS_METADATA` da `"OWNER"."NOMBRE"` y marca como distintas las routines de dos
  schemas). `metadata/oracle/tables.fetch_standalone_routine_sources_for_schema_sql` excluye `PACKAGE BODY`.
- **[arquitectura]**: `comparar` (capa 6) puede importar `metadata` (capa 5) pero no `dump` (capa 7): para ordenar por
  FKs se usa un Kahn propio (`SqlDiffReporter._order_by_foreign_keys`), no `dump/_fk_graph`. Todo SQL de introspección
  nuevo va a `metadata/<motor>/` (REGLA #1), con parámetros `:nombre` si lo consume `sqlalchemy.text`.
- **[mysql]**: `SHOW CREATE` con un `:` en el nombre se rompe en `text()` (lo toma por parámetro): escapar `\:`.
  `SHOW CREATE` sin schema busca en la base de la conexión: calificar siempre (`fetch_show_create_routine_sql`).
- **[sql_reporter]**: SQLite solo admite `ALTER TABLE` RENAME/ADD COLUMN/DROP COLUMN: un aviso `-- ⚠` dentro de
  `ALTER TABLE … ;` se come el `;`; emitirlo como línea propia (`_alter_table_sql`). En MariaDB/MySQL los literales
  duplican también `\` (`_escape_sql_string(value, dialect)`).
- **[herramientas]**: En Bash de esta máquina, heredocs con `\d`/`\n` en literales Python pierden un nivel de barras y un
  heredoc largo con `'''` puede fallar al parsear: escribir el script con Write y ejecutarlo, o editar con Edit.
- **[herramientas]**: No usar `git stash` de ficheros con cambios propios para «probar sin el fix»: se lleva todo el
  trabajo del fichero. Verificar la reproducción con un test escrito antes del fix.
- **[bench]**: `scripts/bench_compare.py setup|run|teardown` (200 tablas por defecto) reproduce las cifras de la
  auditoría; la primera medición tras `setup` en SQL Server/Oracle está fría (×10-30): usar `--repeat` ≥ 2.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| AUDIT_CODE inicial, PLAN/AUDIT_PLAN, AUDIT_CODE de entregas | conversación de la sesión | emitidos |
| IMPLEMENT | 9 commits `0f1c6b3`…`5b9319f` (excepto `85e773a`, del usuario) | completado |
| Benchmark | `scripts/bench_compare.py` | completado |
| TRACEABILITY | `.ai/sessions/2026-10-02g-comparar-audit/TRACEABILITY.md` | este fichero |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno de la sesión. Publicada como **v0.30.0** (MINOR: MySQL gana comparación de routines y hay funciones públicas
  nuevas en `metadata/`; el resto, fixes y perf compatibles): CHANGELOG `[0.30.0] - 2026-10-03`, campos de versión de
  `sync.instructions.md` § 4, `CURRENT_STATE.md`, `SESSIONS_DIGEST.md` e `INDEX.md` (a petición expresa del usuario:
  «Todo»), commit `release:`, tag `v0.30.0` y push de `develop` y del tag.
- Límites conocidos de `comparar`: ver «Known limitations».
