# TRACEABILITY

## Session metadata
- id: 2026-09-29b-feature-mysql-pymysql
- fecha: 2026-09-29
- rama: develop (base `cd2e964`)
- skill: new_feature (E1–E4) + refactor (E0); E5 (hotfixes de defectos previos) planificada
- fase: PLAN + AUDIT_PLAN (v1, v2) + IMPLEMENT + verificación real por entrega

## Prompt issued
```
EL driver utillizado en MariaDB/MySQL es pymysql, quiero utilizar el original de MariaDB para MariaDB y pymysql para
MySQL, analiza el proyecto para incluirlo y dime que partes afecta, no se implementa nada
```
Decisiones del usuario: (A) `mysql` motor propio completo; pool sync de MySQL con `QueuePool` de SQLAlchemy; MariaDB
async sigue con aiomysql; sin aviso de compatibilidad para `db_type="mariadb"` contra MySQL; `migrate/` incluido;
extras opcionales en `pyproject.toml`; unificar la resolución de adapters en el registro (E0, `/refactor`); los
defectos previos encontrados pasan al PLAN como E5.

## Context supplied
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`, `.github/prompts/new_feature.prompt.md`,
  `.github/agents/plan-architect.agent.md`, `.ai/architecture.md`, `.ai/runtime.md`, `.ai/product.md`.
- Banco de 5 servidores (`docker-compose.bench.yml`): MySQL 8.4, MariaDB 11.4, PostgreSQL 17, SQL Server 2022,
  Oracle 23 Free.

## AI output summary
- Análisis: la vía sync de MariaDB **ya** usaba Connector/Python (conexión, pool y `mariadb+mariadbconnector`);
  PyMySQL entraba por aiomysql (async), scripts y tests. `mysql` no existía como `db_type` (`InvalidDatabaseType`).
- **E0** `0c7e841` refactor(managers): `_get_metadata_adapter()` resuelve por `db_type` en el registro global
  (Protocols `EngineMetadataAdapter{Sync,Async}`, `StorageInventoryAdapter{Sync,Async}`); fuera
  `_get_mariadb_adapter` (14 llamadas). La estrategia async de storage de HSQLDB pasa a async. Suite idéntica
  (5298/199) antes y después.
- **E1** `3b75eb9` feat(connection): `connection/mysql/` (PyMySQL, `QueuePool` con `pre_ping` + dialecto,
  aiomysql con `database`→`db` y filtrado por firma), `MySQLConnectionConfig/MySQLPoolConfig` (lista blanca, TLS),
  factorías, URLs con `URL.create`, `MySQLValidator`, catálogo `mysql` en `sql_queries.json`, escape de `%` solo con
  parámetros, extras `mariadb`/`mysql`, `types-PyMySQL`.
- **E2** `0ad0301` feat(metadata): `MysqlSync/AsyncAdapter` delegan las 7 lecturas especializadas en el adapter de
  MariaDB; `query/`, `doc/` (cabeceras, columnas, índices, FK, storage) y `analysis/` tratan `mysql` como `mariadb`.
- **E3** `f04c4fc` feat(migrate): `mysql` origen/destino (20 pares), `MySQLSchemaExtractor`,
  `MariaDBFullTypeSchemaExtractor`, `MySQLDDLEmitter`, transformers de la familia, `validate_mysql_collation`,
  `fetch_columns_with_type_sql` en `metadata/mysql/tables.py`; docs `migrate_mysql.md` (functional + api).
- **E4** `de8904f` test(integration) `test_mysql_engine_e2e.py` + `GRANT PROCESS` a `bench` en el banco (aplicado al
  contenedor vivo y como script de inicio); docs de drivers, CHANGELOG, `.ai/`, diagrama de capas.
- Verificación real: managers sync/async con y sin pool; 19 queries del catálogo y 7 lecturas especializadas en
  MySQL y MariaDB; documentación Word/Excel/HTML con el mismo contenido en ambos; `migrate` ejecutando el DDL en el
  destino para MySQL → MariaDB/PostgreSQL/SQL Server/Oracle y MariaDB/PostgreSQL/SQL Server/Oracle → MySQL.
- Calidad al cierre de E4: `ruff` y `mypy` limpios; `pytest` 5404 passed / 199 skipped (sin URLs); `tests/integration` con las URLs del banco: **344 passed, 0 skipped** en 5 servidores; `zensical build --strict` sin incidencias.
- Controles: con MariaDB como origen/destino y el código anterior (`3b75eb9`, worktree temporal) se reproducen los
  mismos fallos de `migrate` → son previos (E5).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN v1/v2 | conversación (veredicto GO_CONDICIONAL) | emitido |
| E0–E4 | commits `0c7e841`, `3b75eb9`, `0ad0301`, `f04c4fc`, `de8904f` y cierre E4 | completado |
| Test de integración MySQL | `tests/integration/test_mysql_engine_e2e.py` | completado |
| Docs | `docs/functional/migrate_mysql.md`, `docs/api/migrate_mysql.md`, guías de drivers | completado |

## Directrices para Futuras IAs
- **[managers/metadata]**: el adapter de lecturas especializadas se obtiene SOLO con `_get_metadata_adapter()` (registro
  global por `db_type`); un motor nuevo con lecturas especializadas se registra en su `metadata/<motor>/__init__.py` y
  los managers importan el paquete para que el registro se ejecute. No reintroducir `_get_<motor>_adapter`.
- **[mysql/metadata]**: MySQL 8 y MariaDB comparten el `INFORMATION_SCHEMA` de las lecturas especializadas y del
  catálogo (validado en 8.4): `MysqlSyncAdapter` delega en `MariaDBSyncAdapter`. Diferencias observadas: MySQL
  devuelve `COLUMN_DEFAULT` sin comillas (`x`; MariaDB `'x'`), `int` sin ancho y collation `utf8mb4_0900_ai_ci`.
- **[mysql/executors]**: PyMySQL/aiomysql solo formatean con `%` si reciben parámetros; escapar `%` sin parámetros
  rompe los `LIKE 'a%'`. Para `mysql` se escapa con `_PYFORMAT_LITERAL_PERCENT` solo cuando hay parámetros.
- **[mysql/connection]**: `aiomysql.connect` no acepta `database`, `read_timeout` ni `write_timeout`: usar
  `build_aiomysql_connect_kwargs` (renombra a `db` y filtra por la firma real). `QueuePool(pre_ping=True)` exige
  `dialect=MySQLDialect_pymysql()`.
- **[mysql/permisos]**: `information_schema.FILES` (inventario de almacenamiento) exige el privilegio global
  `PROCESS` en MySQL.
- **[migrate]**: con destino MySQL se reutilizan los transformers `X → MariaDB`; los avisos no deben escribirse como
  `ddl_comment` en línea hasta corregir H3 (rompen el `CREATE TABLE`).
- **[postgresql/connection]**: `PostgreSQLConnectionConfig.to_driver_kwargs()` mantiene `database` a propósito (lo consumen el `conninfo` del pool y asyncpg); la traducción a libpq (`dbname`, booleanos a entero) se hace solo en la conexión sync directa. `psycopg.conninfo.make_conninfo` no valida tipos: `keepalives="True"` solo falla en el servidor.
- **[postgresql/libpq]**: `tcp_keepalives_*` son nombres del parámetro del servidor; libpq usa `keepalives_*`. Toda traducción a libpq pasa por `connection/postgresql/_libpq.to_libpq_params` (pool y conexión directa). `psycopg.conninfo.conninfo_to_dict` valida nombres de parámetros de URI sin conectar; no valida tipos.
- **[migrate/defaults]**: el DEFAULT del origen se normaliza UNA vez en `_build_plan` (forma canónica: `'x'`, números, `NULL`, `CURRENT_TIMESTAMP[(n)]`, `CURRENT_DATE`, booleanos 1/0); los emitters traducen desde esa forma. Un motor origen nuevo necesita su rama en `normalize_default`. Lo no reconocido pasa intacto (`NEXTVAL` lo usan los transformers de Oracle).
- **[metadata/defaults]**: `COLUMN_DEFAULT` llega entrecomillado en MariaDB (`'x'`) y sin comillas en MySQL (`x`); `format_mariadb_default` acepta ambos. En MySQL, `EXTRA` puede traer `DEFAULT_GENERATED`, que no se copia al DDL.
- **[bench]**: la integración ya cubre MariaDB con los dos drivers (URL base `mariadb+pymysql` y variantes
  `mariadbconnector`); no cambiar la URL base o se pierde la cobertura de PyMySQL sobre MariaDB.

## Veredicto final
Veredicto: CLOSED (E0–E5 completadas)
Pendientes al cierre:
- E5 completada (hotfixes de defectos previos, uno por commit):
  - ~~H1 (P1): conexión async directa de MariaDB (`use_pool=False`) → `TypeError` en `aiomysql.connect`.~~ Corregido (`hotfix(connection)`): `_map_connect_kwargs` renombra `database`→`db` y descarta los timeouts; test de regresión contra la firma real de `aiomysql.connect` (el aiomysql falso aceptaba `**kwargs` y ocultaba el fallo); verificado contra MariaDB 11.4 con y sin pool.
  - ~~H2 (P1): conexión sync directa de PostgreSQL → `database=` en lugar de `dbname=` en `psycopg.connect`.~~ Corregido (`hotfix(connection)`) en `connection_postgresql.py` (no en la config: el pool y asyncpg usan `database`): `database`→`dbname` y booleanos → `0`/`1` (segundo fallo, oculto tras el primero). Verificado contra PostgreSQL 17 con y sin pool.
  - ~~H6~~ Corregido (`hotfix(connection)`): el `conninfo` del pool lleva todas las opciones libpq; nuevo `connection/postgresql/_libpq.py` (`to_libpq_params`: `database`→`dbname`, `tcp_keepalives_*`→`keepalives_*`, booleanos → 0/1) usado por pool y conexión directa. Verificado contra PostgreSQL 17 (`ssl=off`): `sslmode="require"` falla ahora también con pool; `application_name`, `keepalives`, `schema` aplicados en ambas vías. Integración 344 passed. Detalle original:
    H6 (P1, seguridad): el pool sync de PostgreSQL (`pool_connection_postgresql.py`, `use_pool=True` por defecto) construye un `conninfo` con solo user/password/host/port/database y `options`: ignora `sslmode`, `connect_timeout`, `keepalives`, `tcp_keepalives_*`, `application_name`, `fallback_application_name`, `target_session_attrs` y `dbname`. `sslmode="require"`/`"verify-full"` no se aplica (libpq usa `prefer`, que admite conexión sin TLS) y no avisa. Verificado: `application_name` llega vacío con pool y correcto sin pool. Fix previsto: añadir esas opciones al `conninfo` (URL-encoded, booleanos → 0/1), con test de regresión y verificación real (incluido `sslmode`). Las vías async ya traducen `sslmode` y `application_name`.
  - ~~H3 (P1): `migrate/` emite el `-- AVISO` antes de la coma que separa columnas (todos los emitters).~~ Corregido (`hotfix(migrate)`): `emitters/_trailing_comment.py` (marcador NUL + `join_definitions`); también afectaba al comentario de columna en PostgreSQL/SQL Server. Verificado: MySQL → PostgreSQL/SQL Server crean todas las tablas (antes 0/6); lo que sigue fallando es H4 (defaults) y vistas pass-through.
  - ~~H4~~ Corregido (`hotfix(migrate)`): normalizador por motor origen en `MigrationPlanner._build_plan` (`_compat/default_normalizer.py`) + Oracle `DEFAULT` antes de `NOT NULL` y sin re-entrecomillar, MariaDB/MySQL `CURRENT_TIMESTAMP(n)`, PostgreSQL `TRUE`/`FALSE` en `BOOLEAN`. Matriz real de 20 pares: todas las tablas creadas (solo fallan las vistas pass-through, limitación documentada). Detalle original:
    H4 (P2): `migrate/` traduce mal defaults (casts PG, paréntesis SQL Server, `SYSDATE`, orden `DEFAULT`/`NOT NULL`
    y doble comillado en Oracle).
  - ~~H5 (P2): DDL reconstruido de MariaDB con doble comillado de defaults de texto (`DEFAULT '''x'''`).~~ Corregido (`hotfix(metadata)` 338550e): `format_mariadb_default` respeta los literales ya entrecomillados; `build_mariadb_table_ddl` quita `DEFAULT_GENERATED` de `EXTRA` (MySQL, introducido por la delegación de E2). Verificado: en MariaDB 11.4 y MySQL 8.4 la tabla re-creada con el DDL reconstruido tiene los mismos defaults.
- Push de los commits de la sesión (pendiente de decisión del usuario).
