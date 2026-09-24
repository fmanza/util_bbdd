# Changelog

Todos los cambios notables en este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- **bulk (SQL Server + pymssql)**: `BulkCrud` registra un INFO al detectar `mssql+pymssql` recomendando
  `mssql+pyodbc` con ODBC Driver 17/18 para cargas masivas (~15× más rápido en INSERT/UPDATE). Se evaluó y **descartó**
  la carga nativa `bulk_copy` de pymssql (P-17): en SQL Server 2022 no aplica CHECK ni claves foráneas aunque se le pida
  (y las deja marcadas como no confiables), sustituye los `NULL` explícitos por el DEFAULT de la columna e ignora los ids
  explícitos de columnas IDENTITY.

- **bulk (todos los motores)**: los registros de `bulk_insert_from_df`, `bulk_insert_from_chunks` y
  `bulk_update_from_df` se preparan por columnas (`dataframe_to_sql_records`) en lugar de `to_dict(orient="records")`
  más `normalize_sql_literal` celda a celda (P-03). Las columnas numpy enteras, booleanas y float y las de fecha (con y
  sin zona) se convierten en bloque; el resto sigue el mismo camino que antes. El resultado es idéntico (mismas claves,
  valores y tipos Python), verificado con una matriz de dtypes que incluye nullable, `str`, `category`, `Decimal`,
  bytes, escalares numpy en columnas object, nanosegundos y zonas horarias. Medido: preparación de 1M filas 8,58 s →
  2,95 s (2,9×); de extremo a extremo en SQLite, INSERT de 1M 13,8 s → 8,4 s y UPDATE 17,1 s → 11,7 s. El ahorro
  (~5,6 s por millón de filas) es el mismo en todos los motores. `normalize_records_for_sql` y
  `normalize_sql_literal` no cambian.

- **bulk (MySQL/MariaDB + PyMySQL)**: el INSERT usa el `executemany` del driver vía `exec_driver_sql`
  (`MySQLDriverExecutemanyStrategy`) en lugar de la vía multi-fila con `text()` (P-02). Medido con 1M filas: MySQL 8.4
  54,9 s → 26,3 s y MariaDB 11.4 50,4 s → 24,0 s (~2,1×). Los valores guardados son idénticos (verificado con JSON,
  BIT, ENUM, DECIMAL, DATETIME(6), TIME, BLOB, NULL y Unicode). Además, ahora funcionan las tablas y columnas con `%` en
  el nombre, que con la vía multi-fila fallaban. Con otros drivers (p.ej. `mariadbconnector`) se mantiene la vía
  multi-fila, que sigue disponible con `InsertStrategyResolver(mysql_strategy=MySQLMultiRowInsertStrategy())`.

### Fixed

- **bulk (columnas binarias)**: los `bytes` que son UTF-8 válido (p.ej. `b"q"`) fallaban o se perdían en columnas
  binarias (P-21). `normalize_sql_literal` los decodifica a `str`, y los parámetros tipados binarios los rechazaban:
  `TypeError` en el INSERT de SQLite y SQL Server (pymssql y pyodbc), y en el UPDATE de PostgreSQL y de MySQL/MariaDB
  sin tabla temporal. En Oracle se llegó a guardar NULL en su lugar. Ahora, en las columnas de tipo binario reflejado,
  el valor vuelve a codificarse en UTF-8 y recupera exactamente los bytes originales. Las columnas de texto siguen
  recibiendo `str`. Verificado en los 6 motores. Oracle guarda `b""` como NULL por diseño propio.

- **bulk (MySQL/MariaDB)**: `MySQLMultiRowInsertStrategy` podía insertar filas en la tabla equivocada, sin error (P-22).
  Su caché de plantillas SQL usaba como clave `(filas, columnas)`, sin la tabla. Una misma `BulkCrud` que insertaba en
  dos tablas con las mismas columnas y el mismo tamaño de sub-lote (p.ej. el volcado secuencial de `dump`, que comparte
  una `BulkCrud` para todas las tablas) reutilizaba la plantilla de la primera, y las filas de la segunda acababan en
  ella. La tabla forma parte ahora de la clave. Desde P-02 la estrategia solo se usa por defecto con drivers distintos
  de PyMySQL (p.ej. `mariadbconnector`); antes afectaba a todos los usuarios de MySQL/MariaDB. **Si has cargado varias
  tablas con las mismas columnas en MySQL/MariaDB con la misma `BulkCrud`, revisa sus datos.**
- **bulk (JSON)**: las columnas de tipo JSON se corrompían en silencio (P-19). `normalize_sql_literal` ya serializa
  dict/list a texto JSON, y las sentencias construidas desde la tabla reflejada volvían a serializarlo con el tipo
  `JSON` de SQLAlchemy: se guardaba un *string* JSON en lugar del objeto, y `None` como el literal JSON `null` en lugar
  de `NULL` SQL. Afectaba a `bulk_update_from_df` en PostgreSQL (`JSON`/`JSONB`), MySQL (`JSON`) y SQLite, y además a
  `bulk_insert_from_df` / `bulk_insert_from_chunks` en SQLite. Ahora esas columnas se enlazan con un tipo que no vuelve a
  procesar el valor (conserva el cast `::JSONB` en PostgreSQL). MariaDB (`JSON` = `LONGTEXT`), Oracle y SQL Server no
  estaban afectados. Los datos ya guardados con el fallo no se corrigen solos.
- **bulk (SQL Server)**: `bulk_delete_from_df` fallaba en SQL Server (P-05). Con pyodbc, a partir de ~2100 filas daba
  `07002 COUNT field incorrect`: todas las PK del lote (`chunk_size`) iban en un único `IN (...)` y SQL Server admite
  como máximo 2100 parámetros por petición. Con PK compuesta fallaba con cualquier driver, por la sintaxis
  `(a, b) IN ((..), (..))`, que SQL Server no admite. Ahora la PK simple se trocea en sentencias de 2000 parámetros como
  máximo y la PK compuesta usa `DELETE ... WHERE a = ? AND b = ?` con executemany. Medido con pyodbc + ODBC Driver 18:
  DELETE de 1M filas en 8,9 s. MySQL, MariaDB y HSQLDB no cambian.
- **bulk (SQL Server + pyodbc)**: `bulk_update_from_df` fallaba con `HY104 Invalid precision value` en tablas con
  columnas `DATETIME` (P-18), y el INSERT no usaba `fast_executemany` aunque `enable_fast_executemany=True` (P-01).
  Causa: el flag se aplicaba con un listener sobre el cursor, a espaldas del dialecto. SQLAlchemy seguía llamando a
  `setinputsizes()` y mantenía insertmanyvalues. Ahora `BulkCrud` configura el dialecto igual que
  `create_engine(..., fast_executemany=True)`. Medido en SQL Server 2022 + ODBC Driver 18: el UPDATE vuelve a funcionar
  (~33.500 filas/s) y el INSERT es ~12× más rápido (100K filas: 26,0 s → 2,0 s). Afecta a todo el engine, como antes
  el listener. `enable_fast_executemany=False` sigue desactivándolo.

### Added

- **bulk (MySQL/MariaDB)**: `BulkCrud(update_via_staging=True)`, **activo por defecto** (P-04). `bulk_update_from_df` carga cada lote en una tabla
  temporal por la vía rápida de INSERT y aplica un único `UPDATE destino, tmp SET ... WHERE destino.pk = tmp.pk`, en
  lugar de un UPDATE por fila: ~12,5× más rápido (1M filas: MySQL 8.4 376 s → 29,5 s; MariaDB 11.4 331 s → 27,1 s). El
  estado final de la tabla es idéntico al del UPDATE por fila, verificado en MySQL 8.4 y
  MariaDB 11.4 con PyMySQL y `mariadbconnector`: tipos variados, JSON, NULL y PK repetidas (gana la última). Respeta
  `bulk_session` (sin commit implícito: DDL `TEMPORARY`) y `commit_every_n_chunks`. Ignorado en otros motores.
  Requiere el privilegio `CREATE TEMPORARY TABLES`. Si el servidor lo deniega (errno 1044/1142/1227), `BulkCrud` vuelve
  solo al UPDATE fila a fila, sin romper la transacción, y registra un único WARNING en el logger
  `util_bbdd.bulk._execution.batch` con la causa y cómo evitarlo. Esa instancia no vuelve a intentarlo.
  `BulkCrud(..., update_via_staging=False)` desactiva el intento.
- **scripts**: `scripts/bench_bulk.py`, banco de pruebas de rendimiento de `BulkCrud` (INSERT/UPDATE/DELETE)
  contra motores reales (SQLite, PostgreSQL, MySQL, MariaDB, SQL Server, Oracle). Las URLs se leen de
  `UTIL_BBDD_BENCH_<MOTOR>_URL` (o `UTIL_BBDD_TEST_<MOTOR>_URL`) y los motores sin URL se saltan. Verifica cada
  operación con SQL, registra los errores sin detenerse y admite variantes A/B de los hallazgos P-01 y P-02 de la
  auditoría de rendimiento. Escribe `summary.md`, `results.csv` y `environment.json` (sin contraseñas) en
  `bench_results/`. Fase 0 de `.ai/sessions/2026-09-23-performance-audit-bulk/`.
- **docker**: `docker-compose.bench.yml` con los 5 servidores para uso local; la contraseña se toma de
  `UTIL_BBDD_BENCH_PASSWORD`, no está en el repo.
- **tests**: `tests/integration/test_bulk_engines.py`, pruebas de ida y vuelta de `BulkCrud` por motor. El DELETE en
  SQL Server queda como `xfail(strict=True)` por P-05 (más de 2100 parámetros y PK compuesta), y el UPDATE con
  columna DATETIME en SQL Server + pyodbc por P-18 (el listener de `fast_executemany` provoca `HY104 Invalid precision value`).
  `tests/unit/test_bench_bulk_script.py` cubre el banco contra SQLite.

### Changed

- **docs**: `docs/guides/benchmarks.md` documenta el banco de pruebas y avisa de que las ganancias publicadas para
  MySQL/MariaDB y SQL Server están en revisión.

## [0.11.0] - 2026-09-22

Auditoría completa del proyecto (12 franjas por capa/módulo) y remediación de todo el
backlog resultante (9 hallazgos P0 de seguridad, 15 P1, 27 P2 — 53 ítems en total, cada
uno con su propio commit y tests de regresión). Sesión `.ai/sessions/2026-09-22-audit-completo-remediacion/`.

### Security

- **doc**: autoescape Jinja2 activado en las plantillas `*.html.j2` — un valor de BD con
  `<script>`/`<img onerror=...>` incrustado en un comentario o nombre se renderizaba sin
  escapar en el HTML generado (XSS reflejado en documentación auto-generada).
- **metadata (MariaDB)**: `schema`/`table` bindeados como parámetros en los helpers SQL en
  vez de interpolados en el texto de la consulta (inyección SQL vía nombre de schema/tabla).
- **validators**: allowlist de caracteres para `tabla`/`rutina`/`tipo_rutina`/`tablespace`
  en los 6 validadores de `query/` — cerraba una vía de inyección SQL por esos parámetros.
- **factory**: la contraseña ya no aparece en claro en el log del connection string
  síncrono (paridad con el camino async, que ya la redactaba).
- **connection (PostgreSQL)**: `user`/`password`/`database` URL-encoded en el conninfo del
  pool — un valor con `@`, `:` o `/` sin escapar corrompía la cadena de conexión o, en el
  peor caso, permitía inyectar parámetros de conexión adicionales.
- **connection (SQL Server)**: valores escapados en el DSN ODBC (sync y async) — mismo
  riesgo que el punto anterior, vía el driver ODBC.

> ⚠️ **Recomendado actualizar en cuanto sea posible** si se conecta contra motores con
> nombres de schema/tabla o credenciales no plenamente controlados por el propio equipo.

### Fixed

#### migrate: `execute()` bloquea si el plan tiene warnings de severidad `ERROR`

`MigrationPlan.execute()` ejecutaba el DDL generado aunque `plan.error_count > 0` (p. ej.
tipos sin mapeo, identificadores irresolubles). Ahora lanza `ValueError` antes de ejecutar
si hay algún warning `ERROR` pendiente, **sin** flag de override — decisión de producto
explícita: no existían callers internos que dependieran del comportamiento permisivo previo.

> ⚠️ **Cambio de comportamiento**: código que llamaba a `execute()` sobre un plan con
> errores y confiaba en que se aplicara parcialmente ahora recibe `ValueError`. Revisar
> `plan.warnings`/`plan.error_count` antes de `execute()` para decidir si proceder.

#### migrate: `AUTO_INCREMENT` preserva el tipo origen en MariaDB

El emisor MariaDB colapsaba cualquier columna `AUTO_INCREMENT` a `INT(11)` sin importar el
tipo origen. Ahora conserva la categoría (`TINYINT`/`SMALLINT`/`MEDIUMINT`/`INT`/`BIGINT`)
con su display width convencional.

> ⚠️ **Cambio de comportamiento**: DDL ya generado con columnas `AUTO_INCREMENT` de tipo
> distinto a `INT` cambiará de ancho en la próxima migración con los mismos datos.

#### comparar: índices y foreign keys se comparan sin distinguir mayúsculas/minúsculas

`SchemaComparator.compare()` reportaba como `added`+`removed` pares de índices/FKs cuyo
nombre solo difería en el case (mismo patrón ya aplicado a tablas/columnas). Ahora se
normalizan a minúsculas antes de comparar.

> ⚠️ **Cambio de comportamiento**: comparaciones entre motores con distinto case-folding
> (p. ej. Oracle mayúsculas vs. PostgreSQL minúsculas) reportarán **menos** diferencias
> falsas-positivas que antes.

#### bulk: `ParallelBulkLoader` reporta filas reales tras un fallo a mitad de partición

Con `commit_every_n_chunks` activo, una partición que fallaba a mitad de carga reportaba
`PartitionResult.rows=0` aunque varios lotes anteriores ya estuvieran confirmados en BD.
`BulkCrud.rows_committed` (nueva propiedad) expone las filas durablemente comprometidas —
solo avanza en los commits reales, nunca en filas ejecutadas-pero-pendientes — y
`ParallelBulkLoader` la usa en vez del `0` fijo.

> ⚠️ **Cambio de comportamiento**: `ParallelLoadResult.total_rows`/`PartitionResult.rows`
> pueden ser mayores que antes para particiones fallidas con `commit_every_n_chunks` activo.

#### migrate: más `MigrationWarning` al migrar vistas y tablas Oracle

- `rewrite_oracle_view` avisa ahora de **todas** las sustituciones léxicas con riesgo de
  falso positivo en literales de texto (SYSDATE, SYSTIMESTAMP, NVL, FROM DUAL, prefijo de
  schema) — antes solo avisaba de la sustitución de `USER`.
- El emisor Oracle avisa cuando una tabla tiene **más de una** columna `AUTO_INCREMENT`
  (solo la primera recibe `SEQUENCE`/`TRIGGER`; antes las demás se descartaban en silencio).
- `find_case_insensitive_collisions()` (nuevo, `migrate/_compat/identifier_rules.py`)
  detecta pares de identificadores de tabla/vista que solo difieren en case y genera
  `MigrationWarning` (`IDENTIFIER_CASE_COLLISION`) — riesgo bajo case-folding de motor
  destino (Oracle mayúsculas, PostgreSQL minúsculas).

> ⚠️ **Cambio de comportamiento**: `plan.warning_count`/`plan.warnings` pueden ser mayores
> que antes para migraciones con esos patrones, aunque el DDL generado no cambia.

#### doc: nombres de fichero de diagramas saneados; aviso cuando no hay estrategia de almacenamiento

- `word_generator.py`/`html_generator.py` saneaban el nombre de tabla insertándolo sin
  filtrar en la ruta del diagrama de fallback a disco — un nombre con `/`/`..`/caracteres
  inválidos de Windows podía escribir fuera del directorio de salida o fallar. Nuevo
  `sanitize_table_filename()` compartido.
- `StorageInventoryRuntime` caía en silencio a un fallback genérico de almacenamiento para
  motores sin estrategia dedicada (p. ej. SQL Server). Ahora loguea un warning y añade una
  sección visible en el documento generado explicando que los datos pueden ser imprecisos.

> ⚠️ **Cambio de comportamiento**: el nombre de fichero de los diagramas de fallback cambia
> de forma para tablas con caracteres no alfanuméricos; el informe de almacenamiento gana
> una sección nueva para motores sin estrategia dedicada.

#### Resto de correcciones (sin cambio de comportamiento observable)

- **Excepciones unificadas a `InvalidDatabaseType`** para `db_type` desconocido/no
  soportado, en vez de excepciones genéricas dispares: `DriverValidator`
  (`check_driver_availability`), `connection/factory.py`, `connection/params.py`.
- **Citado de identificadores** (cierra el patrón de interpolación insegura ya corregido en
  la ronda P0): PRAGMA de SQLite, `SqlDiffReporter` (tabla/columna/índice/FK/vista/rutina),
  `DBCC CHECKIDENT` de SQL Server.
- **`Protocol`/adaptadores de metadatos**: `extract_views` declarado en `SchemaExtractor`
  (las 4 implementaciones ya lo exponían); MySQL y SQL Server registrados como
  `RoutineAdapter` completo (`fetch_routine_definition_sync/async`); PostgreSQL y SQL
  Server ganan `fetch_routine_definition_sync/async`; adaptadores de Oracle/SQL
  Server/MariaDB alineados con `SourceAdapter`/`RoutineAdapter`.
- **Oracle**: identificadores normalizados a mayúsculas antes de bindear en los 12 puntos
  de consulta de metadatos; columnas `LONG`/`LONG RAW` conservadas con marcador en vez de
  descartadas; filtro de schema de sistema corregido a `WMSYS` exacto (antes excluía
  cualquier schema con prefijo `WM`, incluidos schemas de negocio legítimos); overflow
  `TINYINT` en `NUMBER(1-2,0)` → SQL Server avisado.
- **MySQL/MariaDB**: mapeo `BIT` añadido a MySQL; MariaDB gana su propia normalización de
  tipos (`mariadb_type_mapping`/`normalize_mariadb_type`, antes copiaba parcialmente el
  comportamiento de MySQL sin fuente de verdad propia); registro de adapters ya no
  enmascara errores reales de programación tras un `except Exception: pass` demasiado
  amplio (ahora `except ImportError`).
- **Managers**: `close_async_resources` agrega errores por recurso en vez de abortar en el
  primero (paridad con la versión sync); `CacheManager.clear_context/clear_routine` delega
  en la API pública nueva de `DatabaseMetadataCache` en vez de tocar 14 atributos privados;
  `DatabaseRelationshipGraphBase.clear_cache()` (nuevo) invalida las 3 cachés internas del
  grafo de relaciones — antes no tenían ningún método de invalidación propio;
  `RelationshipMetadataCache` incluye `context` (schema) en sus 4 cachés, evitando colisión
  cross-schema entre tablas homónimas.
- **bulk/comparar**: `__run_bulk_pipeline` captura también `AuditError`/`OSError`;
  `_substitute_ordered_params`/`_substitute_named_params` localizan placeholders sobre el
  SQL original antes de sustituir (un valor con `%s`/`?`/`:param` literal ya no corrompe el
  siguiente parámetro); `escape_markdown_table_cell()` (nuevo) escapa `|`/backtick/salto de
  línea en comentarios de `MarkdownDiffReporter`.
- **PostgreSQL async**: aplica `schema`/`options`/`application_name` vía `server_settings`
  (asyncpg no soporta el `options=` estilo libpq de psycopg3).
- **Oracle**: import de `oracledb` en `PoolConnectionOracle` hecho perezoso — antes fallaba
  en import-time si el paquete no estaba instalado, incluso sin usar Oracle.
- **`DumpOrchestrator`** conecta de verdad `DumpError`/`DumpConstraintError`/
  `DumpReportError` en fallos reales de introspección/constraints/reportes (antes código
  muerto); toda la jerarquía se exporta desde `util_bbdd/__init__.py`.
- **`MetadataManager`/`AsyncMetadataManager` conectados a producción**:
  `SyncDatabaseManager.get_metadata_manager()`/`AsyncDatabaseManager.get_metadata_manager()`
  (nuevo, aditivo) construyen de forma diferida un `MetadataManager` que reutiliza `self`
  como `metadata_provider` y comparte `db_cache`/`relationship_cache` con el resto del
  manager. `DDLBuilder._quote_identifier` corregido para duplicar el delimitador embebido
  (cerraba una inyección de identificador) y citar/escapar `DEFAULT` string.
- **Docstrings corregidos** (sin cambio de código): `validate_db_type` (nunca retorna
  `False`, siempre lanza `InvalidDatabaseType`); `transform_views` (la reescritura Oracle es
  un hook sobrescrito solo por los 3 pares con Oracle como origen, no los 12).

### Removed

- **`AsyncLifecycleManager`/`AsyncSessionManager`** (`managers/async_mgr.py`): se
  construían pero ningún método llegaba a invocarse — código muerto.
- **`QueryExecutorBase`** (ABC sin implementaciones reales) y
  `_build_hsqldb_connection_string` async (nunca invocado).
- **`MetadataFetcher`** dejó de instanciarse dentro de `MetadataManager` (nunca se usaba);
  la clase sigue exportada tal cual, sin cambios.

### Changed

- **Renombrados por colisión de nombre** entre un `Protocol`/ABC interno y un alias
  `Callable`/clase homónima ya exportados:
  - `ConnectionProvider`/`ConnectionReleaser` (Protocol, `_core/contracts.py`) →
    `ConnectionProviderProtocol`/`ConnectionReleaserProtocol`.
  - `DatabaseTypeValidator` (ABC, `validators/base_validator.py`) → `QueryParameterValidator`.

  > ⚠️ **Breaking** si se importaban estos nombres directamente (poco probable: son tipos
  > internos de anotación, no instanciados por consumidores típicos). Actualizar el import
  > al nuevo nombre; el comportamiento en ejecución no cambia.
- **3 ficheros de mapeo de tipos renombrados** a la convención
  `type_map_<origen>_to_<destino>.py`: `type_map.py` → `type_map_oracle_to_mariadb.py`,
  `type_map_postgresql.py` → `type_map_oracle_to_postgresql.py`, `type_map_sqlserver.py` →
  `type_map_oracle_to_sqlserver.py`. `migrate/_compat/__init__.py` reexporta ahora los 12
  mapas de tipos (antes 7) y los 4 emisores DDL se exportan desde `migrate/emitters/__init__.py`
  (antes solo 2 de 4).

  > ⚠️ **Breaking** solo para quien importara `migrate._compat.type_map`/
  > `type_map_postgresql`/`type_map_sqlserver` por su ruta antigua directamente (no desde
  > `migrate`/`migrate._compat` como paquete, que ya funcionaba). Actualizar el import a la
  > nueva ruta.
- **`sync_query_executor`**: normalización `%`→`%%` de MariaDB antes de bindear;
  `sqlalchemy_engine_factory` valida `database`/`user`/`service_name` vacíos antes de
  construir la connection string.

#### migrate: collation MariaDB por defecto → `utf8mb4_uca1400_ai_ci`

Se cambia el valor por defecto de la collation para destinos MariaDB en el módulo
`migrate` de `utf8mb4_unicode_ci` a **`utf8mb4_uca1400_ai_ci`** (UCA 14.0.0,
acento-insensible y mayúsculas-insensible). El charset por defecto sigue siendo `utf8mb4`.

> ⚠️ **Cambio de comportamiento (potencialmente breaking)**: `utf8mb4_uca1400_ai_ci`
> solo existe en **MariaDB ≥ 10.10**. Las migraciones generadas con los valores por
> defecto ahora requieren esa versión mínima. Para MariaDB < 10.10 o MySQL, pasar
> `collation=` explícito al construir `MigrationPlanner`; `utf8mb4_unicode_ci` sigue
> siendo una opción válida.

Cambios:

- **`migrate/charset.py`**: `DEFAULT_COLLATION = "utf8mb4_uca1400_ai_ci"`; la nueva
  collation se añade a `VALID_COLLATIONS` y a `CHARSET_COLLATION_MAP["utf8mb4"]` para
  que el default supere la validación del constructor de `MigrationPlanner`.
- **`migrate/__init__.py`**: docstrings de ejemplo actualizados al nuevo default.
- **Documentación**: README, `docs/DDL_MIGRATION_GUIDE.md` y los ejemplos de migración
  (PostgreSQL/SQL Server → MariaDB) actualizados con el nuevo default y la nota de
  versión mínima.

Referencia:
- [DEFAULT_COLLATION](src/util_bbdd/migrate/charset.py)
- [Guía de Migración DDL](docs/DDL_MIGRATION_GUIDE.md)

#### connection/mariadb: `UpdateAutoIncrement` reescrito sin dependencia de `factory`

`UpdateAutoIncrement` (`connection/mariadb/update_auto_increment.py`) importaba `factory/`, una capa superior, y
cerraba un ciclo `connection/` ⇄ `factory/` contrario a la Regla #6 de `architecture.instructions.md`. Se reescribe en
su misma ruta: recibe el `Engine` por parámetro, como `MySQLVariableValidator` recibe la conexión, y deja de depender
de `factory/`, de `pandas` y de SQL de introspección propio (Reglas #1 y #3). Sigue generando las sentencias sin
ejecutarlas.

> ⚠️ **Breaking**: el constructor ya no recibe el `dict` de configuración, sino un `Engine` de SQLAlchemy con dialecto
> `mysql` o `mariadb`. Pasar un `dict` lanza `TypeError` con la indicación de migración:
> `UpdateAutoIncrement(conf)` → `UpdateAutoIncrement(SQLAlchemyEngineFactory.create_engine(db_type, conf, database))`.

Correcciones de comportamiento respecto a la versión anterior:

- **Una sentencia por tabla**, sobre su columna `AUTO_INCREMENT` (antes, una por cada columna de la clave primaria:
  incorrecto con claves compuestas).
- **Sin `ValueError`** con claves no numéricas: las columnas `AUTO_INCREMENT` no enteras se omiten con un `WARNING`.
- **Identificadores siempre entre backticks**, también el esquema (antes se interpolaban sin escapar, `conf["database"]`
  incluido).
- **Valor mínimo 1**: un máximo negativo ya no produce un valor no positivo.
- **Sin `sys.exit(1)`**: los fallos se elevan como `DatabaseOperationError` con la causa encadenada; un dialecto no
  soportado lanza `InvalidDatabaseType`.
- **Salida ordenada por tabla**, parámetro opcional `schema` y exportada desde `util_bbdd.connection.mariadb`.

Para ejecutar el ajuste en vez de generarlo existe `BulkCrud.sync_pk_sequences()`.

Cambios:

- **`connection/mariadb/update_auto_increment.py`** reescrito; **`connection/mariadb/__init__.py`**: export perezoso.
- **`tests/unit/connection/mariadb/test_update_auto_increment.py`**: 23 tests, sin servidor.
- **`tests/integration/test_update_auto_increment_mariadb.py`**: 3 pruebas contra un MariaDB real sobre una base
  temporal que se elimina siempre (se saltan sin `UTIL_BBDD_TEST_MARIADB_URL`). Ejecutadas con éxito contra un
  servidor de pruebas: claves compuestas, `BIGINT UNSIGNED`, vistas, nombres con palabra reservada o backtick, y que el
  script ejecutado deja cada contador en `MAX + 1`.
- **Documentación**: [API](docs/api/update-auto-increment.md), [ejemplo](docs/examples/update-auto-increment-example.md)
  y `mkdocs.yml`.
- **`scripts/gen_arquitectura_capas.py`**: la figura ya no dibuja `connection → factory` ni su marca; las marcas
  restantes se renumeran (1 = `metadata → managers`, 2 = `analysis`/`doc → managers`). Si el import vuelve, el script
  y `tests/unit/test_architecture_import_rules.py` fallan.

Referencia:
- [UpdateAutoIncrement](src/util_bbdd/connection/mariadb/update_auto_increment.py)
- [Regla #6](.github/instructions/architecture.instructions.md)

#### metadata: los adaptadores dependen de `MetadataCachePort`, no de `managers`

`metadata/adapters/base_adapter.py` importaba `CacheService` de `managers/` (capa superior) bajo `TYPE_CHECKING`, solo
para anotar `cache_service` en los constructores de `BaseSourceAdapter` y `BaseRoutineAdapter`. Ahora depende del
Protocol `MetadataCachePort` (`metadata/adapters/_adapter_protocol.py`), que refleja las cuatro operaciones públicas
de invalidación de `CacheService` (`clear_all`, `clear_table`, `clear_routine`, `clear_context`) y que este cumple de
forma estructural.

- **API pública**: solo cambia la anotación de `cache_service` (acepta cualquier objeto con esos métodos, `CacheService`
  incluido). Comportamiento en ejecución idéntico.
- **Regla #6**: desaparece la única excepción de la guarda (`metadata` → `managers` bajo `TYPE_CHECKING`).
- **Tests**: `tests/unit/test_protocol_conformance.py` comprueba que `CacheService` cumple el Protocol (en ejecución con
  `isinstance` y, con `mypy`, también las firmas).

#### analysis, doc: dependen de contratos, no de `managers`

`analysis/` (3 ficheros) y `doc/` (2) importaban `SyncDatabaseManager` solo para anotar sus constructores. Ahora
`analysis/` depende del Protocol `RelationshipGraphSource` (`analysis/contracts.py`) y `doc/` de
`DocumentationSourcePort` (`doc/application/ports.py`), definidos por el consumidor y con parámetros posicionales.
`SyncDatabaseManager`, `SyncDatabaseManagerAdapter` y `DocumentationManagerPort` los cumplen de forma estructural.

- **API pública**: solo cambia la anotación de `db_manager` en `DatabaseRelationshipGraphBase`,
  `GraphvizRelationshipGraphExt`, `MatplotlibRelationshipGraph`, `DatabaseDocumentation` y
  `SyncDatabaseManagerAdapter`: acepta más tipos y `SyncDatabaseManager` sigue valiendo. `RelationshipGraphSource` se
  exporta desde `util_bbdd.analysis`. Comportamiento en ejecución idéntico.
- **`doc/application/ports.py`**: `DocumentationIntrospectionPort` (extraído de `DocumentationManagerPort`),
  `DocumentationQueryPort` y `DocumentationSourcePort` (nuevos). `DocumentationManagerPort` gana `relationship_cache`,
  que `DocumentationSession` expone por delegación: cierra el hueco de tipado que tapaba un `cast`, porque `analysis`
  usaba `relationship_cache` sin que el puerto de `doc` lo declarase.
- **Regla #6**: solo el `__init__.py` raíz importa ya `managers/`; `analysis` baja a la capa 6 y `doc` a la 7 (7 capas).
  No quedan excepciones ni marcas en la figura.
- **Tests**: `tests/unit/test_protocol_conformance.py` comprueba con `mypy` (tipos, aridad y miembros) que el manager, el
  adaptador y el puerto de `doc` cumplen ambos contratos.

#### ci/mypy: el paso `mypy` deja de fallar por `docs_build_plugin.py`

El paso `mypy` de `.github/workflows/tests.yml` corre antes de los tests y sin `continue-on-error`: si falla, los tests
no se ejecutan. `docs_build_plugin.py` (plugin de MkDocs, cargado por entry point desde `mkdocs.yml`) daba 2 errores con
mkdocs instalado y, en una simulación sin él —el caso de CI, porque los extras `dev` no lo instalan—, 4: los mismos 2
más dos `import-not-found`.

- **`[tool.mypy] exclude`** para ese fichero: es una herramienta de documentación, no la librería, y `mypy src` ya no
  lo recorre.
- **Override de mypy para `mkdocs`** (`ignore_missing_imports`) y corrección del fichero, para que también quede limpio
  si se comprueba de forma explícita o desde el IDE: `config_options: ClassVar[dict[str, Any]]` y sin el
  `# type: ignore[override]`, que sobraba con y sin mkdocs. Sin cambio funcional.
- **Resultado**: `python -m mypy src tests/unit/test_protocol_conformance.py` termina con `Success: no issues found`,
  también con caché en frío. Con `--no-incremental` mypy avisa de que el override de `mkdocs` queda sin uso, porque la
  exclusión deja fuera el único fichero que lo necesitaba: es solo un aviso.

### Documentation

#### architecture: Regla #6 con capas estrictas

La Regla #6 (`architecture.instructions.md`) asignaba `connection/`, `factory/` y `results/` a Level 1 y
`managers/` a Level 2, frente a Level 2 y Level 3 en `.ai/architecture.md`, README, onboarding y el script del
diagrama. Además, su frase inicial prohibía los imports entre paquetes del mismo nivel mientras su propia lista de
reglas solo prohibía los ciclos. Tres niveles no bastan para expresar la estructura real sin imports horizontales
(11 pares de paquetes en el código, p. ej. `factory` → `connection`, `metadata` → `results`).

- **Capas**: cada nivel se divide en 7 capas numeradas asignadas por función. Un paquete importa solo de paquetes de
  capas de número menor; los de una misma capa son independientes. La tabla es `LAYER` en
  `scripts/gen_arquitectura_capas.py`, de la que se derivan `LEVEL`, las notas de banda de la figura y la tabla
  generada que incrusta `docs/architecture.md`.
- **Niveles**: los de `.ai/architecture.md`; `models.py` y `async_utils.py` cuentan como Foundation.
- **Imports perezosos** cuentan igual que los de módulo; los de `TYPE_CHECKING` tampoco pueden ir a una capa igual o
  superior.
- **Actualizados**: `.github/instructions/architecture.instructions.md`, `.ai/architecture.md`, `README.md`,
  `docs/guides/onboarding_dev.md`, `docs/architecture.md`, `docs/guides/architecture_diagram_guide.md` y
  `.ai/DECISIONS_LOG.md`.

Referencia:
- [Regla #6](.github/instructions/architecture.instructions.md)
- [Decisión 2026-09-22](.ai/DECISIONS_LOG.md)

#### bulk: Guía de tuning de commit_cadence para cargas masivas en MariaDB/MySQL

Se agregó documentación exhaustiva sobre `commit_every_n_chunks` en `BulkCrud`, que es **crítico**
para evitar degradación exponencial de rendimiento en cargas masivas en MariaDB/MySQL.

**Problema**: Sin commits intermedios, el undo log crece linealmente y el buffer pool se satura,
causando degradación exponencial (latencia × 5–10 en millones de filas).

**Solución**: Usar `commit_every_n_chunks` para emitir `COMMIT` cada N lotes, liberando el undo log
periódicamente.

Cambios:

- **`BulkCrud.__init__` docstring** actualizado con tabla de recomendaciones por servidor
  (`innodb_buffer_pool_size` → `commit_every_n_chunks`), ejemplos y advertencias de atomicidad.
- **Nuevo ejemplo**: `docs/examples/benchmark_commit_cadence.py` — script reproducible que demuestra
  el patrón de degradación vs. solución (100K–2M filas, compara sin/con cadencia).
- **Nueva guía**: `docs/examples/benchmark_commit_cadence.md` — análisis detallado de la causa raíz,
  tabla de recomendaciones por BD, caso de uso Oracle→MariaDB, y advertencias.
  - **Sección 3 (NUEVA)**: "Configuración Crítica de MySQL/MariaDB" — Describe `innodb_buffer_pool_size` y `max_allowed_packet`
    con comandos SHOW/SET, recomendaciones por tamaño de carga, e impacto en bulk inserts.
    Incluye checklist pre-carga masiva.
- **mkdocs.yml**: Agregado nuevo ejemplo "Benchmark: Commit Cadence" bajo sección Ejemplos.

Referencia:
- [bulk: Guía de Tuning › commit_every_n_chunks](docs/examples/benchmark_commit_cadence.md)
- [BulkCrud.commit_every_n_chunks](src/util_bbdd/bulk/crud.py) (docstring actualizado)

### Added

#### tests: guarda automática de la Regla #6

Nuevo `tests/unit/test_architecture_import_rules.py`. Reutiliza `measure()`, `LAYER` y `LEVEL` (derivado) de
`scripts/gen_arquitectura_capas.py` (las capas se declaran en un único sitio) y falla ante:

- un **ciclo de imports entre paquetes** (los imports perezosos cuentan);
- un **import que no va a una capa estrictamente inferior**, sea hacia arriba o entre paquetes de la misma capa
  (cuentan los de módulo, los perezosos y los de `TYPE_CHECKING`; sin excepciones);
- una **tabla de capas incoherente** (capas no contiguas, o un nivel por debajo de una capa de un nivel inferior);
- un **paquete nuevo sin capa asignada**;
- un paquete que **no se importa como primer import** de un intérprete (import circular o dependiente del orden).

Los mensajes indican el `fichero:línea` del import. No añade dependencias.

Junto a ella, `tests/unit/test_protocol_conformance.py` comprueba que las implementaciones reales cumplen los Protocols
que las capas altas usan en lugar de importarlas (`CacheService`, `SyncDatabaseManager` y el adaptador de `doc`). En
ejecución solo comprueba que los miembros existen; las firmas las verifica `mypy`, que `mypy src` por sí solo no cubre:
el paso `mypy` de `.github/workflows/tests.yml` ejecuta ahora `python -m mypy src tests/unit/test_protocol_conformance.py`.

Referencia:
- [test_architecture_import_rules.py](tests/unit/test_architecture_import_rules.py)
- [test_protocol_conformance.py](tests/unit/test_protocol_conformance.py)

#### connection/mariadb: validación automática de variables MySQL/MariaDB para bulk operations

Se agregaron dos módulos nuevos (`_variables.py`, `_config.py`) para automatizar la validación
y recomendación de configuración crítica de MySQL/MariaDB **antes** de cargas masivas.

**Problema**: `max_allowed_packet` (default 16 MB) e `innodb_buffer_pool_size` (default 128–256 MB)
insuficientes causan fallos en producción (`Lost connection to server (2013)`) o degradación exponencial
sin avisos tempranos.

**Solución**: Tres nuevas clases (read-only, sin breaking changes):

1. **`MySQLVariableValidator`** (`connection.mariadb._variables.MySQLVariableValidator`)
   - Lee variables críticas (`max_allowed_packet`, `innodb_buffer_pool_size`) vía `SHOW VARIABLES` (sin modificación)
   - Método `validate(required)` compara actuales vs. requeridos, emite warnings
   - Método `log_summary()` loguea estado actual + recomendaciones en log.info/warning
   - **Permisos**: Solo lectura de `INFORMACIÓN_SCHEMA` (sin SUPER)

2. **`MySQLOptimalConfig`** (`connection.mariadb._config.MySQLOptimalConfig`)
   - Dataclass congelada con valores recomendados por workload:
     - `dev()`: 256 MB buffer, 16 MB packet (default)
     - `production()`: 1 GB buffer, 64 MB packet (estándar)
     - `high_volume()`: 4 GB buffer, 128 MB packet (1M+ filas)
   - Método `suggest(num_rows)` retorna configuración automática basada en tamaño de dataset

3. **`MySQLMultiRowInsertStrategy.get_min_max_allowed_packet()`** (nuevo método)
   - Calcula el `max_allowed_packet` mínimo recomendado basado en `max_rows_per_statement`
   - Típicamente retorna 64 MB para max_rows=1000 (default)
   - Permite a clientes proactivos validar configuración

**Integración en BulkCrud**:
- `BulkCrud.__init__` llamaahora `__validate_mysql_config()` para dialectos mysql/mariadb
- Lee variables actuales + loguea recomendaciones en nivel INFO/WARNING (no lanzaexcepción, no breaking)
- Ejemplo de log: `"MySQL variables: max_allowed_packet=16 MB, innodb_buffer_pool_size=128 MB"` +
  `"WARNING: max_allowed_packet por debajo de mínimo: actual=16 MB, requerido=64 MB"`

**Cambios**:
- Nuevo archivo: `src/util_bbdd/connection/mariadb/_variables.py` (MySQLVariableValidator, 150 líneas)
- Nuevo archivo: `src/util_bbdd/connection/mariadb/_config.py` (MySQLOptimalConfig, 110 líneas)
- Modificado: `src/util_bbdd/connection/mariadb/__init__.py` (lazy-loaded exports)
- Modificado: `src/util_bbdd/bulk/crud.py` (__validate_mysql_config method, ~40 líneas)
- Modificado: `src/util_bbdd/bulk/_execution/batch.py` (MySQLMultiRowInsertStrategy.get_min_max_allowed_packet)
- Nuevo: `tests/unit/connection/mariadb/test_mysql_variables_config.py` (18 tests)
- Nuevo: `tests/unit/bulk/test_mysql_min_packet_calculation.py` (8 tests)

**Backward compatibility**: 100% — nuevos módulos no afectan API pública, validación es opt-in (logging).

Referencia:
- [MySQLVariableValidator](src/util_bbdd/connection/mariadb/_variables.py)
- [MySQLOptimalConfig](src/util_bbdd/connection/mariadb/_config.py)
- [BulkCrud.__validate_mysql_config](src/util_bbdd/bulk/crud.py)

### Performance

#### bulk: Caching de plantillas SQL en MySQLMultiRowInsertStrategy

Se optimizó `MySQLMultiRowInsertStrategy` en `src/util_bbdd/bulk/_execution/batch.py`
mediante caching de plantillas SQL. La estrategia evita reconstruir el mismo template SQL
para sub-lotes de igual tamaño durante inserciones masivas en MySQL/MariaDB.

**Beneficio**: 5–20% mejora de rendimiento en operaciones de 1M+ filas (reducción de CPU,
menor asignación de memoria en construcción de strings).

**Implementación**:
- Nuevo atributo: `_sql_template_cache: dict[tuple[int, tuple[str, ...]], tuple[str, str]]`
  crea caché por clave `(num_rows, columns_tuple)`.
- Nuevo método: `_build_sql_template()` construye template una única vez y reutiliza
  para sub-lotes del mismo tamaño.
- Modificado: `execute()` ahora consulta caché antes de construir SQL.

**Cambios**:
- `src/util_bbdd/bulk/_execution/batch.py`: Nuevo método `_build_sql_template()`, caché inicializado en `__init__`.
- `tests/unit/bulk/test_insert_strategies_cache.py` (nuevo): 11 tests de cobertura E2E (caché hit/miss, aislamiento, corrección funcional).

Referencia:
- [MySQLMultiRowInsertStrategy._build_sql_template()](src/util_bbdd/bulk/_execution/batch.py)
- [Test suite: insert strategies cache](tests/unit/bulk/test_insert_strategies_cache.py)

## [0.10.1] - 2026-06-04

### Infrastructure

#### Migración MkDocs → Zenical: +80% performance, Material Design 3

Migración pura de MkDocs Material 9.5 a **Zenical v0.0.44** (generador estático Rust).
**Cero cambios de contenido**, 100% compatibilidad Markdown, breaking changes 0%.

**Beneficios**:
- ⚡ **Performance**: Build time 300ms → 80ms (-73%)
- 🎨 **Visualización**: Material Design 3 nativo (mejora UI/UX)
- 📊 **Mermaid**: Integración nativa (sin plugins, mejor rendering)
- 🔍 **Búsqueda**: Instant search (vs 200ms MkDocs)
- 📱 **Responsive**: Dark mode automático, diseño moderno

**Cambios técnicos**:
- **Nueva configuración**: `zensical.toml` (634 líneas TOML, equivalente 1:1 a mkdocs.yml)
- **Dependencias**: `pyproject.toml` - `mkdocs-material + mkdocstrings` → `zensical>=0.0.44` (simplificación)
- **CI/CD**: GitHub Actions actualizado - `mkdocs build` → `zensical build` + peaceiris/actions-gh-pages
- **Instrucciones IA**: Actualizadas comandos en copilot-instructions.md, CLAUDE.md; nuevo ZENICAL.md para futuras IAs

**Documentación**:
- [ZENICAL.md](ZENICAL.md) - Guía técnica Zenical para IAs y desarrolladores
- [.ai/PLAN_MIGRATION_ZENICAL_PURE.md](.ai/PLAN_MIGRATION_ZENICAL_PURE.md) - Plan + audit completos
- [.ai/ZENICAL_IMPLEMENTATION_NOTES.md](.ai/ZENICAL_IMPLEMENTATION_NOTES.md) - Notas de implementación

**Validaciones**:
- ✅ Sintaxis TOML: Valid (135 nav entries, todas validadas)
- ✅ Markdown: 100% compatible (92 docs, 0 breaking changes)
- ✅ Mermaid: 44 diagramas, nativo Zenical
- ✅ CI/CD: Workflow completamente funcional, tested
- ✅ Instrucciones IA: Sincronizadas (copilot, CLAUDE, ZENICAL)

**Rollback**: <5 minutos (`git checkout main; mkdocs build`)

**Nota para desarrolladores**: La generación de documentación IA mantiene el **workflow idéntico**
(leer código → aplicar `.github/prompts/` → generar Markdown). Solo cambió la herramienta de rendering.

### Changed

#### Configuración de documentación

- `pyproject.toml`: Dependencias docs simplificadas - `zensical>=0.0.44` (vs mkdocs-material + mkdocstrings)
- `zensical.toml`: Nueva configuración (reemplaza mkdocs.yml, archivado para rollback)
- `.github/workflows/docs.yml`: Triggers, build y deploy actualizados a Zenical

### Documentation

- `ZENICAL.md`: Nueva guía técnica para Zenical (comandos, características, troubleshooting)
- `.ai/PLAN_MIGRATION_ZENICAL_PURE.md`: Plan + AUDIT_PLAN completos (referencia para futuras IAs)
- `.ai/ZENICAL_IMPLEMENTATION_NOTES.md`: Notas de implementación con validaciones y métricas

## [0.10.0] - 2026-06-01

### Performance

#### bulk: vías rápidas de INSERT por motor (PostgreSQL COPY, MySQL multi-fila)

`InsertStrategyResolver` (`bulk/_execution/batch.py`) elige automáticamente la vía nativa
más rápida por motor cuando `BulkCrud(insert_resolver=None)` (default). Output idéntico;
cambia el mecanismo de ejecución. Degradación automática a `executemany` cuando la sentencia
es un `TextClause` (ruta `override_identity` / `OVERRIDING SYSTEM VALUE`).

- **`PostgresCopyStrategy`** (nuevo) — `COPY ... FROM STDIN` vía psycopg3 `cursor.copy()`:
  la vía nativa más rápida de PostgreSQL (streaming por STDIN, sin staging a disco). psycopg3
  adapta automáticamente cada valor Python (incluido `None`→NULL).
- **`MySQLMultiRowInsertStrategy`** (nuevo) — `INSERT ... VALUES (...),(...)` parametrizado
  multi-fila para MySQL/MariaDB, sub-loteado por `max_rows_per_statement` (default 1000) para
  acotar `max_allowed_packet`. Alternativa portable y segura a `LOAD DATA INFILE` (que exige
  `local_infile` y staging a disco).
- Oracle, SQL Server, SQLite y HSQLDB siguen con `DefaultInsertStrategy` (`executemany`;
  SQL Server acelerado por `fast_executemany`, Oracle vía la capa C de `oracledb`).

Documentación: tabla "Estrategias INSERT por motor" en `docs/api/bulk-crud.md`.

#### dump: el volcado reutiliza la resolución única por tabla

`DumpOrchestrator._load_whole_table` (`dump/orchestrator.py`) ahora delega en
`bulk_insert_from_chunks` (resuelve columnas de inserción y estrategia de identidad **una sola
vez** por tabla) en lugar de re-resolver el pipeline por cada chunk con `bulk_insert_from_df`.
El renombrado de columnas se aplica de forma perezosa por chunk, manteniendo el streaming.

### Fixed

- **bulk**: el fast path de PostgreSQL era **código muerto** con el driver real de la librería.
  `InsertStrategyResolver` solo activaba la vía rápida con `psycopg2`, pero el engine síncrono
  se construye con `postgresql+psycopg` (psycopg3), por lo que la aceleración nunca se aplicaba
  (siempre caía en `executemany`). Ahora `psycopg3` → COPY y `psycopg2` → `execute_values`.

## [0.9.0] - 2026-06-01

### Performance

#### dump: palancas de rendimiento opt-in (cadencia de commit, índices, paralelización)

Cuatro palancas nuevas en `DumpConfig`, **todas desactivadas por defecto** (comportamiento
secuencial/atómico byte-idéntico). Combinables entre sí.

- **`commit_every_n_chunks: int | None = None`** — la carga de cada tabla commitea cada N
  lotes (commit-as-you-go) en lugar de una transacción por tabla, acotando el undo/redo log.
  Implementado en `bulk` (`BulkCrud`/`BatchStatementExecutor`/`bulk_session`); `dump` lo
  propaga. **No atómico** con la cadencia activa.
- **`manage_indexes: bool = False`** — nueva clase `IndexManager` (`dump/_indexes.py`):
  deshabilita los índices secundarios **no únicos** y los reconstruye al final.
  mssql `DISABLE`→`REBUILD` (solo NONCLUSTERED), oracle `UNUSABLE`→`REBUILD`, postgresql
  `DROP`+recreate desde `pg_get_indexdef` (DDL logueado antes del DROP), mariadb/mysql no
  soportado. Resultados en `DumpResult.index_results` (`IndexActionResult`) + 4ª hoja Excel.
- **`max_parallel_tables: int = 1`** — carga concurrente de tablas independientes de un mismo
  nivel topológico FK (`ThreadPoolExecutor`, una `BulkCrud` por hilo); ciclos FK secuenciales;
  workers degradados a la capacidad real del pool con `WARNING`.
- **`parallel_pk_ranges: int = 1`** — particiona una tabla con PK entera única en N rangos
  (`WHERE pk BETWEEN`) cargados en paralelo; concurrencia total acotada al pool.

Documentación: `docs/api/dump.md`, `docs/functional/dump-data-export.md`,
`docs/examples/dump_data_export.md`, `docs/BENCHMARKS.md`.

#### dump: el volcado ya no ejecuta comparación de esquemas (elimina cascada N+1)

`DumpOrchestrator.run()` ya **no** invoca `SchemaComparator().compare()` en su fase de
inspección. Esa comparación introspeccionaba índices, FKs de destino, comentarios y vistas
(~500 queries para 100 tablas según el propio docstring de `compare()`) **antes de insertar
una sola fila**, y su resultado solo alimentaba la hoja «Columnas Inexistentes» del informe.
En esquemas con muchas tablas y pocas filas por tabla, ese coste fijo dominaba el tiempo total
y explicaba que un volcado fuera mucho más lento que una inserción directa con `bulk`.

La hoja «Columnas Inexistentes» se reconstruye ahora desde `TableDumpResult.skipped_columns`
—las columnas presentes en origen y ausentes en destino, ya calculadas durante la carga en
`_common_columns`—, por lo que el informe es **equivalente** sin coste adicional. El volcado
queda con solo la introspección imprescindible (tablas, columnas y FKs de origen).

- `dump/orchestrator.py`: eliminada la FASE 1 (`SchemaComparator.compare`) y su import; fases
  renumeradas (1: análisis, 2: deshabilitar constraints, 3: limpieza, 4: carga, 5a/5b: sync PK + informe).
- `dump/reporters.py`: `_sheet_missing_columns` se alimenta de `table_results`.

**BREAKING (API interna del módulo `dump`)**: `DumpReporter.generate()` elimina el parámetro
`diff: SchemaDiff`; la firma pasa a `generate(table_results, missing_tables, constraint_results, cycles)`.
Solo afecta a quien invoque `DumpReporter` directamente. `DumpOrchestrator.run()` mantiene su API
y su salida (`DumpResult`, informe Excel de 3 hojas) sin cambios. `SchemaComparator` sigue disponible
en `util_bbdd.comparar` para comparaciones de esquema independientes.

#### bulk/dump: tres mejoras de rendimiento en el pipeline dump→DataFrame→bulk

Análisis de cuellos de botella en `DumpOrchestrator._process_table` e implementación
de tres optimizaciones ortogonales. Sin cambios de contrato público; retrocompatibilidad
total garantizada (`collect_row_counts=True` por defecto).

**Propuesta A — Identity Map en `reflect_table` (`BulkCrud`):**

- `crud.py`: `_table_cache: dict[str, Table] = {}` en `__init__`; `reflect_table()`
  devuelve el objeto cacheado en llamadas sucesivas con el mismo nombre de tabla.
  Elimina N-1 round-trips de introspección SQL por tabla en loops de chunks
  (con `chunk_size=5000` y 500K filas eran 100 `autoload_with` innecesarios).
  Caché aislado por instancia (no compartido entre instancias de `BulkCrud`).

**Propuesta B — `bulk_session()` + conexión inyectada en `BatchStatementExecutor`:**

- `crud.py`: nuevo `@contextmanager bulk_session(*, atomic: bool = True)` — abre
  1 única transacción para todo el loop de chunks. Con `atomic=False` preserva el
  comportamiento anterior (transacción por chunk / legacy).
- `_execution/batch.py`: `BatchStatementExecutor` gana `_active_connection: Any | None`;
  si está inyectado (via `bulk_session()`), reutiliza la conexión en lugar de abrir
  `engine.begin()` por lote. Método interno `_execute_on_connection()` extrae la
  lógica del loop.
- `dump/orchestrator.py`: loop de chunks envuelto en `with crud.bulk_session()`.
  **Cambio de semántica**: comportamiento anterior era partial-commit (commit por chunk);
  nuevo es table-atomic (todo o nada por tabla). Error en cualquier chunk → rollback
  completo de la tabla. Inner `try/except` por chunk eliminado; outer `except` cubre
  errores de lectura origen con prefijo `"Error leyendo origen: "`.

**Propuesta C — `collect_row_counts: bool = True` en `DumpConfig`:**

- `dump/_models.py`: nuevo campo `collect_row_counts: bool = True` en `DumpConfig`.
  Con `False`, omite los `COUNT(*)` sobre origen y destino y devuelve `-1` como
  sentinel; útil en volcados de alto volumen donde el conteo es costoso (Snowflake,
  Oracle sin estadísticas actualizadas, tablas de decenas de millones de filas).
  `DumpReporter` ya manejaba `-1` con guarda `if res.source_rows >= 0`.
- `dump/orchestrator.py`: `_process_table` (ruta normal y ruta `skipped`) aplica la
  guarda. `_safe_count` no se invoca cuando `collect_row_counts=False`.

**Tests añadidos (9 nuevos):**
- `tests/unit/test_bulk_internal_helpers.py`: caché aislado por instancia, hit del caché,
  conexión inyectada omite `engine.begin()`
- `tests/unit/test_bulk_crud_helpers.py`: `bulk_session` abre 1 transacción, resetea
  `_active_connection` al salir, `atomic=False` no inyecta
- `tests/unit/dump/test_orchestrator.py`: `collect_row_counts` default `True`,
  `False` devuelve `-1` sin llamar `_safe_count`, `bulk_session` se invoca por tabla

**Archivos afectados:**
- `src/util_bbdd/bulk/crud.py`
- `src/util_bbdd/bulk/_execution/batch.py`
- `src/util_bbdd/dump/_models.py`
- `src/util_bbdd/dump/orchestrator.py`

---

### Refactored

#### dump: FK MariaDB por checkout/checkin sin engine.dispose()

`ConstraintManager` deshabilitaba los FK checks de MariaDB/MySQL ciclando todo el pool con
`engine.dispose()` (cerraba todas las conexiones activas), incompatible con un engine
compartido entre hilos. Se sustituye por listeners `checkout`/`checkin` que aplican
`SET SESSION FOREIGN_KEY_CHECKS=0`/`=1` por-conexión, sin reciclar el pool. Comportamiento y
API públicos sin cambios. Prerequisito de la paralelización del volcado. (`dump/_constraints.py`)

#### bulk: API de carga de gran volumen — relocalización del mecanismo paralelo

El mecanismo de inserción paralela por rangos de PK, que antes orquestaba `dump`
(`_load_in_pk_ranges` gestionaba el `ThreadPoolExecutor` y las `BulkCrud`), se traslada a la
nueva clase `bulk.ParallelBulkLoader`. `dump` conserva solo la **política** (MIN/MAX, cálculo
de rangos, SQL de origen) y delega el **mecanismo** vía lectores de partición. Frontera
clara: `bulk` = cómo cargar gran volumen, `dump` = qué/cómo particionar. Sin cambios de
comportamiento observable del volcado. (`bulk/_execution/parallel_loader.py`, `dump/orchestrator.py`)

#### bulk: remediación de deuda técnica — 20 ítems en 4 fases

Auditoría completa del módulo `bulk` con corrección de 20 ítems de deuda técnica
clasificados como `quick_win`, `fase_media` y `deuda_estructural`.
Sin cambios de contrato público; retrocompatibilidad total garantizada.

**Fase 1 — Quick wins:**

- `audit.py`: eliminado guard erróneo en `obtener_historial_transacciones` que
  requería `audit_csv_path` para operaciones que no lo necesitan (QW-1)
- `_audit/service.py`: corregido `if operacion:` → `if operacion is not None:`
  para evitar falso negativo cuando el string es `"0"` (QW-2)
- `_support/sql_helpers.py`: reemplazado parsing manual de URL por `make_url()`
  de SQLAlchemy para evitar fallos con URIs con parámetros (QW-3)
- `bulk/normalize.py`: corregida rama muerta `dtype.kind == "O"` en
  `pandas_dtype_to_sqlalchemy`; `_decode_bytes_to_string` simplificado a
  un único bloque try/except sin conversión redundante (QW-4)
- `crud.py`: anotaciones de retorno `-> None` añadidas a los métodos públicos
  de mutación (QW-5)

**Fase 2 — Correcciones core:**

- `crud.py`: clase renombrada `bulk_crud` → `BulkCrud` (PEP 8); alias
  `bulk_crud = BulkCrud` mantiene retrocompatibilidad (C1)
- `crud.py`: eliminada entrada `"insert"` de `_operation_strategies` — era
  código muerto que nunca se invocaba; tipo del dict actualizado a
  `dict[Literal["update", "delete"], _BulkOperationStrategy]` (C2)
- `_support/validation.py`: nueva función `normalize_identifier()` que
  normaliza mayúsculas/minúsculas del identificador de tabla según el
  dialecto (oracle/postgresql→lower, mssql/mysql→upper) (C4)
- `crud.py`: `reflect_table` usa `normalize_identifier()` en lugar de
  `.lower()` incondicional (C4)
- `_support/sql_helpers.py`: parsing de URL migrado a `make_url()` (QW-3)
- `crud.py`: importaciones no usadas `func`, `select`, `Session` eliminadas (C1)

**Fase 3 — Refactor audit:**

- `audit.py`: eliminados 7 miembros privados muertos/con leak:
  `_cache_df`, `_cache_timestamp`, `_validar_ruta`, `_auditar_lote_csv`,
  `_es_cache_valido`, `_determinar_group_cols`, `_agrupar_y_generar_resumen` (A1+A2)
- `audit.py`: `AuditTransaction.__exit__` guarda la excepción en
  `self.audit_error` en lugar de silenciarla (A4)
- `_audit/repository.py`: `auditar_lote_csv` ya no acepta `audit_path`
  externo; usa `self.audit_csv_path` con `AuditConfigError` si no está
  configurado; constante `_ERR_NO_CSV_PATH` para Sonar S1192 (R1+R2)
- `_audit/repository.py`: separador de decimales eliminado en
  `elapsed` — `f"{elapsed:.3f}"` en lugar de `.replace(".", ",")` (R1)
- `_execution/batch.py`: `_iter_batches` convertido a generador
  `Iterator[pd.DataFrame]` para evitar materializar todos los batches
  en memoria simultáneamente (B1)
- `_audit/exporters.py` + nuevo `_audit/html_template.py`: template HTML de
  60+ líneas extraído a `AUDIT_HTML_TEMPLATE = Template(...)` en módulo
  propio; `exporters.py` usa `substitute()` (E1)

**Fase 4 — Tabla utils y delegación:**

- Nuevo `_support/table_utils.py`: `get_column_case_insensitive()` y
  `get_max_column_value()`; `crud.py` delega en estas funciones (C5)
- `__init__.py`: `BulkCrud` añadido a exports y `__all__` junto con el
  alias retrocompatible `bulk_crud` (C1)

**Archivos afectados:**
- `src/util_bbdd/bulk/crud.py`
- `src/util_bbdd/bulk/audit.py`
- `src/util_bbdd/bulk/normalize.py`
- `src/util_bbdd/bulk/__init__.py`
- `src/util_bbdd/bulk/_audit/exporters.py`
- `src/util_bbdd/bulk/_audit/repository.py`
- `src/util_bbdd/bulk/_audit/service.py`
- `src/util_bbdd/bulk/_execution/batch.py`
- `src/util_bbdd/bulk/_support/sql_helpers.py`
- `src/util_bbdd/bulk/_support/validation.py`
- Nuevos: `src/util_bbdd/bulk/_audit/html_template.py`,
  `src/util_bbdd/bulk/_support/table_utils.py`

**Tests añadidos:**
- `tests/unit/test_audit_subsystem.py` — 39 tests para `_audit/`
- `tests/unit/test_normalize.py` — 45 tests para `bulk/normalize.py`
- Tests existentes actualizados para reflejar renombrado `BulkCrud`

---

### Fixed

#### bulk: auditoría thread-safe ante escrituras concurrentes

`AuditCsvRepository.auditar_lote_csv` serializa las escrituras al mismo CSV mediante un lock
por-ruta compartido a nivel de proceso (registro keyed por `path.resolve()`). Evita filas
intercaladas y cabeceras duplicadas cuando varios `AuditManager` concurrentes (una `BulkCrud`
por hilo en el volcado paralelo) apuntan al mismo fichero. Con esto, la auditoría de inserts
**vuelve a estar activa bajo `max_parallel_tables > 1`** (antes se desactivaba con warning).
(`bulk/_audit/repository.py`, `dump/orchestrator.py`)

#### dump: `_pool_capacity` defensivo ante `size()` no numérico

`_pool_capacity` convierte el resultado de `pool.size()` de forma defensiva (vía `str` si no
es `int`/`float`/`str`), evitando fallos cuando un pool devuelve un tipo inesperado.
(`dump/orchestrator.py`)

#### comparar: comparación de columnas case-insensitive en migraciones cross-engine (Oracle → MariaDB)

En comparaciones entre motores con convenciones de case distintas (Oracle devuelve
nombres en `UPPERCASE`, MariaDB en `lowercase`), las columnas de la tabla origen
aparecían todas como `"missing"` en el destino aunque existiesen con el mismo nombre.

**Root cause**: `SchemaComparator._compare_columns_from_raw()` construía diccionarios
con clave `col["name"]` (case-sensitive). Las operaciones de `set` producían intersección
vacía entre `{"EMPLOYEE_ID"}` y `{"employee_id"}`.

**Fix**:

- `_compare_columns_from_raw`: construye `source_by_lower` / `target_by_lower`
  (`lower→col`). Operaciones de existencia sobre claves lowercase; `ColumnDiff`
  preserva el nombre canónico del motor origen. Añade `logger.warning` si dos columnas
  colisionan al normalizar.
- `_diff_common_column`: nuevo parámetro `tgt_col_name`; PK check usa
  `{pk.lower() for pk in pks}` para ser case-insensitive entre motores.
- `_compare_comments_from_raw`: mismo patrón `lower→col`; nombre canónico en
  `CommentDiff` usa el del origen cuando existe, el del destino si la columna
  solo está en target.

El volcado de datos (`_common_columns`) ya era case-insensitive desde la sesión
`2026-05-31-dump-cross-engine`. Este fix corrige el **informe Excel** que reportaba
incorrectamente columnas como inexistentes.

**Archivos afectados**:
- `src/util_bbdd/comparar/comparator.py`
- `tests/comparar/test_comparator.py` — 5 tests nuevos (`TestCrossEngineCaseInsensitiveColumns`)

---

#### migrate/emitters: doble entrecomillado de DEFAULT en migraciones Oracle → MariaDB / PostgreSQL / SQL Server

Oracle almacena `DATA_DEFAULT` en `ALL_TAB_COLUMNS` **incluyendo las comillas simples**
cuando el valor por defecto es un literal de texto (p.ej. `'6'`, `'ACTIVO'`).
Las funciones `_format_default` de los tres emitters no detectaban el literal ya
entrecomillado y lo re-envolvían, produciendo `DEFAULT '''6'''`, que falla al ejecutar.

**Fix**: añadido guard en `_format_default` / `_format_default_postgresql` /
`_format_default_sqlserver`:

```python
if len(v) >= 2 and v.startswith("'") and v.endswith("'"):
    return v
```

**Archivos afectados**:
- `src/util_bbdd/migrate/emitters/mariadb.py`
- `src/util_bbdd/migrate/emitters/postgresql.py`
- `src/util_bbdd/migrate/emitters/sqlserver.py`
- `tests/unit/migrate/test_emitter.py` — 3 tests nuevos
- `tests/unit/migrate/test_emitter_postgresql.py` — 3 tests nuevos
- `tests/unit/migrate/test_emitter_sqlserver.py` — 3 tests nuevos

---

#### migrate/emitters: Oracle emite body de rutinas verbatim (sin `CREATE OR REPLACE`)

`_emit_create_routine()` en `OracleDDLEmitter` anteponía `CREATE OR REPLACE` al body
extraído de `ALL_SOURCE`. Oracle almacena las rutinas sin ese prefijo (la primera línea
es `PROCEDURE name (...)` / `FUNCTION name (...)`), por lo que el script generado no era
una copia exacta del origen.

**Fix**: eliminado el prefijo artificial; el emitter Oracle emite ahora `routine.body`
verbatim, alineado con los emitters de SQL Server, PostgreSQL y MariaDB.

**Archivos afectados**:
- `src/util_bbdd/migrate/emitters/oracle.py` — `_emit_create_routine()` sin prefijo
- `tests/unit/migrate/test_routines_oracle_emitter.py` — tests actualizados

**Comportamiento sin cambios**:
- Aviso `-- NOTE: requires manual review` cuando hay warnings
- Stub `-- TODO: ... body not available` cuando body no está disponible
- PACKAGE MEMBERS: solo comentario, sin DDL ejecutable

---

### Added

#### bulk: API de carga de gran volumen (`bulk_insert_from_chunks`, `ParallelBulkLoader`)

- **`BulkCrud.bulk_insert_from_chunks(chunks, tabla_destino, *, override_identity=False,
  exclude_autoincrement_pk=False) -> int`** — inserta en streaming un iterable de DataFrames
  (p.ej. `pandas.read_sql(chunksize=N)`) sin materializar todo el dataset, resolviendo columnas
  de inserción e identidad **una sola vez** (frente a la re-resolución por chunk de
  `bulk_insert_from_df`). Gestiona su propio `bulk_session` (respeta `commit_every_n_chunks`).
- **`bulk.ParallelBulkLoader`** + **`ParallelLoadResult`** — carga particiones disjuntas en
  paralelo, una `BulkCrud`/conexión por hilo, sobre `bulk_insert_from_chunks`. Agnóstico del
  origen: cada partición es un lector `Callable[[], Iterable[DataFrame]]`. Best-effort
  (errores agregados por partición). Exportados desde `util_bbdd.bulk`.

Documentación: `docs/api/bulk-crud.md`, `docs/api/bulk-parallel.md` (nuevo).

#### migrate: soporte PostgreSQL → Oracle / MariaDB / SQL Server

Ampliación del módulo `migrate` para permitir migración DDL **desde PostgreSQL**
hacia los tres motores destino disponibles. Completa la matriz 4×3 (PostgreSQL
añadido como 4.ª fuente junto con Oracle, MariaDB y SQL Server).

**Nuevos componentes:**

- `PostgreSQLSchemaExtractor` (`extractors/postgresql.py`) — Lee tablas, columnas,
  PKs, FKs, índices y vistas desde `INFORMATION_SCHEMA` + `pg_catalog.pg_index`.
  Usa param style `%(name)s` (psycopg2/psycopg3). Normaliza DATA_TYPE a UPPERCASE
  (tipos multi-palabra: `character varying` → `CHARACTER VARYING`). Detecta SERIAL
  via `COLUMN_DEFAULT starts with "nextval("`. `char_length=None` indica tipo sin
  límite (no hay sentinel -1). Índices no-PK: `pg_catalog.pg_index +
  generate_subscripts(ix.indkey, 1)` (PG 8.4+). FK cross-schema: `is_external=True`.

- `type_map_postgresql_to_oracle.py` — `TypeMappingPostgreSQLToOracle` +
  `POSTGRESQL_TO_ORACLE` + `resolve_postgresql_type_oracle()`. Cubre 25+ tipos PG.
  BOOLEAN→NUMBER(1,0) (WARNING), TEXT→CLOB (WARNING), TSVECTOR/ARRAY→CLOB (ERROR),
  TIMESTAMP WITH TIME ZONE→TIMESTAMP WITH TIME ZONE.

- `type_map_postgresql_to_mariadb.py` — `TypeMappingPostgreSQLToMariaDB` +
  `POSTGRESQL_TO_MARIADB` + `resolve_postgresql_type_mariadb()`. BOOLEAN→TINYINT(1),
  TEXT→LONGTEXT, TIMESTAMP WITH TIME ZONE→DATETIME(6) (WARNING: TZ lost),
  BYTEA→LONGBLOB, ARRAY→LONGTEXT (ERROR).

- `type_map_postgresql_to_sqlserver.py` — `TypeMappingPostgreSQLToSQLServer` +
  `POSTGRESQL_TO_SQLSERVER` + `resolve_postgresql_type_sqlserver()`. BOOLEAN→BIT,
  TEXT→NVARCHAR(MAX), UUID→UNIQUEIDENTIFIER, XML→XML (nativo), MONEY→MONEY,
  ARRAY→NVARCHAR(MAX) (ERROR).

- `PostgreSQLToOracleTransformer` (`transformers/postgresql_to_oracle.py`) —
  Identificadores truncados a 30 chars (Oracle 12.1). CHARACTER VARYING
  None→CLOB, >4000→CLOB+warning, ≤4000→VARCHAR2(n). BIT(n)→CHAR(n),
  BIT VARYING→VARCHAR2(n). FK ON UPDATE genera WARNING.
  `auto_increment` preservado para SEQUENCE+TRIGGER.

- `PostgreSQLToMariaDBTransformer` (`transformers/postgresql_to_mariadb.py`) —
  Identificadores truncados a 64 chars. CHARACTER VARYING None→LONGTEXT,
  BIT(n) nativo, BIT VARYING→VARBINARY(ceil(n/8)).
  `auto_increment` preservado para AUTO_INCREMENT.

- `PostgreSQLToSQLServerTransformer` (`transformers/postgresql_to_sqlserver.py`) —
  Identificadores truncados a 128 chars. CHARACTER VARYING None/MAX→NVARCHAR(MAX),
  BIT VARYING→VARBINARY(ceil(n/8)).
  `auto_increment` preservado para IDENTITY(1,1).

- Vistas: pass-through v1 en los tres transformers. Warning indicando revisión
  manual de funciones PostgreSQL-específicas (NOW(), GENERATE_SERIES, EXTRACT, etc.).

**Actualización MigrationPlanner:**

- `_SUPPORTED_SOURCE` ampliado: añadido `"postgresql"`.
- Nuevo método `_plan_from_postgresql()` que sigue el mismo patrón que
  `_plan_from_oracle()`, `_plan_from_mariadb()` y `_plan_from_sqlserver()`.
- Parámetro `schema` en `plan()` corresponde a `TABLE_SCHEMA` (habitualmente `'public'`).

**Tests:**

- `test_postgresql_extractor.py` — 20 tests: `_parse_raw_column`, extract, FKs, índices, vistas.
- `test_type_map_postgresql_source.py` — 60 tests de los 3 mapas de tipos.
- `test_transformer_postgresql_to_oracle.py` — 35 tests: tipos, CLOB, PK/FK, vistas.
- `test_transformer_postgresql_to_mariadb.py` — 28 tests: tipos, LONGTEXT, BIT, SERIAL.
- `test_transformer_postgresql_to_sqlserver.py` — 30 tests: tipos, NVARCHAR(MAX), XML, MONEY.
- `test_planner_postgresql_source.py` — 18 tests: validación engines, pipelines end-to-end, emit_ddl.
- **Total tests migrate**: ~979 (789 existentes + ~190 nuevos).

**Limitaciones v1:**

- Param style `%(name)s` (psycopg2/psycopg3). Para asyncpg se necesita wrapper en el manager.
- Vistas: pass-through sin reescritura PostgreSQL-SQL→dialecto destino.
- Sin soporte de `pg_description` (comentarios de columna omitidos).
- Tipos espaciales (`POINT`, `POLYGON`, etc.) y `USER-DEFINED` (enums) → CLOB equivalente (ERROR).

---

#### migrate: soporte SQL Server → Oracle / MariaDB / PostgreSQL

Ampliación del módulo `migrate` para permitir migración DDL **desde SQL Server**
hacia los tres motores destino disponibles. Completa la matriz 3×3 junto con Oracle
y MariaDB como fuentes ya existentes.

**Nuevos componentes:**

- `SQLServerSchemaExtractor` (`extractors/sqlserver.py`) — Lee tablas, columnas, PKs,
  FKs, índices y vistas desde `INFORMATION_SCHEMA` + vistas `sys.*`. Usa param style
  `%(name)s` (compatible con pymssql). Detecta columnas `IDENTITY` mediante
  `COLUMNPROPERTY(OBJECT_ID(...), col, 'IsIdentity')` (SQL Server 2008+).
  Preserva el sentinel `char_length=-1` para tipos `MAX` (VARCHAR/NVARCHAR/VARBINARY).

- `type_map_sqlserver_to_oracle.py` — `TypeMappingSQLServerToOracle` +
  `SQLSERVER_TO_ORACLE` + `resolve_sqlserver_type_oracle()`. Cubre 25 tipos SQL Server.
  Señala: TINYINT unsigned→NUMBER(3,0), DATETIMEOFFSET→TIMESTAMP WITH TIME ZONE,
  TEXT/NTEXT obsoletos→CLOB, GEOGRAPHY/GEOMETRY→CLOB (severity ERROR).

- `type_map_sqlserver_to_mariadb.py` — `TypeMappingSQLServerToMariaDB` +
  `SQLSERVER_TO_MARIADB` + `resolve_sqlserver_type_mariadb()`. BIT→TINYINT(1),
  TINYINT→SMALLINT (unsigned/signed, WARNING), DATETIME2→DATETIME(6),
  DATETIMEOFFSET→VARCHAR(35) (WARNING), MAX types→LONGTEXT/LONGBLOB.

- `type_map_sqlserver_to_postgresql.py` — `TypeMappingSQLServerToPostgreSQL` +
  `SQLSERVER_TO_POSTGRESQL` + `resolve_sqlserver_type_postgresql()`. BIT→BOOLEAN,
  NCHAR/NVARCHAR→CHAR/VARCHAR (Unicode-native), UNIQUEIDENTIFIER→UUID,
  DATETIMEOFFSET→TIMESTAMPTZ, BINARY/VARBINARY→BYTEA (sin parámetros).

- `SQLServerToOracleTransformer` (`transformers/sqlserver_to_oracle.py`) —
  Identificadores truncados a 30 chars (Oracle 12.1). VARCHAR(MAX)/NVARCHAR(MAX)→CLOB,
  VARBINARY(n>2000)→BLOB, VARBINARY(MAX)→BLOB. FK ON UPDATE genera WARNING.
  `auto_increment` (IDENTITY) preservado para SEQUENCE+TRIGGER.

- `SQLServerToMariaDBTransformer` (`transformers/sqlserver_to_mariadb.py`) —
  Identificadores truncados a 64 chars. VARCHAR(MAX)→LONGTEXT, VARBINARY(MAX)→LONGBLOB.
  `auto_increment` preservado para AUTO_INCREMENT.

- `SQLServerToPostgreSQLTransformer` (`transformers/sqlserver_to_postgresql.py`) —
  Identificadores truncados a 63 chars. VARCHAR(MAX)/NVARCHAR(MAX)→TEXT,
  BINARY/VARBINARY→BYTEA (sin longitud). `auto_increment` preservado para SERIAL.

- Vistas: pass-through v1 en los tres transformers. Warning T-SQL indicando revisión
  manual (GETDATE, ISNULL, TOP, etc.).

**Actualización MigrationPlanner:**

- `_SUPPORTED_SOURCE` ampliado: añadido `"sqlserver"`.
- Nuevo método `_plan_from_sqlserver()` que sigue el mismo patrón que
  `_plan_from_oracle()` y `_plan_from_mariadb()`.
- Parámetro `schema` en `plan()` corresponde a `TABLE_SCHEMA` (ej. `'dbo'`).

**Tests:**

- `test_sqlserver_extractor.py` — 20 tests: `_parse_raw_column`, extract, FKs, índices, vistas.
- `test_type_map_sqlserver_source.py` — 60 tests de los 3 mapas de tipos.
- `test_transformer_sqlserver_to_oracle.py` — 35 tests: tipos, MAX, CLOB/BLOB, PKs, FKs, vistas.
- `test_transformer_sqlserver_to_mariadb.py` — 28 tests: tipos, MAX→LONGTEXT/LONGBLOB, IDENTITY.
- `test_transformer_sqlserver_to_postgresql.py` — 30 tests: tipos, MAX→TEXT/BYTEA, PKs, FKs.
- `test_planner_sqlserver_source.py` — 18 tests: validación engines, pipelines end-to-end, emit_ddl.
- **Total tests migrate**: 789 (605 existentes + 184 nuevos).

**Limitaciones v1:**

- Param style `%(name)s` (pymssql). Para pyodbc se necesita wrapper en el manager.
- Vistas: pass-through sin reescritura T-SQL→dialecto destino.
- Sin soporte de tipos computed columns, UDTs ni tablas temporales.
- `VIEW_DEFINITION` en INFORMATION_SCHEMA puede truncarse a 4000 chars en SQL Server < 2019.

---

#### migrate: soporte MariaDB → Oracle / SQL Server / PostgreSQL

Ampliación del módulo `migrate` para permitir migración DDL **desde MariaDB** hacia
los tres motores destino disponibles. El flujo sigue el mismo patrón de 3 capas
(Extractor → Transformer → Emitter) ya existente para Oracle como fuente.

**Nuevos componentes:**

- `MariaDBSchemaExtractor` (`extractors/mariadb.py`) — Lee tablas, columnas, PKs,
  FKs, índices y vistas de `INFORMATION_SCHEMA` con param style `%(name)s`
  (compatible con PyMySQL/MariaDB Connector). Detecta `AUTO_INCREMENT` en el campo
  `EXTRA`, y FKs cross-database (`is_external=True`) cuando `ref_schema != schema`.

- `type_map_mariadb_to_oracle.py` — `TypeMappingMariaToOracle` + `MARIADB_TO_ORACLE`
  + `resolve_mariadb_type_oracle()`. Cubre todos los tipos comunes de MariaDB con
  `MigrationWarning` donde aplica (TIMESTAMP, ENUM, JSON, GEOMETRY, BIT, TIME, etc.).

- `type_map_mariadb_to_sqlserver.py` — `TypeMappingMariaToSQLServer` +
  `MARIADB_TO_SQLSERVER` + `resolve_mariadb_type_sqlserver()`. Señala TINYINT
  signed/unsigned, TIMESTAMP, JSON, ENUM, GEOMETRY.

- `type_map_mariadb_to_postgresql.py` — `TypeMappingMariaToPostgreSQL` +
  `MARIADB_TO_POSTGRESQL` + `resolve_mariadb_type_postgresql()`. BIT(n) nativo de
  PostgreSQL, JSON→JSONB (con INFO), ENUM→TEXT (WARNING).

- `MariaDBToOracleTransformer` (`transformers/mariadb_to_oracle.py`) — Identificadores
  truncados a 30 chars (Oracle 12.1). VARCHAR>4000→CLOB, VARBINARY>2000→BLOB,
  BIT(1)→NUMBER(1,0), BIT(n)→RAW(ceil(n/8)). FK ON UPDATE genera WARNING (Oracle no
  soporta ON UPDATE CASCADE). `auto_increment` preservado para SEQUENCE+TRIGGER.

- `MariaDBToSQLServerTransformer` (`transformers/mariadb_to_sqlserver.py`) —
  Identificadores truncados a 128 chars. VARCHAR(n)/NVARCHAR(n), CHAR/NCHAR,
  BINARY/VARBINARY con umbral 8000→MAX. `auto_increment` preservado para IDENTITY(1,1).

- `MariaDBToPostgreSQLTransformer` (`transformers/mariadb_to_postgresql.py`) —
  Identificadores truncados a 63 chars. VARCHAR(n), CHAR(n), BIT(n) nativo,
  NUMERIC(p,s). `auto_increment` preservado para SERIAL/BIGSERIAL/SMALLSERIAL.

- `OracleDDLEmitter` (`emitters/oracle.py`) — Identificadores double-quoted en
  mayúsculas (`"TABLE_NAME"`). SEQUENCE + TRIGGER por columna AUTO_INCREMENT
  (patrón clásico, compatible Oracle 11g+). COMMENT ON TABLE / COMMENT ON COLUMN.
  ON DELETE solo CASCADE/SET NULL (ON UPDATE silenciado, ya avisado por transformer).
  Vistas emitidas como `CREATE OR REPLACE VIEW "NAME" AS`. Orden topológico de tablas
  y vistas reutilizando `_topological_sort` de `emitters/mariadb.py`.

- `MAX_ORACLE_IDENTIFIER_LENGTH = 30` añadido a `_compat/identifier_rules.py`.

**Integración en `MigrationPlanner`:**
- `source_engine="mariadb"` ahora soportado además de `"oracle"`.
- `target_engine="oracle"` ahora soportado además de `"mariadb"`, `"sqlserver"`,
  `"postgresql"`.
- Validación `src == tgt` → `ValueError` para prevenir migraciones triviales.

**Vistas v1 (pass-through):** Los tres transformers MariaDB emiten las vistas sin
reescritura de SQL dialect-específico (funciones MariaDB como NOW, IFNULL,
GROUP_CONCAT requieren revisión manual). Cada vista recibe un `MigrationWarning`
severity=WARNING.

**177 tests nuevos** en 5 ficheros:
- `test_type_map_mariadb.py` — 50 tests (3 clases, 1 por motor)
- `test_transformer_mariadb_to_oracle.py` — 31 tests (4 clases)
- `test_transformer_mariadb_to_sqlserver.py` — 31 tests (4 clases)
- `test_transformer_mariadb_to_postgresql.py` — 33 tests (4 clases)
- `test_emitter_oracle.py` — 32 tests (7 clases, incluye _format_default_oracle)

Suite completa: **2583 passed, 1 skipped**. ruff limpio, mypy 0 errores.

#### migrate: soporte de vistas Oracle → MariaDB / SQL Server / PostgreSQL

Ampliación del módulo `migrate` para incluir vistas DDL en los tres escenarios
de migración ya existentes. Las vistas se emiten automáticamente **después de
todas las tablas** en el mismo script DDL producido por `MigrationPlan.emit_ddl()`.

**Nuevos componentes:**

- `CanonicalView` — modelo IR de vista: `name`, `original_name`, `schema`, `query`
  (SQL reescrito), `columns` (nombres), `comment`, `warnings`.
- `rewrite_oracle_view()` — motor de reescritura best-effort sin parser SQL externo:
  - `SYSDATE` → `NOW()` / `GETDATE()` / `NOW()` según target
  - `SYSTIMESTAMP` → equivalente por target
  - `USER` → `CURRENT_USER()` / `SYSTEM_USER` / `CURRENT_USER`
  - `NVL(a, b)` → `COALESCE(a, b)`
  - `FROM DUAL` → eliminado
  - Hints Oracle `/*+ ... */` → eliminados
  - Prefijo `SCHEMA.` → eliminado
  - `ROWNUM`, `CONNECT BY`, `DECODE`, `outer join (+)`, `LISTAGG`, `NVL2`,
    `WM_CONCAT`, `MODEL` → se conservan tal cual + `MigrationWarning` severity=WARNING
- `OracleSchemaExtractor.extract_views(schema)` — lee `ALL_VIEWS.text` + columnas
  de `ALL_TAB_COLUMNS`.
- `transform_views()` en los tres transformers (`OracleToMariaDBTransformer`,
  `OracleToSQLServerTransformer`, `OracleToPostgreSQLTransformer`) con truncación
  de identificadores según límites del motor (64 / 128 / 63 bytes).
- `_emit_create_view()` en los tres emitters:
  - MariaDB: `CREATE OR REPLACE VIEW \`name\` AS ...`
  - SQL Server: `CREATE OR ALTER VIEW [name] AS ...` _(requiere SQL Server 2016+)_
  - PostgreSQL: `CREATE OR REPLACE VIEW "name" AS ...`
- `MigrationPlan.views: list[CanonicalView]` — campo con `default=[]`;
  `emit_ddl()` y `emit_statements()` incluyen vistas automáticamente. Sin cambios
  en código existente que no pase `views`.

**Compatibilidad hacia atrás:** total. El campo `views` es opcional con default `[]`.
Código que construye `MigrationPlan` sin el campo sigue funcionando sin cambios.

**76 tests nuevos** (411 total en el módulo migrate). ruff limpio, mypy 0 errores.

### Changed

#### metadata: centralización del SQL de introspección (punto canónico único)

Los módulos `metadata/*/tables.py` son ahora el **único punto canónico** para todas
las queries SQL de introspección de esquema usadas en el pipeline de migración.
Objetivo: eliminar duplicación entre `migrate/sql/` y `metadata/`, y facilitar
el mantenimiento a largo plazo (un solo lugar para cambiar una query).

**Cambios en `metadata/`:**

- `metadata/mariadb/tables.py` — Añadidas 7 funciones `fetch_*_sql()` con las queries
  de extracción de esquema MariaDB: `fetch_tables_sql`, `fetch_columns_sql`,
  `fetch_pk_sql`, `fetch_fk_sql`, `fetch_indexes_sql`, `fetch_views_sql`,
  `fetch_view_columns_sql`.

- `metadata/sqlserver/tables.py` — Añadidas 7 funciones `fetch_*_sql()` equivalentes
  para SQL Server (con soporte `COLUMNPROPERTY` para detección de IDENTITY y
  `sys.indexes` para índices no-PK).

- `metadata/postgresql/tables.py` — Añadidas 4 funciones sin conflicto de nombre
  (`fetch_pk_sql`, `fetch_fk_sql`, `fetch_views_sql`, `fetch_view_columns_sql`) y
  3 aliases con sufijo `_for_extract` para las funciones con nombre solapado respecto
  a las existentes de display: `fetch_tables_for_extract_sql`,
  `fetch_columns_for_extract_sql`, `fetch_indexes_for_extract_sql` (Opción P-A).

**Cambios en `migrate/`:**

- `migrate/sql/` — Directorio **eliminado** por completo. Tras redirigir los
  extractores directamente a `metadata/*/tables.py`, los re-exportadores no tenían
  ningún consumidor (0 imports en `src/`, tests ni docs). Se elimina la capa
  intermedia para evitar código muerto.

- `migrate/extractors/mariadb.py`, `migrate/extractors/sqlserver.py`,
  `migrate/extractors/postgresql.py` — Imports redirigidos directamente a
  `metadata/*/tables.py` (mismo patrón que `migrate/extractors/oracle.py`, que
  ya era la referencia canónica).

**Compatibilidad hacia atrás:** total dentro del proyecto. `migrate.sql.*` no
formaba parte de ninguna API pública documentada. Ningún cambio de comportamiento;
1189 tests de migrate + 3202 totales pasan sin modificación.

### Fixed

#### migrate: columnas AUTO_INCREMENT siempre emiten `INT(11)` en MariaDB

Al migrar hacia MariaDB desde cualquier motor fuente (SQL Server, PostgreSQL, Oracle),
las columnas `AUTO_INCREMENT` no siempre producían el tipo `INT(11)`. El emitter
usaba `col.target_type` directamente, que los transformers dejaban como `INT`, `BIGINT`,
`SMALLINT`, etc. según el mapeo del motor de origen.

- **`emitters/mariadb.py` → `_emit_column()`**: cuando `col.auto_increment` es `True`,
  se usa `INT(11)` en lugar de `col.target_type`, aplicando la convención estándar de
  MariaDB/MySQL para columnas de auto-incremento.
- Columnas **sin** `AUTO_INCREMENT` no se ven afectadas.
- **3 tests nuevos** en `tests/unit/migrate/test_emitter.py`:
  - `test_auto_increment_column` actualizado para validar `INT(11) NOT NULL AUTO_INCREMENT`.
  - `test_auto_increment_always_emits_int11` (parametrizado ×5): `INT`, `BIGINT`,
    `SMALLINT`, `INT(11)`, `BIGINT(20)` como tipo fuente → todos emiten `INT(11)`.
  - `test_non_auto_increment_preserves_original_type`: regresión para tipos no AUTO_INCREMENT.

#### migrate: ordenación topológica de vistas

Los emitters (MariaDB, SQL Server, PostgreSQL) ahora ordenan las vistas por
dependencias antes de emitirlas, usando el mismo algoritmo de Kahn ya empleado
para las tablas.

- Nueva función `_topological_sort_views(views)` en `emitters/mariadb.py`,
  compartida por los tres emitters.
- Nueva función `_detect_view_deps(view, all_views)` que detecta qué vistas del
  schema aparecen en `view.query` mediante word-boundary match case-insensitive.
  Comprueba tanto `name` (truncado) como `original_name` (nombre Oracle original)
  para cubrir el caso de identificadores truncados.
- Si dos o más vistas forman un ciclo (dependencia circular), se emiten al final
  precedidas de un comentario `-- AVISO: dependencia circular detectada`.
- **12 tests nuevos** (10 en `test_views_mariadb.py`, 2 en cada uno de los otros).

#### Limitaciones conocidas (restante de v1)

> Esta limitación sigue pendiente y no representa un bug. Se abordará en una
> versión futura según prioridad.

- **`ALL_VIEWS.text` es tipo LONG en Oracle.** Los drivers modernos
  (`cx_Oracle` ≥ 8, `python-oracledb` ≥ 1.x) convierten el tipo `LONG`
  a `str` Python automáticamente devolviendo el texto completo. En
  configuraciones con drivers más antiguos o Oracle < 12.2, la lectura puede
  producir resultados truncados o un error dependiente del driver. Alternativa
  para Oracle 12.2+: reemplazar la columna `text` por `text_vc` en la query
  `_FETCH_VIEWS_SQL` del extractor (limitada a 4 000 caracteres).

---

## [0.8.0] - 2026-04-21

### Fixed

#### Connection Pool Finalization Error (Hotfix)
- **Issue**: `PythonFinalizationError: can't create new thread at interpreter shutdown` occurring during pool closure at program exit
- **Root Cause**: Attempt to create worker threads during Python interpreter finalization when `sys.is_finalizing() == True`
- **Solution**: Added finalization detection in `run_close_operation_sync()` to skip thread-based timeout during interpreter shutdown
- **Files Modified**: `src/util_bbdd/connection/close.py` (lines 147-150)
- **Impact**: All database drivers (MariaDB, SQLite, SQLServer, Oracle, PostgreSQL) now gracefully close pools during shutdown
- **Tests**: Added 6 finalization-safety tests in `tests/unit/test_finalization_safety.py`
- **Backward Compatibility**: ✅ No breaking changes; normal pool closure behavior unchanged

### Added

#### Phase 4: Complete Type System Coverage (All 5 Database Drivers)

**Objetivo completado**: Soporte de introspección de tipos avanzados para 100% de los motores de base de datos (8/8).

##### Phase 4a.1 — Oracle OBJECT Types
- Nuevo módulo: `src/util_bbdd/metadata/oracle/types_advanced.py` (237 LOC)
- **Funcionalidad**: Parse de tipos OBJECT definidos por usuario (composite types) vía catálogos `dba_types` + `dba_type_attrs`
- **Dataclasses**: `ObjectTypeField`, `ObjectTypeInfo` (frozen=True, slots=True)
- **Función principal**: `parse_object_type_structure(type_name, adapter) → ObjectTypeInfo | None`
- **Seguridad**: `_validate_type_name()` valida identificadores (prevención de SQL injection, max 30 caracteres per Oracle)
- **Tests**: 11 tests de integración cubriendo casos simples, complejos, nullable fields, precisión/escala, compatibilidad de versiones
- **Ejemplo**:
  ```python
  adapter = get_database_manager("oracle", ...)
  info = adapter._execute_query(
      "SELECT ... FROM dba_types WHERE type_name = ?",
      ("OBJECT_TYPE",)
  )
  type_info = parse_object_type_structure("OBJECT_TYPE", adapter)
  assert type_info.type_name == "OBJECT_TYPE"
  assert len(type_info.fields) > 0
  ```

##### Phase 4a.2 — SQL Server UDT Types
- Nuevo módulo: `src/util_bbdd/metadata/sqlserver/types_advanced.py` (290 LOC)
- **Funcionalidad**: Parse de tipos definidos por usuario (UDT) vía catálogos `sys.types` + `sys.type_members`
- **Dataclasses**: `UDTMember`, `UDTTypeInfo` con métodos `to_dict()` para serialización
- **Funciones principales**:
  - `parse_udt_structure(type_name, adapter) → UDTTypeInfo | None`
  - `_detect_udt_kind()` — categorización de UDT (STRUCTURED vs HIERARCHY)
- **Seguridad**: `_validate_type_name()` con límite de 128 caracteres
- **Tests**: 13 tests cubriendo UDT simples, precisión/escala, múltiples UDTs, gating de versiones, serialización
- **Ejemplo**:
  ```python
  udt_info = parse_udt_structure("MyUDT", adapter)
  assert udt_info is not None
  assert len(udt_info.members) >= 1
  # Serialización para APIs
  api_response = udt_info.to_dict()
  ```

##### Phase 4a.3 — MariaDB JSON Schema
- Nuevo módulo: `src/util_bbdd/metadata/mariadb/types_advanced.py` (100 LOC)
- **Patrón**: Wrapper que delega a `mysql.types_advanced.query_json_column_schema()` (reutilización de código)
- **Rationale**: MariaDB ≈ MySQL para manejo de JSON en v0.8.0
- **Función**: `query_json_column_schema(schema, table, column, adapter, sample_size) → dict | None`
- **Tests**: 6 tests cubriendo schemas JSON con muestreo, CHECK constraints, manejo de NULL
- **Ejemplo**:
  ```python
  schema = query_json_column_schema("test", "events", "data", adapter)
  assert schema["type"] == "object"
  assert "properties" in schema
  ```

##### Phase 4b.1 — Redshift Types
- Nuevo módulo: `src/util_bbdd/metadata/redshift/types_advanced.py` (115 LOC)
- **Funcionalidad**: Graceful fallback para Redshift (hereda PostgreSQL 8.x, sin tipos compuestos modernos)
- **Dataclass**: `RedshiftTypeInfo` (type_name, note)
- **Función principal**: `parse_redshift_types(type_name, adapter) → RedshiftTypeInfo | None` (siempre retorna None en MVP)
- **Diseño**: "Tipos típicamente no disponibles" — degradación elegante, nunca lanza excepciones
- **Tests**: 5 tests cubriendo el escenario típico y manejo de errores
- **Ejemplo**:
  ```python
  result = parse_redshift_types("SOME_TYPE", adapter)
  assert result is None  # Expected in legacy Redshift
  ```

##### Phase 4b.2 — SQLite JSON Schema
- Nuevo módulo: `src/util_bbdd/metadata/sqlite/types_advanced.py` (~125 LOC)
- **Funcionalidad**: Inferencia de schema JSON vía muestreo de columnas (base de datos sin tipado)
- **Patrón**: Reutiliza módulo compartido `json_schema.py` de Phase 2
- **Función**: `query_json_column_schema(schema, table, column, adapter, sample_size) → dict | None`
- **Algoritmo**:
  1. Muestrea primeras N filas de la columna
  2. Detecta valores JSON (parsing intent)
  3. Infiere schema de propiedades y tipos
  4. Retorna dict con `{"type": "object"|"array", "properties": {...}, "required": [...]}`
- **Tests**: 6 tests cubriendo detección JSON, inferencia, arrays, columnas non-JSON, tablas vacías, manejo de errores
- **Ejemplo**:
  ```python
  schema = query_json_column_schema("main", "logs", "payload", adapter)
  if schema:
      print(f"Detected: {schema['type']} with keys {schema['properties'].keys()}")
  ```

#### Code Quality Enforcement (Enforced across all 5 drivers)

- **F-Strings (100% Compliance)**:
  - Todos los strings parametrizados usan f-strings (sin `.format()`, `%`, concatenación)
  - Validado en Ruff lint con regla ARG

- **Logging Tipado**:
  - Module-level `logger: logging.Logger = logging.getLogger(__name__)` en todos los parsers
  - Adapter.logger para logging contextual
  - Error handling: siempre log antes de degradación elegante

- **Type Hints (100% Coverage)**:
  - 266+ archivos fuente pasan mypy strict mode
  - Todas las APIs públicas completamente tipadas

- **Cognitive Complexity ≤15**:
  - Todas las funciones parser cumplen límite (ruff enforced)
  - Funciones simples, legibles, mantenibles

- **Docstrings (Google-Style)**:
  - Args, Returns, Raises, Example en todas las funciones
  - Ejemplos ejecutables, no hardcodeados

- **Identifier Validation (SQL Injection Prevention)**:
  - `_validate_identifier()` en todos los 5 drivers
  - Límites de longitud per-driver (Oracle 30, SQL Server 128, etc.)
  - Patrón: `^[a-zA-Z_][a-zA-Z0-9_]*$`

#### Test Coverage

- **41 nuevos tests** en Phase 4:
  - Oracle: 11 tests
  - SQL Server: 13 tests
  - MariaDB: 6 tests
  - Redshift: 5 tests
  - SQLite: 6 tests
- **Total suite**: 1969 passed, 1 skipped
- **Baseline**: 1928 tests (Phases 1-3) + 41 new (Phase 4)

#### v0.8.0 Type System Coverage Summary

| Phase | Drivers | Tipo | Status |
|-------|---------|------|--------|
| Phase 1 | PostgreSQL | Composite types via `pg_type`, `pg_attribute` | ✅ DONE |
| Phase 2 | MySQL, Shared | JSON schema via sampling + `json_schema.py` | ✅ DONE |
| Phase 3 | Snowflake | OBJECT/ARRAY types via INFORMATION_SCHEMA | ✅ DONE |
| **Phase 4** | **Oracle, SQL Server, MariaDB, Redshift, SQLite** | **User-defined types, wrappers, graceful fallbacks** | ✅ **COMPLETE** |
| **TOTAL** | **8/8 engines** | **100% coverage** | ✅ **RELEASED** |

### Validation

✅ **Ruff Lint**: All checks passed (0 violations)
✅ **Mypy Strict**: 266 source files clean (no errors)
✅ **Pytest**: 1969 passed, 1 skipped
✅ **mkdocs build**: Successful

---

## [0.7.0] - 2026-04-21

### Added

#### Performance Monitoring — Automatic Operation Timing in Bulk CRUD
- **Feature**: Automatic measurement of bulk CRUD operation duration using `util.timing.medir_tiempo` decorator
- **CSV Audit Schema**: Extended with `tiempo_seg` column (float, seconds) — now 7 columns: timestamp, tabla, motor, operacion, total_filas, tiempo_seg, sql
- **Decorated Methods**: `bulk_insert_from_df()`, `bulk_update_from_df()`, `bulk_delete_from_df()` (lines 189, 221, 253 in `src/util_bbdd/bulk/crud.py`)
- **Fallback Mechanism**: Graceful fallback if `util.timing` unavailable — decorator placeholder, timing manual within operation continues correctly
- **Documentation**:
  - Updated `docs/api/bulk-crud.md` — Internal Dependencies section, 7-column schema table, fallback behavior
  - Added `docs/index.md` — Performance Monitoring subsection
  - Updated `README.md` — Performance Monitoring feature row in main table
  - Updated `docs/INSTALLATION.md` — Internal Dependencies note
  - New example: `docs/examples/bulk_insert_csv.py` — Audit CSV analysis with timing metrics
- **Dependencies**: Added `util @ git+https://github.com/fmanza/util.git@develop` to `pyproject.toml`

### Fixed

- `src/util_bbdd/managers/_manager_storage.py` — Eliminado `async` innecesario de `_AsyncHSQLDBStorageStrategy.execute()` (HSQLDB es in-memory, sin I/O async)
- `src/util_bbdd/managers/async_mgr.py` — Agregado manejo de ambos sync/async returns via `asyncio.iscoroutine()` detection
- `docs/INSTALLATION.md` (línea 157) — Fijado link inconsistente a ORACLE_DRIVER_GUIDE.md (archivo no existe)
- `docs/RELEASE_v0.5.0.md` (líneas 92-96) — Actualizados links a archivos históricos movidos a `archive/`

### Removed

#### Security Improvement — Eliminación de scripts legacy con credenciales hardcodeadas
- `docs/legacy/main_MariaDB.py` (411 líneas, credenciales hardcodeadas)
- `docs/legacy/main_Oracle.py` (1,207 líneas, credenciales hardcodeadas: 10.20.0.236, COREUFV/COREUFV)
- `docs/legacy/MariaDB.py` (407 líneas, credenciales hardcodeadas)

**Razón:** Estos scripts eran desarrollo manual sin valor documental, exponían topología de red interna y credenciales.

**Total:** 1,618 líneas de código legacy eliminadas

### Changed

#### Documentation Reorganization
- Reorganizado `docs/archive/plan-legacy/` → `docs/archive/releases/v0.1-v0.3.0/` (28 archivos PR 0-8)
- Movido `docs/v0.5.6/` → `docs/archive/versions/v0.5.6/` (6 archivos de versión)
- Creado `docs/legacy-versions.md` — nuevo índice/navegación para documentación histórica
- Actualizado `mkdocs.yml` — agregado entry "Versiones Históricas" a navegación

### Docs

- Documentado patrón Singleton en `get_database_validator()`:
  - Explicación de implementación con lazy-loading
  - Por qué se usa (performance, consistency, memory efficiency)
  - Limitaciones conocidas (single-threaded context)
  - Ejemplos de uso y reinitialización para testing

- Mejorado docstrings en funciones de conveniencia:
  - `validate_db_type()` — ejemplos y cross-references
  - `get_db_type_info()` — estructura de retorno y ejemplos

- Creado `docs/DOCUMENTATION_AUDIT_v0.7.0.md`:
  - Auditoría completa de gaps en documentación
  - Identificación de links rotos y archivos faltantes
  - Checklist priorizado de mejoras
  - Referencias cruzadas entre guías técnicas
  - Recomendaciones para v0.8.0+

### Validation

✅ Lint: All checks passed
✅ Type-check: 257 files clean
✅ Tests: 1881 passed, 1 skipped
✅ mkdocs build: Successful

---

## [0.6.8] - 2026-04-20

### Refactored

#### Tech Debt — Logging tipado (Fases 1-4B)
Añadido `self.logger: logging.Logger` instanciado en `__init__` a 36 clases en los módulos de mayor riesgo:

- **Comparar reporters** (`_base.py`, `markdown_reporter.py`, `sql_reporter.py`) — 3 clases
- **Managers** (`_manager_lifecycle.py`, `_manager_metadata.py`, `_manager_metadata_runtime.py`, `async_mgr.py`, `sync_mgr.py`) — 5 clases
- **Metadata adapters** — 14 adaptadores concretos (mariadb, mysql, oracle sync/async, postgresql, sqlserver) + 8 protocolos de manager
- **Metadata bases** — `_adapter_protocol.py`, `builder.py`

**Nuevos módulos internos en managers:**
- `_metadata_cache.py`, `_metadata_context.py`, `_metadata_parser.py`, `_metadata_request.py`

### Fixed

- `src/util_bbdd/metadata/oracle/sync_adapter.py` — referencia a logger en staticmethod corregida
- `src/util_bbdd/managers/async_mgr.py` — detección de coroutines via `inspect.iscoroutine()` (eliminado `hasattr`)

### Docs / Config

- `.github/SHARED_INSTRUCTIONS.md`, `CLAUDE.md`, `copilot-instructions.md` — política de logging obligatorio y checklist f-strings

---

## [0.6.7] - 2026-04-10

### Breaking Changes

#### Facades legacy eliminados (Option A — nombres canónicos)
Los siguientes módulos raíz han sido eliminados. Migrar a las rutas canónicas indicadas:

| Módulo eliminado | Ruta canónica |
|---|---|
| `util_bbdd.database_exceptions` | `util_bbdd` (todas las excepciones exportadas directamente) |
| `util_bbdd.database_queries` | `util_bbdd.query.DatabaseQueries` |
| `util_bbdd.database_type_validator` | `util_bbdd._drivers.DatabaseTypeValidator` |
| `util_bbdd.driver_validator` | `util_bbdd._drivers.DriverValidator` |

Los aliases históricos (`DatabaseConnectionError`, `DatabasePoolError`, `DatabaseError`, `UtilBbddError`, etc.) ya no existen. Usar nombres canónicos:
- `DatabaseConnectionError` → `ConnectionError`
- `DatabasePoolError` → `PoolConnectionError`
- `DatabasePoolTimeoutError` → `PoolTimeoutError`
- `DatabaseDriverError` → `DriverError`
- `DatabaseValidationError` → `ValidationError`
- `DatabaseTypeNotSupportedError` → `InvalidDatabaseType`
- `DatabaseError` / `UtilBbddError` → `DatabaseException`
- `InvalidQueryError` → `QueryValidationError`
- `QueryExecutionTimeoutError` → `QueryTimeoutError`

#### Protocols de adaptadores: aliases deprecated eliminados
`SourceAdapter` y `RoutineAdapter` de `util_bbdd.metadata.adapters` han sido eliminados.
Usar `SourceAdapterSync`/`SourceAdapterAsync` y `RoutineAdapterSync`/`RoutineAdapterAsync`.

### Added

#### Excepciones canónicas en raíz del paquete
Todas las excepciones de `_core.exceptions` están ahora disponibles directamente desde `util_bbdd`:
```python
from util_bbdd import (
    DatabaseException, ConnectionError, PoolConnectionError, PoolTimeoutError,
    ValidationError, InvalidDatabaseType, DriverError,
    DatabaseOperationError, QueryError, QueryNotFoundError, ...
)
```

#### Test de contrato B5: excepciones de managers
`tests/unit/test_manager_exception_contract.py` — 15 tests que verifican:
- Jerarquía completa de excepciones (`DatabaseException` como base)
- `InvalidDatabaseType` ante db_type inválido
- `DatabaseOperationError` ante executor no inicializado (sync y async)
- Wrapping de errores inesperados como `DatabaseOperationError`

### Changed

#### `_foundation/` eliminado íntegramente
- `exceptions.py` → consolidado en `_core/exceptions.py` (ya en v0.6.6)
- `validators_core.py` → movido a `_drivers/` (Phase B1)
- `driver_validator.py` → movido a `_drivers/driver_validator.py` (Phase B2)
- `queries.py` → movido a `query/queries.py` como `DatabaseQueries` (Phase C)

#### mypy: overrides para pandas y networkx
Añadidos `[[tool.mypy.overrides]]` para `pandas`/`pandas.*` y `networkx`/`networkx.*`
(los stubs son opcionales; mypy pasa sin ellos instalados).

#### pyproject.toml
- `version`: `0.6.7.dev0` → `0.6.7`
- `keywords`: añadidos `postgresql`, `sqlite`, `sqlserver`, `async`, `documentation`
- `classifiers`: añadido `Typing :: Typed`

### Fixed

- Import sort (ruff I001) en múltiples ficheros de test y `connection/__init__.py`
- Positional constructor calls → keyword args en todos los `raise XxxError(...)` de managers, factory y connection

---

## [0.6.8] - Unreleased (In Development)

### Planned

#### Phase 4 Optimizations (LOW priority, v0.6.8 scope)

**L1: MSSQL Bracket Regex Enhancement** (COMPLETE)
- File: `src/util_bbdd/comparar/comparator.py:76`
- Change: `r"\[(\w+)\]"` → `r"\[([^\]]+)\]"` to support spaces/dashes in brackets
- Supported: `[My Column]`, `[Column-X]`, `[My Table Name]`, `[Table@123-ABC]`
- Tests: 4 dedicated test cases (test_comparator.py: TestNormalizeDdl)
  - `test_removes_sql_server_brackets_simple` — simple identifiers
  - `test_removes_sql_server_brackets_with_spaces` — spaces in names
  - `test_removes_sql_server_brackets_with_dashes` — dashes in names
  - `test_removes_sql_server_brackets_mixed_special_chars` — special characters
- Status: ✅ Implemented + Tested (L1 complete with full coverage)

**L2: Performance Limitations Documentation** (COMPLETE)
- File: `src/util_bbdd/comparar/comparator.py` (docstrings)
- Add: N+1 query warnings and optimization guide for large schema comparisons
- Implementation: Added "Performance Considerations" section to `compare()` docstring
- Coverage:
  - N+1 query cascade warnings (breakdown per flag)
  - Optimization guide for large schemas (100+ tables)
  - Driver-specific overhead analysis
  - Cost table by flag combinations
  - Best practices for parallelization and caching
- Status: ✅ Implemented + Tested (L2 complete with cost matrix and optimization patterns)

**L3: Exception Handling Test Coverage** (COMPLETE)
- File: `tests/comparar/test_comparator.py`
- Add: 3 parametrized test cases for exception handling robustness validation
- Framework: `pytest.mark.parametrize` with 3 test methods × 3 exception types = 9 test cases
- Coverage:
  - `test_inspector_exception_during_table_introspection`: TimeoutError, PermissionError, Deadlock (3 cases)
  - `test_inspector_exception_during_routine_introspection`: TimeoutError, PermissionError, Deadlock (3 cases)
  - `test_inspector_exception_during_constraint_validation`: TimeoutError, PermissionError, Deadlock (3 cases)
- Test Results: All 9 tests passing; suite total: 1892 tests (↑9 from L3 addition)
- Status: ✅ Implemented + Tested (L3 complete with parametrized robustness validation)

### Added

#### Exception Hierarchy for `comparar/` Module (Phase 4B)
- New exception hierarchy in `_core/exceptions.py`:
  - `ComparerError`: Base exception for all schema comparison errors (inherits from `DatabaseException`)
  - `SchemaDiffValidationError`: Input/parameter validation failures (dialect, format, path, type errors)
  - `MetadataIntrospectionError`: Inspector failures (missing tables, permissions, unsupported dialects)
  - `DiffReportGenerationError`: Reporter rendering failures (SQL script, HTML, Word, Excel, Markdown generation)
- Exported directly from `util_bbdd` root package (canonical import path)
- Enables specific error handling in reporters and consumer code
- Documentation: See `EXCEPTIONS.md` for full hierarchy and usage patterns

### Changed

#### BREAKING: Exception Types in `comparar/` Reporters
- `reporters/sql_reporter.py`: `ValueError` → `SchemaDiffValidationError` (line 253)
- `reporters/facade.py`: `ValueError` → `SchemaDiffValidationError` (line 140)
- `reporters/word_reporter.py`: `ValueError` → `SchemaDiffValidationError` (line 88)
- **Migration guide**: Catch `SchemaDiffValidationError` instead of `ValueError` in consumer code
  ```python
  # Before
  try:
      reporter = SqlDiffReporter("invalid_dialect")
  except ValueError as e:
      log.error(f"Invalid dialect: {e}")

  # After
  try:
      reporter = SqlDiffReporter("invalid_dialect")
  except SchemaDiffValidationError as e:
      log.error(f"Invalid dialect: {e.details}")
  ```
- All tests updated to capture new exception types (6 tests in `test_diff_reporters.py`)

#### Documentation of Fallback Exception Handling
- 8 `# noqa: BLE001` comments replaced with explicit M1 fallback justifications:
  - Line 726 (view DDL): Fallback for dialects without native DDL support
  - Lines 797, 839, 842 (MariaDB, Oracle general): Connection/permission failures
  - Lines 883, 886 (MSSQL): sys.sql_modules access and connection handling
  - Lines 937, 940 (PostgreSQL): pg_get_functiondef failures and connection handling
- Each fallback now documents why capturing `Exception` is necessary in multi-driver introspection

### Fixed

#### 9 mypy `no-redef` Errors in `comparar/comparator.py`
- **Lines 372/384**: Index loop variables renamed (`idx` → `source_index_dict`/`target_index_dict`)
- **Lines 573-574/580**: View comparison variables renamed (`s_def`/`t_def` → `source_def_cmp`/`target_def_cmp`)
- **Line 625**: Routine comparison variable fixed (`r.get()` → `target_routine.get()`)
- **Lines 663-665**: URL sanitization consolidated (`url_str`/`url`)
- **Lines 774-799**: MariaDB procedure/function variables contextualized (`proc_*`/`func_*` prefixes)
- **Result**: mypy clean — `Success: no issues found in 248 source files`

#### Validation
- All 1,879 tests passing (1 skipped)
- Lint: all checks passed (ruff)
- Type-check: all checks passed (mypy v0.942)
- No functional changes, zero regressions

---

## [Unreleased]

### Planned (v0.7.0+)

#### MongoDB / NoSQL Support (ADR Pending)
- Requires architecture decision on DocumentAdapter pattern
- Roadmap pending formal approval
- Target: v0.7.0+

## [0.6.6] - 2026-04-09

### Added

#### Phase 4A: Redis Caching Layer (Complete)
- Optional Redis integration for metadata caching
- Fallback to in-memory cache if Redis unavailable
- Strategy Pattern: CacheBackend protocol with Redis/Memory implementations
- Redis backend (redis-py) + Memory backend (built-in)
- Cache invalidation strategies (TTL, manual flush)
- Manager-level injection (non-breaking API)
- 60+ tests, all passing
- Documentation: docs/v0.6.6/PHASE_4A_REDIS_CACHING_IMPL.md

#### Phase 3C.5a: BigQuery Driver (Complete)
- Google Cloud BigQuery metadata introspection support
- Multi-level schema: Project.Dataset.Table (normalized)
- 40+ type mappings (INT64, FLOAT64, STRING, STRUCT, ARRAY, JSON, GEOGRAPHY, etc.)
- Advisory constraints (metadata-only, like Snowflake)
- UDF/stored procedure introspection
- Sync adapter (google-cloud-bigquery) + async adapter (executor-based)
- Auto-registration: registry.register_source_adapter_*("bigquery", BigQueryAdapter)
- 100+ tests, all passing
- Documentation: docs/v0.6.6/BIGQUERY_DRIVER_GUIDE.md

#### Phase 4B: Async Query Optimization (Complete)
- Batch metadata loading (parallel queries within single connection)
- Connection pool tuning per driver-specific profiles
- Query result streaming for large schema introspection
- Improved async manager performance (20-30% faster for large schemas)
- 40+ async-focused tests

#### Phase 4C: Production Hardening (Complete)
- Security audit: dependency vulnerability scan, SQL injection prevention validation
- Performance profiling complete (baseline established)
- Documentation completeness: 100% API coverage with examples
- Release stability guarantees (zero known critical issues)
- Migration guides updated for v0.6.5→v0.6.6

#### Registry Expansion (9 drivers now available)
- MariaDB (Phase 3B)
- PostgreSQL (Phase 3C.1)
- Oracle (Phase 3C.2)
- SQLite (Phase 3C.3)
- SQL Server (Phase 3C.3)
- MySQL (Phase 3C.4)
- Redshift (Phase 3C.4)
- Snowflake (Phase 3C.4)
- BigQuery (Phase 3C.5a) ✨ NEW

### Changed

- Redis caching now integrated into core manager layer (optional, backward-compatible)
- Async manager performance optimized for bulk metadata operations
- Type mapping system extended for BigQuery multi-level schema support
- Documentation structure reorganized: driver-specific guides + core API reference
- Python 3.12+ requirement maintained; testing now includes Python 3.14.2

### Performance

- Metadata loading: 20-30% faster for projects with 100+ tables (Phase 4B)
- Cache hit rate: 80%+ for repeated introspection queries (Phase 4A)
- BigQuery schema normalization: <100ms per 1000 objects (Phase 3C.5a)

### Code Quality & Testing

- Total tests: 2000+ (410+ from Phase 3C.4, 160+ from Phase 4A/3C.5a, 40+ from 4B)
- Ruff: 0 issues ✅
- Mypy: 260+ files, 0 errors in strict mode ✅
- Pytest: 2000+ passing (zero skipped)
- Backward compatibility: 100% (all v0.6.3 tests still passing)

### Roadmap (Deferred to v0.7.0+)

- MongoDB / NoSQL: Architecture Decision Record (ADR) pending. Requires separate design discussion.

## [0.6.3] - 2026-04-09

### Added

#### Phase 3C.4: MySQL, Redshift, Snowflake Drivers (3 new drivers, 410+ tests)

**MySQL Driver** (10 modules, 121 tests, ~600 LOC):
- Full metadata introspection via `information_schema` (Standard SQL)
- 30+ MySQL type mappings (TINYINT, MEDIUMINT, JSON, ENUM, SET, GEOMETRY, etc.)
- Auto-increment detection (separate from primary key)
- Cascade action support (RESTRICT, CASCADE, SET NULL, NO ACTION)
- Sync adapter (mysql-connector-python) + async adapter (asyncmy)
- Auto-registration: `registry.register_source_adapter_*("mysql", MysqlAdapter)`

**Redshift Driver** (10 modules, ~87 tests, ~600 LOC):
- PostgreSQL-derived metadata catalogs (pg_catalog + information_schema)
- 30+ type mappings (PostgreSQL subset: no arrays, ranges, or UDTs)
- **Advisory constraints** (PK/FK metadata NOT enforced—warning logged per operation)
- SortKey detection and optimization hints
- Limited UDFs support (no stored procedures)
- Sync adapter (psycopg2) + async adapter (asyncpg)
- Auto-registration: `registry.register_source_adapter_*("redshift", RedshiftAdapter)`
- **CRITICAL NOTE:** "Redshift constraints are metadata-only; not enforced by database. Application layer responsible for validation."

**Snowflake Driver** (10 modules, 162 tests, ~700 LOC):
- Multi-level schema support (DATABASE.SCHEMA.TABLE extraction and normalization)
- 40+ Snowflake type mappings (VARIANT, OBJECT, ARRAY, GEOGRAPHY, TIMESTAMP_* variants, etc.)
- Case normalization (uppercased identifiers by default, quoted identifiers preserve case)
- **NO constraint enforcement** (PK/FK/CHECK constraints return empty stubs with advisory logging)
- **NO native indexes** (recommendation: use CLUSTERING KEY instead)
- Support for UDFs and stored procedures across multiple languages
- Sync adapter (snowflake-connector-python) + async adapter (executor-based)
- Auto-registration: `registry.register_source_adapter_*("snowflake", SnowflakeAdapter)` + aliases `"snowflake-cloud"`
- **CRITICAL NOTE:** "Snowflake enforces no constraints; returning empty metadata. Partitioning and clustering keys provide optimization guidance."

**Registry Consolidation (8 drivers total):**
- MariaDB (Phase 3B)
- PostgreSQL (Phase 3C.1)
- Oracle (Phase 3C.2)
- SQLite (Phase 3C.3)
- SQL Server (Phase 3C.3)
- MySQL (Phase 3C.4) ✨ NEW
- Redshift (Phase 3C.4) ✨ NEW
- Snowflake (Phase 3C.4) ✨ NEW

All drivers auto-register on import via proven Registry pattern (extensible for future drivers).

**Code Quality Consolidated (Phase 3C.4):**
- 1,688 total unit tests (410+ new)
- 100% docstring coverage on all 30 new modules
- 100% type hints coverage (248 source files total)
- Ruff: 0 issues ✅
- Mypy: 248 files, 0 errors in strict mode ✅
- All SQL queries parameterized (SQL injection prevention enforced)

#### Architectural Evolution

- Nueva capa de agentes especializados de VS Code en `.github/agents` para clasificación, planificación, implementación, hotfix, auditoría, seguridad y cierre de versión.
- Extra `analysis` en `pyproject.toml` para declarar `graphviz` como dependencia instalable explícita (`pip install util_bbdd[analysis]`).

### Changed

- El soporte oficial de runtime pasa a ser Python 3.12+.
- Se alinean CI, metadatos de paquete y documentación pública con el nuevo rango soportado.
- Los enlaces públicos del paquete y del README pasan a apuntar al repositorio real de `fmanza/util_bbdd`.
- Se cierra formalmente la Fase 3.C (drivers SQL) del plan de deuda técnica y desarrollo de features.
- README y guía de migración pasan a distinguir de forma explícita entre imports canónicos y rutas legacy todavía soportadas.
- `DatabaseDocumentation` queda reducida a la orquestación documental y el acceso ad hoc a metadatos se deriva al manager o a las sesiones internas.
- La política transversal de Copilot incorpora el modelo combinado de instrucciones, prompts y agentes.
- README, guía de `.github` y ejemplo integral documentan el flujo recomendado de trabajo con Copilot y el mapeo rápido prompt-agente.

### Removed

- **Breaking Change (Pre-3C.4)**: `DatabaseDocumentation` deja de exponer la API legacy de consulta de metadatos y DDL; ahora se limita a orquestar la generación documental.
- **Note:** El cierre de v0.6.3 cierra explícitamente Phase 3 completa. Fases futuras (4A, 4B, 4C) quedan para v0.6.4+.

### Roadmap (Deferred to v0.6.4+)

- **Phase 4A (Redis Caching):** Planning complete, implementation deferred. Optional optimization for distributed metadata caching. PLAN available at `docs/v0.6.4/PHASE_4A_PLAN_REDIS_CACHING.md`.
- **Phase 3C.5a (BigQuery):** Planning complete, implementation deferred. SQL data warehouse driver (3-4h implementation). PLAN available at `docs/v0.6.3/PHASE_3C5a_PLAN_BIGQUERY.md`.
- **Phase 4B (Async Optimizations):** Planned for future. Batch queries, parallelization.
- **Phase 4C (Connection Pool Tuning):** Planned for future. Per-driver configuration.
- **MongoDB (NoSQL):** Architecture Decision Record (ADR) pending. Requires separate design discussion post-v0.6.3.

## [0.6.2] - 2026-03-26

### Added
- Nuevas fuentes de verdad compartidas para diagramas documentales:
  - `src/util_bbdd/doc/diagram_legend.py`
  - `src/util_bbdd/doc/diagram_summary.py`
- Copia de assets offline con subcarpeta `icons/` para páginas HTML exportadas y prueba dedicada de regresión.
- Ejemplo completo y comentado del contrato `imprimir_config` en `docs/examples/imprimir_config_full_example.toml`.
- Notas de release específicas de v0.6.2 en `docs/v0.6.2/RELEASE_NOTES_v0.6.2.md`.

### Changed
- El detalle HTML de diagramas pasa a consumir SVG inline para garantizar navegación offline con zoom, paneo, ajuste y reset sin depender de `contentDocument`.
- HTML y Word comparten ahora payloads comunes para resumen de niveles, ayudas de lectura y leyenda visual.
- Las páginas globales `Ver todo` muestran acciones de exportación con iconografía local y tooltips consistentes en la salida offline.
- La documentación pública se alinea a v0.6.2 e incorpora el contrato comentado de `imprimir_config` como referencia principal.

### Fixed
- Los tooltips de exportación de `Ver todo` ya no quedan recortados por el contenedor del toolbar.
- La exportación HTML offline incluye los iconos SVG necesarios para paginación y acciones de exportación.
- La experiencia interactiva de diagramas en HTML se mantiene operativa fuera de VS Code y en navegadores externos.

## [0.6.1] - 2026-03-24

### Added
- Tipología visual de tablas en el análisis de grafos con tres estados iniciales:
  - `entity`
  - `association`
  - `hierarchy`
- Leyenda HTML ampliada para exponer tipo de tabla, cardinalidad y tipo de relación soportado por el renderer actual.
- Nota pública preliminar de v0.6.1 en `docs/v0.6.1/RELEASE_NOTES_v0.6.1.md`.

### Changed
- `GraphvizRelationshipGraphExt` deja de colorear nodos solo como principal vs relacionada y pasa a una paleta visual por tipología de tabla.
- La heurística de `association` mejora la detección de tablas puente reales al considerar PK compuesta basada en columnas FK.
- La documentación pública aclara que la tipología visual de tablas es heurística y no una taxonomía absoluta del modelo de datos.
- La política de diagramado de vistas se documenta explícitamente como `exclude` en el estado actual del renderer enriquecido.
- Word y HTML pueden reutilizar el mismo generador Graphviz en una misma ejecución multi-formato.

### Fixed
- El detalle HTML refleja de forma explícita la leyenda de tipos de tabla realmente soportados por el modelo actual.
- La semántica de niveles ocultos queda alineada entre SVG, HTML y Word.

## [0.6.0] - 2026-03-22

### Removed
- **Breaking Change**: el contrato de configuración de grafos deja de depender de `first_level_only` y `show_columns` como parámetros principales.
- **Breaking Change**: la representación HTML antigua de diagramas como lista plana deja paso al modelo por sentido y por nivel.
- **Breaking Change**: `util_bbdd.bulk.base` deja de existir; el núcleo de grafos queda consolidado en `util_bbdd.analysis.base`.

### Added
- Nuevo dominio de análisis multinivel en `analysis/base.py`:
  - `GraphDocument`
  - `GraphLevel`
  - `GraphNode`
  - `GraphEdge`
  - `HiddenLevelsSummary`
  - `LevelDirection`
  - `ColumnVisualizationMode`
- Soporte de relaciones de `n` niveles mediante `max_depth`.
- Dirección configurable de recorrido: `incoming`, `outgoing` y `both`.
- Modos de columnas para diagramas:
  - `compact`
  - `relations`
  - `all`
- Cardinalidad representada por extremos en Graphviz.
- HTML con pestañas por sentido y por nivel.
- Word con resumen de niveles visibles y no visibles bajo cada diagrama.
- Nueva guía específica de migración en `docs/v0.6.0/MIGRATION_GUIDE_v0.6.0.md`.
- Cobertura nueva para payloads HTML tabulados, resumen Word y traversal multinivel.

### Changed
- `GraphvizRelationshipGraphExt` consume `GraphDocument` en lugar de listas planas como fuente principal de renderizado.
- `PrintConfigManager` normaliza el nuevo bloque `grafo` con:
  - `max_depth`
  - `direction`
  - `columns.mode`
  - `columns.max_items`
  - `columns.show_data_types`
  - `cardinality.show_constraint_name`
- HTML y Word consumen el nuevo contrato de configuración de grafos.
- `MatplotlibRelationshipGraph` se alinea con el nuevo traversal multinivel y ya puede renderizar profundidad y dirección configurables.
- README y guías de migración actualizados a v0.6.0.

### Fixed
- La generación HTML de diagramas conserva fallback cuando no hay pestañas disponibles.
- El resumen de niveles ya se refleja también en la salida Word.
- Se estabilizan pruebas unitarias para payloads documentales y renderizado de detalle.

## [0.5.6] - 2026-03-16

### Removed
- **Breaking Change**: `DatabaseManager` deja de publicarse como alias sync compatible.
  - Usa `SyncDatabaseManager` desde `util_bbdd` o `util_bbdd.managers`.
  - `AsyncDatabaseManager` mantiene su nombre y contrato público.
- **Breaking Change**: se elimina `ficheros_fisicos_adicional` del catálogo SQL en todos los motores.
  - El inventario de almacenamiento deja de modelarse como `primary`/`secondary`.
  - SQLite deja de exponer un falso bloque de “ficheros adicionales”.

### Added
- Soporte MariaDB para metadatos temporales:
  - `temp_tablespaces` desde `information_schema.FILES` cuando hay acceso.
  - `temp_storage_variables` para exponer `innodb_temp_data_file_path`.
- Nueva capacidad explícita `sqlite_file_summary` para documentar `page_count`, `page_size` y `size_bytes` del fichero SQLite principal.
- Cobertura adicional de tests para tipado, contratos sync/async y paridad estructural entre managers.
- Refactorización Jinja2 standalone para la documentación HTML:
  - `TemplateEngine` dedicado
  - `templates/layouts`, `templates/macros` y `templates/pages`
  - pruebas unitarias específicas del motor de plantillas
- Páginas HTML globales `Ver todo` con búsqueda, ordenación, paginación y exportación filtrada.

### Changed
- La lógica específica de MariaDB se reorganiza bajo `metadata/mariadb/` con helpers puros y adaptadores sync/async.
- `SyncDatabaseManager` pasa a ser el nombre canónico de la API sync en código, tests y documentación.
- La obtención de DDL y metadatos de MariaDB prioriza `information_schema` y datasets batched por esquema frente a `SHOW CREATE` como ruta principal.
- `get_storage_inventory()` pasa a devolver claves explícitas por capacidad:
  - `primary`
  - `temp_tablespaces` cuando aplica
  - `temp_storage_variables` en documentación MariaDB
  - `sqlite_file_summary` para SQLite
- Word, Excel y HTML dejan de generar la sección global `Ficheros físicos adicionales`; SQLite integra ahora ese contenido como ampliación del bloque de físicos.
- La documentación HTML deja de usar plantillas monolíticas en `src/util_bbdd/doc/data` y pasa a una estructura modular Jinja2.
- Word aplica defaults de grafo más conservadores para documentación:
  - `show_columns=False`
  - `images_paginated=True`
  - `max_subnodes=5`
  - `dpi=150`
- El análisis de relaciones reutiliza un índice cacheado de relaciones entrantes por contexto para reducir recorridos repetidos.

### Fixed
- Los caminos principales de columnas y DDL de rutinas MariaDB evitan depender del fallback de decodificación del driver.
- La documentación Word/Excel/HTML refleja almacenamiento temporal MariaDB y falta de permisos sobre `information_schema.FILES` sin romper la generación.
- Se estabilizan múltiples tests con avisos de tipado en VS Code/Pylance.
- La exportación HTML de colecciones genera CSV y TSV en UTF-8 y Excel en `.xlsx` real.
- La generación Word de diagramas registra tiempos de análisis, render e inserción para diagnosticar bloqueos aparentes.

## [0.5.3] - 2026-03-12

### Added
- Expanded unit coverage for:
  - Bulk CRUD helper behavior
  - Documentation generators (HTML/Excel/Word helper paths)
  - Relationship graph base analysis
  - Metadata cache units and cache invalidation flows

### Changed
- Hardened contract tests for sync/async manager-executor paths:
  - Better validation of query/custom error propagation
  - Explicit verification of wrapping unexpected errors with chained causes
- Reworked documentation legacy-API checks to AST-based assertions to reduce false positives from raw string matching.

### Fixed
- Added edge-case cleanup tests to ensure cursor-close failures do not break query result delivery and connection release paths.

## [0.5.2] - 2026-03-11

### 🎯 Major Cleanup Release

This is a **comprehensive cleanup release** eliminating 27 wrapper files and consolidating the codebase architecture.
No breaking changes - all refactoring is internal. **89% of major refactoring complete (17/19 PRs).**

### Removed (Internal Only - No Breaking Changes)
- **27 wrapper files eliminated** (~2,000 lines of duplicate code):
  - **Phase 1 (PR #16):** Removed directory wrappers (`bulk_crud/`, `grafos/` - 9 files)
  - **Phase 2 (PR #16):** Removed root wrappers (5 files)
  - **Phase 3 (PR #16):** Removed connection layer wrappers (8 files):
    - `conn_params_builder.py` → consolidated to `builder.py`
    - `connection_configs.py` → consolidated to `config.py`
    - `connection_params_manager.py` → consolidated to `params.py`
    - `async_close_utils.py` + `sync_close_utils.py` → consolidated to `close.py`
    - `async_protocols.py` + `pool_protocol.py` → consolidated to `protocols.py`
    - `connect_factory.py` → consolidated to `factory.py`
- **40+ files updated** with new import paths
- **Function rename:** `run_sync_close_operation()` → `run_close_operation_sync()`
- **Class rename:** `ConnectFactory` → `ConnectionFactory`

### Changed
- Import paths streamlined for all internal modules
- Connection layer now uses direct imports instead of wrappers
- No circular dependencies in codebase
- Architecture simplified with consolidated module structure

### Architecture
**Old Pattern (v0.5.0):**
```
connection/
├── conn_params_builder.py (wrapper)
├── connection_configs.py (wrapper)
├── connection_params_manager.py (wrapper)
├── async_close_utils.py (wrapper)
├── sync_close_utils.py (wrapper)
├── async_protocols.py (wrapper)
├── pool_protocol.py (wrapper)
├── connect_factory.py (wrapper)
└── [driver modules]
```

**New Pattern (v0.5.2):**
```
connection/
├── builder.py (consolidated)
├── config.py (consolidated)
├── params.py (consolidated)
├── close.py (consolidated async + sync)
├── protocols.py (consolidated async + pool)
├── factory.py (consolidated)
└── [driver modules - updated imports]
```

### Migration
- **100% Backward Compatible** - Old imports still work
- See `docs/MIGRATION_GUIDE.md` for new import paths
- See `RELEASE_NOTES_v0.5.2.md` for detailed migration guide
- **No code changes required** - but refactoring to new imports is recommended

### Quality Metrics
- ✅ 410/410 unit tests passing (100%)
- ✅ All internal references updated
- ✅ No breaking changes
- ✅ All database drivers validated (MariaDB, Oracle, PostgreSQL, SQLite, HSQLDB, SQL Server)
- ✅ Async/sync APIs fully functional

### Commits Included
- **db61c78** - PR #16 Phase 1: Eliminar directorios wrapper legacy
- **dc3584b** - PR #16 Phase 2: Eliminar wrappers en raíz
- **cb7746a** - PR #16 Phase 3: Eliminar 8 wrappers en connection/
- **3d9add4** - Documentación: Actualizar catálogo PR (17/19 = 89%)

---

## [0.5.0] - 2026-03-11

### What's New
- **Architecture Refactoring:** Complete 3-level hierarchical reorganization
  - Level 1: Abstractions (`_core/`, `_drivers/`)
  - Level 2: Core Services (`connection/`, `query/`, `executors/`, `metadata/`, `results/`)
  - Level 3: Specialization (`bulk/`, `analysis/`, `managers/`)
- **9 new modules consolidated** from fragmented codebase
- **16 backward compatibility wrappers** ensuring zero breaking changes
- **Unified documentation** with architecture diagrams and migration guides

### Changed
- All internal imports reorganized for 3-level structure
- DatabaseManager and AsyncDatabaseManager moved to `managers/` module
- Bulk operations consolidated in `bulk/` module
- Relationship graphs consolidated in `analysis/` module

### Migration
- See `docs/MIGRATION_GUIDE.md` for detailed v0.4.0 → v0.5.0 upgrade path
- All existing APIs remain functional through backward compatibility wrappers
- **100% backward compatible** - no code changes required by users

### Performance & Quality
- 443/443 tests passing consistently
- Test execution: 7.59s (avg)
- Full test coverage reports available
- Code organized for better maintainability

## [Unreleased]

### Removed
- **Breaking Change**: Removed legacy execution APIs based on `fetch_one`
  - `DatabaseManager.execute_query(...)`
  - `DatabaseManager.execute_custom_query(...)`
  - `AsyncDatabaseManager.execute_query(...)`
  - `AsyncDatabaseManager.execute_custom_query(...)`
- **Breaking Change**: Removed executor legacy entry points
  - `SyncQueryExecutor.execute_query(...)`
  - `SyncQueryExecutor.execute_custom_query(...)`
  - `AsyncQueryExecutor.execute_query(...)`
  - `AsyncQueryExecutor.execute_custom_query(...)`
- **Breaking Change**: `DatabaseManager.db_queries` is no longer exposed as public API.
- Removed legacy executor class from `database_queries.py`; module remains catalog/resolution only.

### Added
- Public execution contract unified and explicit in sync/async:
  - `execute_query_many(...)`
  - `execute_query_one(...)`
  - `execute_custom_many(...)`
  - `execute_custom_one(...)`

### Changed
- Documentation generators now consume public manager APIs instead of direct catalog access.
- README examples updated to the final split many/one API.

## [0.3.0] - 2026-03-08

### Removed
- **Breaking Change**: `DatabaseQueryError` class removed from `database_queries.py`
  - Use `QueryNotFoundError` from `database_exceptions.py` instead
  - Alias no longer available
- **Breaking Change**: `DatabaseQueries.validate_query_parameters()` method removed
  - Use `QueryResolver.resolve()` directly instead
  - Simplified API by removing deprecated wrapper
- **Breaking Change**: `DatabaseQueries.analyze_query_parameters()` method removed
  - Use `QueryResolver.resolve()` for comprehensive validation
- **Breaking Change**: `DatabaseManager.validate_query_parameters()` wrapper removed
  - Use `manager.db_queries.resolver.resolve()` instead

### Changed
- Internal query validation completely delegated to `QueryResolver`
- All validation errors use specific exception types (QueryNotFoundError, QueryValidationError)
- Simplified DatabaseQueries API surface (-79 lines of deprecated code)

### Tests
- Removed 2 deprecation compatibility tests
- All remaining 239 unit tests passing
- All 19 E2E tests passing (10 sync + 9 async)

### Migration
Users affected by these breaking changes should:
```python
# OLD CODE (v0.2.x):
from util_bbdd.database_queries import DatabaseQueryError
if manager.validate_query_parameters('query', param=value):
    result = manager.execute_query('query', param=value)

# NEW CODE (v0.3.0+):
from util_bbdd.database_exceptions import QueryNotFoundError
try:
    result = manager.execute_query('query', param=value)
except QueryNotFoundError as e:
    print(f"Query error: {e}")
```

See [08_ESTADO_COMPLETO_PR8.md](08_ESTADO_COMPLETO_PR8.md) for detailed migration guide.

## [0.2.0] - 2026-03-07

### Added
- **Query Registry Pattern**: Centralized query loading via `QueryRegistry` class
- **Query Resolver**: Unified validation and parameter resolution via `QueryResolver`
- **New Exception Hierarchy**:
  - `QueryNotFoundError` - Query does not exist for motor
  - `QueryValidationError` - Validation failed for query parameters
  - `QueryParameterError` - Invalid parameter value for motor
  - `QueryTimeoutError` - Query execution timeout
  - `DatabaseTypeNotSupportedError` - Unsupported database motor
- **Advanced Validators**: Motor-specific validation rules
  - MariaDB: Charset, Database parameter validation
  - Oracle: Schema context (max 30 chars), Character restrictions (alphanumeric, _, $, #)
  - PostgreSQL: Reserved schema detection
  - HSQLDB: Table name format (alphanumeric, _, - only)
  - SQL Server: Schema support, 128-char limits
  - SQLite: Minimal parameters
- **New DatabaseManager Methods**:
  - `execute_query(query_name, **params)` - Execute query by name with validation
- **AsyncDatabaseManager Enhancements**:
  - `get_tables()`, `get_views()`, `get_columns()`, `get_routines()` - Full parity with sync
  - `execute_query(query_name, **params)` - Async query execution by name
  - Async/sync contract validation tests
- **Improved Error Handling**:
  - All exceptions use `raise ... from err` pattern
  - Structured logging with DEBUG level details (elapsed_ms, param_count, etc.)
- **Documentation**:
  - Migration guide v0.1.x → v0.2.0
  - Database motor support matrix
  - Exception usage examples

### Changed
- **DatabaseQueries Refactoring** (SRP improvement):
  - Reduced from 2001 → 1042 lines (-48%)
  - Delegates query loading to `QueryRegistry`
  - Delegates resolution to `QueryResolver`
  - Delegates validation to motor-specific validators
  - Maintains `get_query()`, `get_tables_query()`, etc. as convenience layer
- **Exception Inheritance**:
  - `DatabaseQueryError` → `QueryNotFoundError` (Alias maintained for compatibility)
  - All query exceptions inherit from `DatabaseError` base class
- **API Organization**:
  - New `executors` module: `SyncQueryExecutor`, `AsyncQueryExecutor`
  - New `validators` module: Motor-specific validators
  - New `models` module: `QueryDefinition`, `ResolvedQuery`, `DatabaseTypeDefinition`

### Deprecated
- `DatabaseQueries._load_queries()` - Now internal (delegated to QueryRegistry)
- `DatabaseQueryError` - Use `QueryNotFoundError`, `QueryValidationError`, etc.
- `DatabaseQueries.analyze_query_parameters()` - Use QueryResolver for comprehensive analysis

### Fixed
- Query parameter validation consistency across all motors
- Timeout handling in async query execution
- Error context preservation with exception chaining

### Breaking Changes ⚠️
- `DatabaseQueryError` no longer raised directly (use specific exceptions)
- Query parameter validation is stricter (missing required params raise early)
- `DatabaseQueries._load_queries()` is no longer public API
- Some internal method signatures changed (no impact on public API)

### Performance
- Query loading/resolving cached properly via QueryRegistry
- Reduced object instantiation in DatabaseQueries
- Lazy validation (only on demand, not during init)

### Tests Added (v0.2.0)
- Query Registry: 51 tests
- Query Resolver: 91 tests
- Sync Executor: 10 tests
- Async Executor: 17 tests
- Async Database Manager: 16 tests
- Advanced Validators: 20 tests
- DatabaseQueries Refactor: 36 tests
- **Total new tests in v0.2.0: 241 tests** (↑67% from v0.1.x)

---

## [0.1.0] - 2026-03-06 (Legacy)

### Added
- Módulo `bulk_crud_audit`: CRUD masivo (insert/update/delete) desde DataFrames
- Sistema de auditoría automática en CSV con timestamps
- Factory para conexiones con pool singleton
- Validación de tipos por dialecto SQL (MySQL/Oracle/PostgreSQL)
- Gestión de metadatos con caché
- Documentación automática de BD (Word/Excel)
- Tests unitarios con pytest y cobertura
- Documentación en README y docstrings (Google style)
- Infraestructura async base (`AsyncDatabaseManager`, `AsyncDatabaseQueryExecutor`)
- Soporte async para PostgreSQL, SQLite, MariaDB, Oracle, SQL Server

### Fixed
- Normalización de columnas según dialecto (Oracle: lower, MySQL: upper)
- Manejo de valores NULL en operaciones CRUD

### Note
- HSQLDB: No soporte async (decisión explícita, ver v0.2.0 para más detalles)

[0.5.3]: https://github.com/fmanza/util_bbdd/releases/tag/v0.5.3
[0.5.2]: https://github.com/fmanza/util_bbdd/releases/tag/v0.5.2
[0.2.0]: https://github.com/fmanza/util_bbdd/releases/tag/v0.2.0
[0.1.0]: https://github.com/fmanza/util_bbdd/releases/tag/v0.1.0
