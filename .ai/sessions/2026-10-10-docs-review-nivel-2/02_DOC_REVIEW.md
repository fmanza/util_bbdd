# Revisión de la documentación — nivel 2 (D2)

## Método

El de `../2026-10-10-api-1-0-final/02_DOC_REVIEW.md` y `../2026-10-10-plan-pendientes-post-1-0/02_DOC_REVIEW.md`,
concretado en `PLAN_AUDIT_PLAN.md` §4. Comprobador: `tools/doc_check.py` (sigue las inclusiones `--8<--` de los
ejemplos) con lista de excepciones `tools/doc_check_allow.txt`. Logs: `build/logs/docsn2_*`.

## C1 — consolidación de `api/managers_sync_technical.md` (D1)

| Hallazgo | Dónde | Corrección |
|---|---|---|
| API pública inventada: `introspect()` → `DatabaseSchema`, `execute(query)`, `__init__(db_type, credenciales, pool_config?)`, `pool_config={"min_size", "max_size"}`, `host`/`port`… como parámetros del constructor | `api/managers_sync_technical.md` | Página borrada y fuera del `nav`; su única parte útil (componentes internos) pasa, verificada, a §3 de `api/managers_sync.md` |
| `db_type` sin `mysql` | `api/managers_sync.md` | Lista de `get_supported_db_types()` (7 motores) |
| «`conn_params` debe incluir `database`» | `api/managers_sync.md` | Obligatorios por motor según `DatabaseTypeValidator.get_required_params` (Oracle: `user`, `password`; HSQLDB: `user`, `jdbc_url`, `jdbc_jar`) |
| Tabla de errores incompleta: sin `InvalidDatabaseType` ni `DatabaseConfigurationError`; «`ConnectionError` si no se puede conectar» | `api/managers_sync.md` | Probado: `db_type="foo"` → `InvalidDatabaseType`; falta de parámetros → `ValidationError`; PostgreSQL inalcanzable con pool → `DatabaseConfigurationError` (tras el timeout del pool, 30 s); `ConnectionError` solo en conexión única |
| Faltaban `execute_query_one`, `init`, `get_connection`/`release_connection`, `clear_cache`, `queries_file`; `ValueError` de `get_storage_inventory` sin `tablespace` en Oracle/PostgreSQL | `api/managers_sync.md` | Añadidos con su firma (`inspect.signature`) |

## C2 — consolidación de `functional/managers_sync_session_lifecycle.md` (D2, aprobada)

| Hallazgo | Dónde | Corrección |
|---|---|---|
| Afirmaciones falsas: «no valida credenciales al inicializar» (con pool, `_init_pool` pide y devuelve una conexión de prueba en `__init__`), «no paraleliza; usa una cola de espera» (hay pool), «timeout de reconexión»; lo demás repetía `managers_sync.md` | `functional/managers_sync_session_lifecycle.md` | Borrada y fuera del `nav` (sin enlaces entrantes); sus tres puntos verdaderos (una instancia = un motor; `execute_*` sin caché; sin transacciones entre BD) pasan a `managers_sync.md` |
| Motores sin MySQL (3 sitios); «seis soportados»; «`database` obligatorio en todos los motores»; `pyodbc` como driver de SQL Server (por defecto es `pymssql`); Instant Client «si se usa conexión nativa» (solo en modo thick); instalación con la forma de PyPI | `functional/managers_sync.md` | 7 motores; obligatorios por motor; drivers según `DriverValidator`; instalación desde git |

## Tanda 1 — `docs/api/` (25 páginas)

Comprobador: `build/logs/docsn2_t1_doc_check_{before,after}.txt` (0 hallazgos). Build: `docsn2_t1_build.txt`. Ejemplos
ejecutados en el scratchpad (SQLite): `prefetch` de `analysis.md`, auditoría de `audit.md` (`BulkCrud` + `dump` con
`JsonLinesAuditSink`), `ConnectionFactory` sync/async, `CatalogSource.from_engine`, el nuevo de `normalize.md`.

| Hallazgo | Dónde | Corrección |
|---|---|---|
| Método inexistente `create_sync_connection` (es `create_connection(db_type, conn_params, db_validator=None, sql_server_driver="pymssql", found_rows=False)`); sin `InvalidDatabaseType`; «ejemplo en preparación» | `connection_factory.md` | Firma real, errores probados, ejemplo sync/async ejecutado |
| Clase base `DatabaseTypeValidator` (renombrada a `QueryParameterValidator` el 2026-09-22; el nombre viejo es otra clase de `_drivers`); faltaba `MySQLValidator`; `KeyError` | `validators_system.md` | Renombrado, nota de desambiguación, `MySQLValidator`, `ValueError` real |
| `normalize_sql_literal(value, sql_type) → str` (es `(value)` y devuelve el valor nativo); «bytes → bytes» (los UTF-8 se decodifican a `str`); no decía que recorta cadenas; tabla que mezclaba normalización de valores con inferencia de tipos | `normalize.md` | Reescrita con tablas medidas (valor → salida; dtype → tipo SQLAlchemy) y ejemplo ejecutado |
| Árbol de excepciones: `DatabaseConfigurationError` bajo `DatabaseOperationError` (son hermanas), «otras subclases de pool» inexistentes; `AuditError` «también desde `util_bbdd`» (no desde 1.0) | `exceptions.md` | Árbol generado desde el módulo |
| Motores sin MySQL | `managers.md` (sync y async) | 7 / 6 motores |
| `close_mode` `"drain"` (no existe); «`release_*` / `close_async_resources` no lanzan» (`close_async_resources` acumula y lanza `DatabaseOperationError`); parámetros no marcados como solo por nombre | `managers_lifecycle.md` | Contra `_manager_lifecycle.py` y `normalize_close_mode` |
| `skip_without_relations` (es `skip_tables_without_relations`); sin `graphviz` → «`DocumentationRenderError`» (es `ImportError` al instanciar); «los parámetros son posicionales» (`kinds` es solo por nombre); cifra 75,7 → 6,2 s sin fuente | `analysis.md` | Firmas reales; fuente: sesión `2026-10-09k-doc-architecture-audit` / CHANGELOG 0.41.0 |
| `DumpConfig` «inmutable» (no es `frozen`); faltaban `collect_row_counts`, `commit_every_n_chunks`, `audit_sink`, `DumpResult.audit_run_id`; «no abre conexiones hasta `run()`» (el `Inspector` conecta en el constructor: probado); sin `DumpError` ni `DumpConstraintError` | `dump.md`, `dump_autodoc.md` | Corregido; errores probados con un engine que no conecta |
| `DumpReporter` «crea `output_dir` al inicializar» (lo crea `generate`); hoja 1 sin «Filas Rechazadas» ni la sección de constraints; hoja 4 sin tabla/dialect; error de escritura genérico (es `DumpReportError`) | `dump_reporter.md` | Contra `reporters.py` |
| Dialectos SQL «mssql, hsqldb» (son `generic`, `sqlserver`… 7 en `SUPPORTED_DIALECTS`); `DiffReportGenerationError` documentada pero nunca lanzada; campos de modelos incompletos | `reporters.md`, `schema_comparator.md` | Corregido; comportamiento real de `render_all` |
| Alias legacy `bulk_crud` «sigue disponible» (no existe) | `bulk.md` | Retirado |
| Firmas incompletas: `ParallelBulkLoader` (`audit_sink`, `audit_run_id`, `load(partition_ranges)`), `ParallelLoadResult` (`elapsed_seconds`, `audit_run_id`, `rows_per_second`), `override_identity` descrito al revés («pasar por alto la IDENTITY»: es `OVERRIDING SYSTEM VALUE` en PostgreSQL) | `bulk_parallel.md` | Contra `inspect` y docstrings |
| `AuditManager` sin `warn_if_disabled`; «desde la sesión 2026-10-02c» | `bulk_audit.md`, `exceptions.md` | Firma real; «desde v0.29.0» |
| `create_sync_connection`, `SyncQueryExecutor` sin `resolver`, `AsyncQueryExecutor` sin `execute_query_one`; `QueryResolver(registry?, db_type?)` (`db_type` solo por nombre); campos de `QueryDefinition`/`ResolvedQuery` incompletos; JSON empaquetado vacío sin avisar | `query_execution.md`, `query_system.md` | Contra `inspect`; aviso de `QueryNotFoundError` sin `queries_file` |
| Diagrama con `MySQLOptimalConfig.suggest` llamado por el validador (no lo llama) y permisos sobre `INFORMATION_SCHEMA` (usa `SHOW VARIABLES`); faltaban `log_summary`, `format_bytes`, la ruta de import | `mysql_variables.md` | Contra `connection/mariadb/_variables.py` |
| Diagrama con `inspect`/`get_columns` (usa el snapshot de `metadata/`); «desde la sesión de centralización» | `update_auto_increment.md` | `CatalogSource.snapshot`; «desde v0.31.0» |
| `DbapiCatalogExecutor` sin ruta de import (no está en `util_bbdd.metadata`); cifras sin fuente citada; enlace a ADR-003 apuntando a `architecture.md` | `metadata_manager.md` | Ruta, fuente (`2026-10-03-metadata-centralization`) y enlace al ADR |
| Lista de usos de `maybe_await` incompleta | `async_utils.md` | `grep` |
| `storage/engines.py` (es `doc/infrastructure/storage/engines.py`) | `database_documentation.md` | Ruta real |

Sin cambios tras verificarlas: `audit.md` (ejemplo ejecutado), `comparator.md` (autodoc).

## Tanda 2 — `docs/functional/` (14 páginas tras C2)

Comprobador: `build/logs/docsn2_t2_doc_check_after.txt` (0 hallazgos; estas páginas no tienen código Python). Build:
`docsn2_t2_build.txt`. Probados en el scratchpad: `ParallelBulkLoader(..., disable_constraints=True)` (SQLite),
`AsyncDatabaseManager` sin `init()` (inicialización perezosa) y con `conn_params` incompletos (`ValidationError`),
`AsyncDatabaseManager("hsqldb")` (`NotImplementedError`).

| Hallazgo | Dónde | Corrección |
|---|---|---|
| Patrón de `maintenance_scope` que no funciona: envolver `loader.load(...)` en el `maintenance_scope` de otra `BulkCrud` (en MySQL/MariaDB `FOREIGN_KEY_CHECKS` es de sesión y los workers usan sus conexiones); motores sin Oracle ni SQLite; «no apto para < 100K filas» sin fuente | `bulk_parallel_loading.md` | `ParallelBulkLoader(disable_constraints=True)` (ejecutado), motores según el docstring, remisión a benchmarks |
| «HSQLDB: el gestor usa estrategia síncrona transparente» y «cae a conexión directa si no hay pool async» (falla con `NotImplementedError`; los 6 motores async tienen pool); «inicialización obligatoria» y a la vez «perezosa»; Python 3.10+; «hasta reiniciar el gestor» (`clear_cache()`) | `managers_async.md` | Probado y corregido |
| «Los gestores async caen a conexión directa sync» | `drivers_selection.md` | `NotImplementedError`, sin caída |
| «Normalización de identificadores por motor… usar el case incorrecto provoca errores» (desde PD-01 las columnas se emparejan sin distinguir mayúsculas); «no soporta UPSERT nativo en todos los motores» (no hay UPSERT en ningún motor) | `bulk_operations.md` | `align_dataframe_columns`; UPSERT inexistente |
| Motores de constraints y de resincronización de PK sin MySQL; sin los motores de `manage_indexes`; «rehabilitación garantizada» (un fallo general al reactivar solo se registra) | `dump_data_export.md` (y `api/dump.md`: `DumpConstraintError` solo al desactivar) | Contra `_constraints.py`, `pk_sync.py`, `_indexes.py` |
| «El resolvedor decide si bloquear o continuar» con `(False, avisos)` (bloquea con `QueryValidationError`); «no se comparte lógica entre motores» (clase base común, MySQL hereda de MariaDB); «Oracle requiere `schema`» (lo valida si viene) | `query_registry.md`, `validators_pattern.md` | Contra `resolver.py` y los validadores |
| «Rutinas: activarlas puede multiplicar las consultas» (una consulta por lado, ADR-003) | `schema_comparison.md` | Corregido |
| Motores sin MySQL | `query_execution.md`, `database_documentation.md`, `validators_pattern.md` | 7 motores |
| «Sesión 2026-10-02c» | `bulk_audit.md` | v0.29.0 |

Sin cambios tras verificarlas: `audit.md` (test de formato congelado `tests/unit/audit/test_legacy_format.py`; vista
previa de 120 caracteres), `metadata_extraction.md`.

## Tanda 3 — `docs/examples/` (17 páginas, todos los ejemplos ejecutados)

Comprobador: `build/logs/docsn2_t3_doc_check_after.txt` (21 inclusiones `.py`, 38 imports, 38 accesos; 0 hallazgos).
Build: `docsn2_t3_build.txt`. Ejecuciones: `docsn2_t3_sqlite_runs.txt` (9 con SQLite) y `docsn2_t3_bench_runs.txt`
(banco). Con el banco (D5): tablas `docsn2_clientes`/`docsn2_pedidos` + vista `docsn2_v_pedidos` en MariaDB, Oracle,
PostgreSQL y SQL Server, `docsn2_ai` en MariaDB/MySQL y `docsn2_usuarios` en PostgreSQL; borradas al terminar
(comprobado: 0 restos). Los `migrate_*` planificaron 2 tablas + 1 vista cada uno (los schemas del banco estaban vacíos:
sin las tablas temporales no se probaba nada).

**Fallo de la librería encontrado** (el usuario eligió `/hotfix` aparte): `DatabaseDocumentation.generate()` sin
`fichero_salida` sobre SQLite `:memory:` → `OSError` WinError 123 en Windows. Hotfix `ae1e8098`
(sesión `2026-10-11-hotfix-doc-auto-filename`); el fragmento de la página funciona después.

| Hallazgo | Dónde | Corrección |
|---|---|---|
| `QueryRegistry.register(...)` no existe (el ejemplo fallaba con `AttributeError`) | `query_execution_example.py` | `QueryRegistry(queries_file)` con un JSON temporal; ejecutado |
| `bulk_insert_from_df` sin `generar_sql=False` (desde 1.0 exige `path_sql`: `ValueError`) | `parallel_bulk_insert.py`, `bulk_insert_csv.py` | `generar_sql=False`; ejecutados |
| `audit_csv_path` como **directorio**, ficheros `audit_insert_*.csv` inventados, CSV leído con coma (es tabulado y con coma decimal); captura de `ValidationError` que el código no tenía; «normalización de identificadores por motor» | `bulk_insert_csv.py` / `.md` | Reescrito: fichero CSV, `AuditManager.leer_auditoria()`, crea la tabla; ejecutado contra PostgreSQL |
| Mocks que responden en orden fijo a un `frozenset` (valores cruzados: `max_allowed_packet` = 1024 MB) y se agotan en `validate()` (`StopIteration`, tragado por un `try/except` con código 0); logs de `BulkCrud` inventados; imports privados; «v0.10.0+»; «requiere `INFORMATION_SCHEMA`»; umbral `dev()` < 50K (es ≤ 100K) | `mysql_variables_example.py` / `.md` | Reescrito: mock por nombre de variable, imports de `util_bbdd.connection.mariadb`, ejemplo 6 real con `UTIL_BBDD_EXAMPLE_URL` (probado en MariaDB del banco: «ENGINE READINESS REPORT») |
| Tiempos «simulados» impresos (~100 ms / ~400 ms); `PoolExhaustedError` (ningún código la lanza: con el pool lleno se espera); `pool_size` en SQLite (el pool async de SQLite es una conexión con semáforo: `gather()` no paraleliza); «inicialización obligatoria» | `async_concurrent_queries.py` / `.md` | Tiempos medidos (`gather()` y secuencial iguales en SQLite, como se explica) |
| Cifras sin fuente («30 → 8 minutos», «SQLite 1,5×», «PostgreSQL/MySQL 2,5–3,5×») que contradicen los benchmarks; `maintenance_scope` externo envolviendo `loader.load()`; resultado esperado inventado | `parallel_bulk_insert.md` | Cifras de `guides/benchmarks.md` + la medida de esta revisión; `disable_constraints=True`; salida real |
| `FROM table` literal, falta `import text`, último tramo de PK fuera por la división entera; `psycopg2` | `examples/database/partition_ranges.py`, `pool_setup.py` | `RangePartitioner.partition_ranges` (probado: cubre 1–102); `postgresql+psycopg://` |
| `psycopg2` en la URL de origen | `dump_data_export.py` | psycopg 3; ejecutado PostgreSQL → SQL Server (2 tablas `success`, 1 `missing_target`) |
| «`"mysql"` en lugar de `"mariadb"` es un error común» (`mysql` es un motor válido); fila esperada como `dict` (es `tuple`) | `example_connect_introspect.md` | Corregido contra la salida real |
| «Requiere dos BDs accesibles» (usan SQLite en memoria) | `diff_reporters.md`, `schema_comparison.md` | Corregido |
| Destinos sin MySQL; extracción descrita con `INFORMATION_SCHEMA`/`COLUMNPROPERTY`/`pg_index` (desde ADR-003 es el catálogo de `metadata/`); «`VIEW_DEFINITION` truncada» (se usa `OBJECT_DEFINITION`); `number_fallback` sin `DECIMAL(18,4)`; nombre sugerido con fecha (no la lleva) | `migrate_*.md` (4) | Contra `planner.py`, `metadata/*/catalog.py`, `ir/models.py` y los mapas de tipos |
| Carpeta de salida `generated_docs/` (es `generated_docs/<nombre>/`) | `database_documentation_generation.md` | Corregido |

Sin cambios tras ejecutarlos: `exception_handling`, `validators_pattern`, `update_auto_increment_example` (MariaDB y
MySQL del banco; reduce 500 → 8, como avisa la página).

## Tanda 4a — guías de uso (9 páginas)

`api_1_0_migration`, `async_guide`, `connection_guide`, `ddl_migration_guide`, `drivers`, `dump_guide`, `exceptions`,
`troubleshooting`, `onboarding_dev`. Comprobador: `docsn2_t4a_doc_check_after.txt` (0 hallazgos). Build:
`docsn2_t4a_build.txt`. Ejecutado contra el banco: conexión sync PostgreSQL y Oracle (thin), async PostgreSQL con
`gather()` (ejemplos de `connection_guide` y `async_guide`).

| Hallazgo | Dónde | Corrección |
|---|---|---|
| Tabla de pool con `max_overflow`/`pool_recycle` y «throughput aprox.» sin fuente; con PostgreSQL esas claves dan `ValidationError` (probado); `PoolExhaustedError` (nunca se lanza); «`init()` obligatorio»; Python 3.10+; sin Oracle async | `async_guide.md` | Tabla de parámetros por motor desde los `*PoolConfig`; errores reales |
| «Thin mode solo asíncrono» (es el modo por defecto también en sync: conectado en sync al Oracle del banco); matriz de compatibilidad de Instant Client sin fuente verificable; `python-oracledb 1.0+`; «`dsn` no recomendado para 11g» | `drivers.md` | Modos según el código y python-oracledb; matriz retirada (remisión a la de Oracle) |
| «Un fallo de credenciales o red es `SQLAlchemyError`» (es `DatabaseConfigurationError` con pool o `ConnectionError`); `DPY-2014` como «Instant Client no encontrado» (es «parámetro duplicado»; el de Instant Client es `DPI-1047`); «pyodbc requiere `driver_name`» (tiene valor por defecto) | `connection_guide.md` | Corregido |
| Árbol de excepciones duplicado e incompleto; «retry» capturando `ConnectionError` (una consulta fallida llega como `DatabaseOperationError`: probado); `PoolExhaustedError`, `DriverNotFoundError`, `DiffReportGenerationError` como errores habituales (no se lanzan) | `guides/exceptions.md` (y `api/managers_sync.md`: «`QueryError` en `execute_*`» → `DatabaseOperationError`) | Tabla por momento + enlace al árbol de la API; patrón de reintento sobre `DatabaseOperationError` |
| Ejemplo de pool con `max_overflow` en PostgreSQL; `PoolExhaustedError`; `GraphRenderError` (no existe) | `troubleshooting.md` | `pool_timeout`; `PoolTimeoutError` real; `graphviz.ExecutableNotFound` |
| Vistas `ALL_*` inventadas, `TABLE_SCHEMA`, nombre sugerido con fecha, `charset` «solo MariaDB» (también MySQL), código `INDEX_EXPRESSION_SKIPPED` ausente | `ddl_migration_guide.md` | Contra `WarningCode`, `planner.py` e `ir/models.py` |
| «Falta `openpyxl`» como error del informe (es dependencia base; el error real es `DumpReportError`) | `dump_guide.md` | Corregido |
| Mapa del código sin `audit/` ni `exceptions.py`; 5 extras ausentes y contenido de `dev` desfasado; versión esperada `0.10.0`; Conventional Commits incompletos; docstring de ejemplo con una firma de `get_tables` inexistente; verificación con `mkdocs` | `onboarding_dev.md` | Contra `pyproject.toml`, `src/` y `SHARED_INSTRUCTIONS.md` |
| `pip install "util_bbdd[x]"` (forma PyPI) | `connection_guide`, `drivers`, `ddl_migration_guide`, `troubleshooting`, `async_guide` | `git+…@v1.1.0` |

Sin cambios tras verificarla: `api_1_0_migration.md` (13 símbolos de la raíz y todos los nombres de su tabla
importables desde donde dice; cifra de importación con fuente en el CHANGELOG).

## Fuera de alcance (registrado)

- `SyncDatabaseManager.__init__` documenta `ConnectionError` si falla la conexión inicial, pero con pool (lo habitual)
  el fallo llega como `DatabaseConfigurationError` («pool initialization incomplete after 30 sec»). Documentado tal
  cual; unificar la excepción sería un cambio de contrato (decisión del usuario).
- El docstring de la clase y de `__init__` omite MySQL en la lista de motores y nombra `DatabaseValidationError` /
  `DatabaseDriverError`, que no existen (son `ValidationError` / `DriverError`). Es `src/`: no se toca en esta sesión.
- `DiffReportGenerationError` está en la API pública (`util_bbdd.exceptions`, `util_bbdd.comparar`) pero ningún código
  la lanza. Candidata a usarse en `render_all` o a retirarse en 2.0.
- El docstring de `QueryParameterValidator` lista 6 subclases (falta `MySQLValidator`).
- `ConstraintManager.__exit__` registra y no propaga un fallo al reactivar constraints en `dump`: `DumpResult` no lo
  refleja (`constraint_results` vacío). Revisar si debería marcarse en el resultado.
- `PoolExhaustedError` está en la API pública pero ningún código la lanza (igual que `DiffReportGenerationError`).
- `DatabaseDocumentation.generate()`: un fallo al preparar la carpeta de salida llega como `OSError` crudo, no como
  `DocumentationRenderError` (registrado en el hotfix `ae1e8098`).
- Entorno local de esta sesión: `importlib.metadata.version('util_bbdd')` devuelve `0.29.0` (instalación editable de
  entonces); el código se carga de `src/`. Reinstalar con `pip install -e ".[dev,docs]"` para que la verificación de
  `onboarding_dev.md` muestre la versión actual.
