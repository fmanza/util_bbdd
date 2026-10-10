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

## Fuera de alcance (registrado)

- `SyncDatabaseManager.__init__` documenta `ConnectionError` si falla la conexión inicial, pero con pool (lo habitual)
  el fallo llega como `DatabaseConfigurationError` («pool initialization incomplete after 30 sec»). Documentado tal
  cual; unificar la excepción sería un cambio de contrato (decisión del usuario).
- El docstring de la clase y de `__init__` omite MySQL en la lista de motores y nombra `DatabaseValidationError` /
  `DatabaseDriverError`, que no existen (son `ValidationError` / `DriverError`). Es `src/`: no se toca en esta sesión.
- `DiffReportGenerationError` está en la API pública (`util_bbdd.exceptions`, `util_bbdd.comparar`) pero ningún código
  la lanza. Candidata a usarse en `render_all` o a retirarse en 2.0.
- El docstring de `QueryParameterValidator` lista 6 subclases (falta `MySQLValidator`).
