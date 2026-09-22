# PLAN + AUDIT_PLAN — Remediación AUDIT_CODE completo (12 franjas)

Estado: **plan emitido, IMPLEMENT pendiente**. Formato: backlog único (tech_debt) con ítems de
severidad hotfix embebidos. Veredicto AUDIT_PLAN: **GO_CONDICIONAL** (ver decisiones abiertas al
final). Fuente: AUDIT_CODE de 2026-09-22, 12 franjas paralelas sobre el commit `ee077b8`.

## PLAN

**Objetivo.** Remediar todas las condiciones emitidas por las 12 franjas del AUDIT_CODE completo,
excluyendo explícitamente los hallazgos específicos de `metadata/redshift` y `metadata/snowflake`
(decisión de producto aplazada — ver `00_REQUEST.md` § Restricciones).

**Estructura de ejecución.** Cada fila de las tablas P0-P3 es un fix independiente: su propia
rama/commit, sin mezclar módulos no relacionados (Conventional Commits). Los P0 se tratan como
`/hotfix` (RCA→FIX→AUDIT_CODE→VERSION, sin refactor añadido); los P1 mixtos bug+contrato como
`/hotfix` o `/refactor` según si cambian una firma pública; los P2 estructurales como `/refactor`
o `/tech-debt`; los P3 son principalmente tests a añadir, agrupables con el fix que motiva cada uno.

**Prioridad**: P0 (seguridad/corrección bloqueante, veredicto RECHAZADO o exploit confirmado) →
P1 (contrato roto o bug de alto impacto, no bloqueante) → P2 (deuda estructural / código muerto /
inconsistencias) → P3 (tests faltantes consolidados, cosmético).

---

### Tabla P0 — Bloqueantes (implementar primero, cada uno aislado)

| ID | Módulo | Archivo(s) | Problema | Fix propuesto |
|---|---|---|---|---|
| **DOC-01** | doc | `doc/infrastructure/renderers/shared/template_engine.py:48-50` | `select_autoescape(enabled_extensions=("html","xml"))` no reconoce plantillas `*.html.j2`; autoescape nunca se activa. XSS confirmado en vivo (nombre de tabla `<script>alert(1)</script>` se inserta sin escapar). | Añadir `"j2"` a `enabled_extensions` o forzar `autoescape=True`. Añadir test de regresión en `test_template_engine.py` que inyecte payload y verifique escapado. |
| **MEO-01** | metadata | `metadata/oracle/async_adapter.py:98,112,127,141,156` | Métodos nombrados `fetch_*_sync` dentro de la clase async; nunca implementa `SourceAdapterAsync` pese a registrarse como tal → `AttributeError` garantizado en caller polimórfico. El test de "paridad" existente certifica el bug. | Renombrar `fetch_*_sync`→`fetch_*_async`. Corregir `tests/unit/test_oracle_adapter_parity.py:143-146` para que compare contra el Protocol real, no `hasattr(adapter, "fetch_columns_sync")`. Agrupar con MDC-05. |
| **MEO-02** | metadata (seguridad) | `metadata/mariadb/_adapter_helpers.py:16-48` (`build_columns_safe_sql`, `build_view_definition_sql`) | Escapado por duplicado de comillas simples sin escapar backslash → bypass bajo `sql_mode` por defecto. Alcanzable desde `managers/sync_mgr.py:499`. | Sustituir interpolación f-string por bind params reales (`%(schema)s`/`%(table)s`), igual que el resto de queries de mariadb/mysql/oracle. Añadir test con payload `\` + comilla. |
| **SVC-01** | query/executors/factory (seguridad) | `factory/sqlalchemy_engine_factory.py:68` | `logger.debug` loguea el connection string completo (con password) sin redactar; el factory async equivalente sí tiene `_sanitize_conn_str()`, ausente en sync. | Portar `_sanitize_conn_str()` del factory async al sync y usarlo en el log. Test de regresión: capturar log y verificar que no contiene la password. |
| **SVC-02** | query/executors/factory (seguridad) | `query/resolver.py:190-197` (`_interpolate_sql`, usa `.format()`) + `validators/{mariadb,postgresql,sqlite,sqlserver}_validator.py` | Solo 3 de 6 validadores aplican allowlist de caracteres, y **ninguno** valida `tabla`/`rutina`/`tipo_rutina`/`tablespace`. Exploit confirmado contra `mariadb.create_table` y `oracle.create_rutina` (`data/sql_queries.json`). | Aplicar regex de allowlist a todo parámetro que se interpole vía `.format()` en los 6 validadores (`tabla`, `rutina`, `tipo_rutina`, `tablespace`, además de `database`/`schema`/`esquema` ya cubiertos). Tests de inyección (`'; DROP TABLE`, `' OR '1'='1`) por motor. |
| **CNX-01** | connection (seguridad) | `connection/postgresql/pool_connection_postgresql.py:103` | `conninfo` construido por f-string sin URL-encoding; `user`/`password`/`database` con `/`, `#`, `%` corrompen o desvían la conexión. | Usar `urllib.parse.quote` en user/password, o pasar kwargs directamente a `psycopg_pool.ConnectionPool` si la versión lo soporta (igual que `connection_postgresql.py` no-pooled). |
| **CNX-02** | connection (seguridad) | `connection/sqlserver/connection_sqlserver.py:119-127`, `async_connection_sqlserver.py:31-40`, `async_pool_connection_sqlserver.py:44` | DSN ODBC construido por interpolación sin escapar `;`/`{`/`}`; un valor con `;` puede inyectar atributos adicionales (p. ej. `TrustServerCertificate=yes`). Duplicado en sync y async. | Centralizar la construcción del DSN en un único helper que escape `;`/`{`/`}`, usado por las 3 variantes (sync, async, async-pool). |
| **MSS-01** | metadata | `metadata/sqlserver/sync_adapter.py:129` vs `async_adapter.py:154-202` | `fetch_routine_parameters_sync(object_id)` no cumple `RoutineAdapterSync` (exige `schema, routine, routine_type`); el async sí cumple. El test "de paridad" codifica el bug (`test_sqlserver_adapter_parity.py:222-228`). | Alinear la firma sync con el Protocol (reutilizar la resolución de `object_id` que ya hace el async internamente). Corregir el test de paridad para comparar contra el Protocol. Agrupar con MDC-05. |
| **CMP-01** | migrate/_compat | `migrate/_compat/type_map_sqlserver.py:211-212` (`resolve_number_type_sqlserver`) | `NUMBER(1,0)`/`NUMBER(2,0)` de Oracle mapea a `TINYINT` de SQL Server (unsigned 0-255) sin warning; valores negativos reales producen overflow silencioso. Las otras 9 direcciones sí avisan del mismo choque de signo. `test_type_map_sqlserver.py:126-129` certifica `comment is None` como correcto. | Emitir `WARNING`/`ddl_comment` igual que `type_map_mariadb_to_sqlserver.py`. Corregir el test para esperar el warning. Revisar también `_handle_pk_identity` en `oracle_to_sqlserver.py:249-250` (acepta TINYINT para IDENTITY sin aviso). |
| **DOC-02** | doc | `docs_build_plugin.py:30-42` | El ZIP de documentación se crea dentro del propio `site_dir` que recorre con `os.walk`, incluyéndose a sí mismo mientras se escribe (entrada autorreferencial corrupta). | Escribir a un fichero temporal fuera de `site_dir` (o excluir `zip_path.name` explícitamente del `os.walk`) y mover al final. Añadir test mínimo para el plugin (hoy sin cobertura). |

---

### Tabla P1 — Contratos rotos / bugs de alto impacto (no bloqueantes, alta prioridad)

| ID | Módulo | Archivo(s) | Problema | Fix propuesto |
|---|---|---|---|---|
| **FND-01** | foundation | `_drivers/validator.py:393-419` (`validate_db_type`) | Docstring documenta `→ False`; la implementación real nunca retorna `False` (siempre `True` o excepción). | Corregir el docstring/ejemplo para reflejar el comportamiento real (excepción, no `False`). |
| **FND-02** | foundation | `_drivers/driver_validator.py:55-63` vs `_drivers/validator.py:91-110` | Dos validadores del mismo paquete lanzan excepciones distintas (`DriverError` vs `InvalidDatabaseType`) para "db_type desconocido". | Unificar el criterio: ambos deben lanzar `InvalidDatabaseType` (subclase de `ValidationError`) para input inválido. |
| **MDC-01** | metadata núcleo | `metadata/builder.py`, `fetcher.py`, `manager.py` (`DDLBuilder`, `MetadataFetcher`, `MetadataManager`) | Subsistema completo exportado en API pública, desconectado de la ruta de producción real. `MetadataFetcher` lanza `NotImplementedError` incondicional si se instancia. `builder.py:130-148` (`_quote_identifier`) no escapa comillas embebidas (inyección de identificador) y `builder.py:107-111` genera `DEFAULT` sin comillas para valores string (DDL inválido). | **Decisión de producto requerida** (ver AUDIT_PLAN): deprecar y retirar de la API pública, o conectarlo a la ruta real y corregir `_quote_identifier`/`DEFAULT` primero. |
| **MDC-02** | metadata núcleo | `metadata/cache.py:190-193,217-260` (`RelationshipMetadataCache`) | 4 cachés (`_cardinality_cache`, `_is_pk_cache`, `_is_uk_cache`, `_table_columns_typed_cache`) indexadas solo por nombre de tabla, sin schema/contexto → colisión entre esquemas con tabla homónima. | Añadir componente de contexto (schema/db_type) a las 4 cachés, igual que ya hace `DatabaseMetadataCache`. Test de colisión cross-schema. |
| **MEO-03** | metadata | `metadata/mariadb/sync_adapter.py:181,189,200,211,222` + `async_adapter.py` | Firma reducida (`fetch_tables_sync(self)` sin `schema`, resto sin `schema` explícito) frente al Protocol y a los otros 8 motores. | Unificar la firma con `(schema, table)` como el resto de motores, o documentar explícitamente la divergencia y excluir MariaDB del Protocol genérico si es intencional. |
| **MPG-01** | metadata | `metadata/postgresql/sync_adapter.py` / `async_adapter.py` | No implementan `fetch_routine_definition_sync/async` pese al Protocol; el helper que construiría el DDL (`process_routine_result()`, `postgresql/_adapter_helpers.py:69-100`) existe pero nunca se invoca. | Exponer `fetch_routine_definition_sync/async` reutilizando `process_routine_result()`. |
| **MSS-02** | metadata | `metadata/sqlserver/sync_adapter.py` / `async_adapter.py` | No exponen `fetch_routine_definition_sync/async` pese a que `routines.py:108-126` (`fetch_routine_body_sync`) ya implementa la lógica completa. | Exponer los métodos en ambos adaptadores reutilizando `fetch_routine_body_sync`/su equivalente async. |
| **MSS-03** | metadata (seguridad) | `metadata/sqlite/{tables,constraints,indexes,routines}.py` | Interpolan `schema`/`table` crudos en `PRAGMA [...]` sin usar `quote_sqlite_identifier()` (existe y escapa bien) ni los helpers ya escritos en `_adapter_helpers.py` (código muerto, 0 usos). Corchetes no escapan `]` interno. | Sustituir la interpolación cruda por `quote_sqlite_identifier()` o activar los helpers muertos de `_adapter_helpers.py`; eliminar el resto del código muerto. |
| **MGR-01** | managers | `managers/_manager_lifecycle.py:105-168` (sync) vs `:211-223` (`close_async_resources`) | `close()` sync agrega errores de cada recurso y lanza `DatabaseOperationError`; `close()` async no tiene try/except — un fallo real (no timeout) se propaga crudo y el segundo recurso ni se intenta cerrar. | Envolver `close_async_resources` igual que la versión sync (try/except por recurso, agregación, `DatabaseOperationError`). Test: forzar fallo de `pool.close()` en async. |
| **BLK-01** | bulk | `bulk/crud.py:543-564` (`__run_bulk_pipeline`) | Excepción de auditoría (`AuditError`, hereda de `Exception` no de `SQLAlchemyError`/`ValueError`) tras un `execute()` ya comprometido no se captura; dentro de `bulk_session()` provoca rollback de operaciones previas ya confirmadas y auditadas. | Ampliar el `except` para capturar `AuditError`/`OSError` explícitamente. Documentar en el docstring de `bulk_session()` el riesgo si no se amplía. Test: fallo de auditoría a mitad de sesión. |
| **BLK-02** | comparar | `comparar/comparator.py:491-492,558-559` (`_compare_indices`, `_compare_foreign_keys`) + `:336-418` (`_compare_columns_from_raw`) | Índices/FKs se comparan sensibles a mayúsculas (a diferencia de tablas/columnas, que sí normalizan) → falsos positivos "added+removed" cross-motor. Columnas se indexan por nombre, el orden físico nunca se compara → falso negativo en reordenamientos. | Normalizar a minúsculas la comparación de nombres de índice/FK igual que tablas/columnas. Documentar explícitamente que el orden de columnas no se compara (o añadir comparación de orden si se decide corregirlo). |
| **BLK-03** | comparar (seguridad) | `comparar/reporters/sql_reporter.py` (`_render_col_definition:517`, `_render_default_diff:798,803,808`) | Valores `DEFAULT` interpolados sin escapar (a diferencia de comentarios, que sí usan `_escape_sql_string`). Un DEFAULT con comilla simple rompe el SQL generado o inyecta SQL adicional. | Aplicar `_escape_sql_string` (o equivalente) a los valores `DEFAULT` igual que ya se hace con comentarios. Test con valor `O'Brien`. |
| **MIG-01** | migrate | `migrate/ir/models.py:157-166` (`MigrationPlan.execute()`) | No comprueba `self.error_count` antes de ejecutar; una excepción a mitad del bucle de sentencias no se captura, deja el destino en estado indeterminado sin informar qué se ejecutó. | Añadir gate: rechazar ejecución si `error_count > 0` (o exigir flag explícito de override). Capturar excepciones por sentencia, registrar cuáles se ejecutaron antes del fallo. |
| **MIG-02** | migrate | `migrate/emitters/mariadb.py:211-213` (`_emit_column`) | **Decisión de producto, no bug simple** (ver `00_CONTEXT_SNAPSHOT.md` § Hechos previos): el forzado a `INT(11)` para todo `AUTO_INCREMENT` es deliberado (commit `a950d18`), pero no contempla `BIGINT`/`SMALLINT` origen → riesgo real de overflow para PKs grandes migradas desde SQL Server/Oracle/PostgreSQL. | **Requiere confirmación del usuario** antes de tocar: preservar el ancho del tipo origen (`INT`/`BIGINT`/`SMALLINT AUTO_INCREMENT` según corresponda) en vez de fijar siempre `INT(11)`. Actualizar los 3 tests existentes de `a950d18` sin revertir su intención original (evitar que quede un tipo incorrecto sin normalizar), solo ampliar la regla a preservar ancho. |
| **MIG-03** | migrate | `migrate/emitters/{oracle,postgresql,sqlserver,mariadb}.py` (`_format_default_*`) | Cada emisor solo reconoce funciones `DEFAULT` de un dialecto origen "canónico"; `planner.py` reutiliza cada emisor para hasta 3 motores origen. Un `DEFAULT GETDATE()`/`CURDATE()` no coincidente cae al fallback y se entrecomilla como string literal, sin `MigrationWarning`. | Como mínimo, emitir `MigrationWarning` cuando el fallback se activa (hoy es silencioso). Evaluar ampliar el diccionario de funciones reconocidas por emisor a los 3 dialectos origen posibles. |

---

### Tabla P2 — Deuda estructural, código muerto, inconsistencias (no bloqueantes)

| ID | Módulo | Resumen | Archivo(s) principal(es) |
|---|---|---|---|
| **FND-03** | foundation | Código muerto: `DatabaseType`, `OperationType`, `RouterineType` (0 usos), `DatabaseTypeDefinition` sin instanciar, jerarquía `DumpError`/`DumpConstraintError`/`DumpReportError` nunca lanzada en `dump/`. | `_core/constants.py`, `_core/exceptions.py:351-370`, `models.py:46-70` |
| **FND-04** | foundation | `util_bbdd/__init__.py` no exporta `ComparerError`/`DumpError` pese a que sus productores (`SchemaComparator`, `DumpOrchestrator`) sí son API pública. | `src/util_bbdd/__init__.py` |
| **FND-05** | foundation | Dos `ConnectionProvider`/`ConnectionReleaser` incompatibles (alias `Callable` vs `Protocol`) resueltos solo por alias en `_core/__init__.py`. | `_core/types.py:44`, `_core/contracts.py:11` |
| **SVC-03** | servicios | Asimetrías sync/async: escape de `%` mariadb solo en async (`executors`), validación `user`/`database` solo en factory async, rutas SQLite Windows solo normalizadas en async. | `executors/{sync,async}_query_executor.py`, `factory/{sync,async}_sqlalchemy_engine_factory.py` |
| **SVC-04** | servicios | `QueryExecutorBase` es un contrato huérfano (0 subclases reales); `_build_hsqldb_connection_string` en factory async es inalcanzable (HSQLDB async rechazado explícitamente antes). | `executors/base.py`, `factory/async_sqlalchemy_engine_factory.py:294-308` |
| **SVC-05** | servicios | Colisión de nombre: dos clases distintas llamadas `DatabaseTypeValidator` (`validators/base_validator.py` vs `_drivers/validator.py`), superficie de import confusa. | `validators/base_validator.py:11`, `_drivers/validator.py:22` |
| **CNX-03** | connection | `connection/factory.py:159-164` y `params.py:138,156` lanzan `ConnectionError`/`ValueError` en vez de `InvalidDatabaseType`, incumpliendo SHARED_INSTRUCTIONS.md. | `connection/factory.py`, `connection/params.py` |
| **CNX-04** | connection | PostgreSQL async descarta silenciosamente `schema`/`options`/`application_name` que sí aplica la versión sync. | `connection/postgresql/{async_connection,async_pool_connection}_postgresql.py` |
| **CNX-05** | connection | `oracle/pool_connection_oracle.py` importa `oracledb` de forma eager, rompiendo el patrón de import opcional lazy que sí siguen mariadb/postgresql. | `connection/oracle/pool_connection_oracle.py:8` |
| **MDC-03** | metadata núcleo | Registro de routine adapters incompleto: mysql y sqlserver nunca llaman `register_routine_adapter_sync/async` pese a tener la capacidad implementada (redshift excluido de esta ronda). | `metadata/mysql/__init__.py`, `metadata/sqlserver/__init__.py` |
| **MDC-04** | metadata núcleo | `except Exception: pass` en el registro de adapters de mariadb enmascara errores reales de bootstrap (incluido el `ValueError` de doble registro que el registry lanza a propósito). | `metadata/mariadb/__init__.py:47-60` |
| **MDC-05** | metadata núcleo | `test_protocol_conformance.py` solo cubre `MetadataCachePort`; ampliar a `SourceAdapterSync/Async` y `RoutineAdapterSync/Async` para los 9 adaptadores de motor — mitigación estructural que habría detectado MEO-01, MSS-01, MEO-03. **Agrupar con esos fixes.** | `tests/unit/test_protocol_conformance.py` |
| **MEO-04** | metadata | Oracle no normaliza a mayúsculas `schema`/`table` antes de bindear en `:owner`/`:table_name`; con input en minúsculas devuelve 0 filas silenciosamente. | `metadata/oracle/{sync,async}_adapter.py` |
| **MEO-05** | metadata | Columnas `LONG`/`LONG RAW` de Oracle se descartan en silencio sin marcador de "tipo no soportado". | `metadata/oracle/tables.py:99-102` |
| **MEO-06** | metadata | Filtro de schema de sistema por prefijo `"WM"` (no `"WMSYS"` exacto) excluye por error esquemas de usuario que empiecen por `WM`. | `metadata/oracle/common.py:163-166`, `tables.py:25` |
| **MEO-07** | metadata | MySQL sin mapeo de `BIT`; MariaDB no tiene ninguna función `normalize_type` propia (expone `DATA_TYPE` crudo). | `metadata/mysql/common.py:19-92`, `metadata/mariadb/common.py` |
| **MGR-02** | managers | `AsyncLifecycleManager`/`AsyncSessionManager` se construyen en `async_mgr.py` pero ningún método se invoca jamás (código muerto que aparenta funcionar). | `managers/async_mgr.py:256,262,285-286` |
| **MGR-03** | managers | `_metadata_cache.py::clear_context/clear_routine` accede a 14 atributos privados de `DatabaseMetadataCache` por nombre hardcodeado en vez de API pública. **Depende de que `DatabaseMetadataCache` exponga métodos públicos equivalentes** (no existen hoy). | `managers/_metadata_cache.py:72-169` |
| **MGR-04** | analysis | Cachés de `DatabaseRelationshipGraphBase` (`_graph_document_cache_by_context`, etc.) sin ningún método de invalidación; no se enteran de `manager.clear_cache()`. | `analysis/base.py:136-138` |
| **BLK-04** | comparar | `sql_reporter.py` nunca cita identificadores vía `identifier_preparer` (a diferencia de `bulk/_support/sql_helpers.py`/`pk_sync.py`, que sí lo hacen). | `comparar/reporters/sql_reporter.py` |
| **BLK-05** | bulk | `_substitute_ordered_params`/`_substitute_named_params` sustituyen placeholders sobre el string ya parcialmente sustituido; un valor que contenga literalmente `%s`/`?`/`:otro_param` puede corromper el SQL (solo en el fallback BLOB). | `bulk/_support/sql_helpers.py:120-142` |
| **BLK-06** | bulk | `_sync_mssql` interpola `table_ref` sin comillas de identificador, a diferencia de `_sync_mariadb`. | `bulk/_support/pk_sync.py:207-248` |
| **BLK-07** | comparar | `markdown_reporter.py` no escapa comentarios en tablas Markdown (`\|`/backtick rompe el render). | `comparar/reporters/markdown_reporter.py:191` |
| **BLK-08** | bulk | `PartitionResult.rows=0` no refleja filas ya comprometidas con `commit_every_n_chunks` si la partición falla a mitad — subestima filas reales insertadas. | `bulk/_execution/parallel_loader.py:375-384` |
| **MIG-04** | migrate | `extractors/base.py` (`Protocol SchemaExtractor`) no declara `extract_views`, pese a que las 4 implementaciones lo exponen y `planner.py` lo invoca incondicionalmente. | `migrate/extractors/base.py:10-37` |
| **MIG-05** | migrate | `emitters/__init__.py` solo exporta `DDLEmitter`/`MariaDBDDLEmitter`; los otros 3 emisores no son importables desde el paquete `emitters` (sí desde `migrate` de nivel superior). | `migrate/emitters/__init__.py` |
| **MIG-06** | migrate | `transformers/base.py` docstring de `transform_views` describe reescritura Oracle como si aplicara a los 12 pares; solo 3 (origen Oracle) la usan. | `migrate/transformers/base.py:25-38` |
| **MIG-07** | migrate | `_view_rewriter.py` — sustituciones léxicas (`SYSDATE`, `NVL(`, `FROM DUAL`, prefijo de schema) sin distinguir literales de código; salvo la de `USER`, no generan `MigrationWarning`. | `migrate/transformers/_view_rewriter.py:75-104` |
| **MIG-08** | migrate | Oracle con múltiples columnas `auto_increment` por tabla: solo la primera recibe SEQUENCE/TRIGGER (`break`); no hay `MigrationWarning` visible para las demás. | `migrate/emitters/oracle.py:287-317` |
| **CMP-02** | migrate/_compat | `identifier_rules.py` no implementa case-folding entre motores (Oracle uppercase-fold vs. PostgreSQL lowercase-fold); no detecta colisiones resultantes. | `migrate/_compat/identifier_rules.py` |
| **CMP-03** | migrate/_compat | Naming inconsistente: 3 de 12 `type_map_*.py` (Oracle como origen implícito) rompen la convención `type_map_<origen>_to_<destino>.py`; `_compat/__init__.py` no reexporta 5/12 mapas. | `migrate/_compat/{type_map,type_map_postgresql,type_map_sqlserver}.py`, `_compat/__init__.py` |
| **DOC-03** | doc | `word_generator.py:676-678` usa nombre de tabla sin sanitizar como nombre de fichero en la rama de fallback (solo si `graph_generator` no expone `pipe_single_table_graph_ext`). `strategy_registry.py` — motores sin estrategia caen a un fallback genérico sin nota explícita. | `doc/infrastructure/renderers/word_generator.py`, `doc/infrastructure/storage/strategy_registry.py` |

---

### Tabla P3 — Tests faltantes consolidados (agrupar con el fix que motiva cada uno)

- Test de conformidad de Protocol (`SourceAdapterSync/Async`, `RoutineAdapterSync/Async`) para los 9 adaptadores → **MDC-05**.
- Test de regresión de escaping en `test_template_engine.py` (payload `<script>`/`<img onerror>`) → **DOC-01**.
- Tests de inyección (`'; DROP TABLE`, backslash, `' OR '1'='1`) en los 6 validadores de `query/` → **SVC-02**.
- Test de integración real (o fake fiel al paramstyle) para motores no cubiertos por SQLite en CI — fuera de alcance de esta ronda salvo que ya esté cubierto por otro ítem.
- Test de fallo de `pool.close()`/`connection.close()` en el path async de `managers/` → **MGR-01**.
- Test de `AUTO_INCREMENT BIGINT` origen → **MIG-02** (una vez tomada la decisión de producto).
- Test factory sync dedicado (`test_sqlalchemy_engine_factory.py`, hoy inexistente — solo existe el async) → **SVC-01**/**SVC-03**.
- Test de `PoolFactory.create_pool`/`create_async_pool` directo (hoy solo cobertura indirecta vía managers) → **SVC-04**.
- Test con `sqlite3.connect(":memory:")` real que ejercite el SQL generado contra identificadores no triviales (hoy toda la suite SQLite mockea `cursor.fetchall`) → **MSS-03**.
- Test que compare explícitamente firmas/comportamiento sync vs async de SQL Server (el fichero "parity" actual no contrasta contra el Protocol) → **MSS-01**.
- Test de colisión cross-schema en `RelationshipMetadataCache` → **MDC-02**.
- Test de `_compare_indices`/`_compare_foreign_keys` con mismo objeto en distinto case, y de reordenamiento de columnas → **BLK-02**.
- Test de `sql_reporter.py` con `DEFAULT` conteniendo comilla simple → **BLK-03**.
- Test de fallo de auditoría dentro de `bulk_session()` → **BLK-01**.

---

## AUDIT_PLAN

### Riesgos funcionales
- **MIG-02** cambia la salida DDL de `emitters/mariadb.py` para cualquier PK `AUTO_INCREMENT` no-`INT`; si algún consumidor externo ya depende del `INT(11)` fijo (aunque sea un efecto no deseado), el cambio es observable. Requiere confirmación explícita antes de tocar (ver decisiones abiertas).
- **BLK-02** (case-insensitive en índices/FKs) cambia la salida de `SchemaComparator.compare()` para pares de motores con distinto case-folding: menos falsos positivos, pero es un cambio de comportamiento observable que debería mencionarse en CHANGELOG.
- **SVC-02**/**MEO-02** (endurecer validación de identificadores) puede rechazar identificadores legítimos pero inusuales (nombres con espacios ya entrecomillados, Unicode) si el allowlist es demasiado estricto — verificar contra los datos de prueba reales de cada motor antes de fijar el regex final.
- **MEO-01**/**MSS-01** (renombrar métodos / corregir firmas) son cambios de contrato en clases registradas en `AdapterRegistry`; grep obligatorio de todo `src/`+`tests/` antes de renombrar, para no dejar un caller apuntando al nombre viejo.

### Riesgos técnicos
- **MDC-05** debe hacerse a la vez (o justo antes) que **MEO-01**, **MSS-01**, **MEO-03**: es el mismo test ampliándose para cubrir tres fixes distintos. Hacerlo por separado tres veces duplica trabajo y puede dejar el test a medias.
- **MDC-01** es una decisión de alcance, no solo un fix: si se decide "conectar a la ruta real" en vez de "deprecar", el esfuerzo crece considerablemente (hay que decidir qué managers exponen `DDLBuilder`/`MetadataFetcher` y con qué contrato). Recomendado: deprecar explícitamente (no exportarlo, o marcar con `DeprecationWarning`) salvo que el usuario confirme un caso de uso real para el subsistema.
- **MGR-03** depende de que `DatabaseMetadataCache` (capa 5, fuera del módulo `managers/`) exponga métodos públicos `clear_context`/`clear_routine` equivalentes a los que hoy se simulan accediendo a atributos privados — es una dependencia real de secuencia, no solo de prioridad: añadir esos métodos públicos en `metadata/cache.py` antes de tocar `managers/_metadata_cache.py`.
- Todo fix dentro de `metadata/` (capa 5) debe re-verificarse contra `tests/unit/test_architecture_import_rules.py` (Regla #6) tras el cambio, dado que es una guarda estricta ya existente en CI.

### Riesgos de seguridad
- Los ítems P0 de seguridad (**DOC-01**, **MEO-02**, **SVC-01**, **SVC-02**, **CNX-01**, **CNX-02**) son los únicos con explotabilidad confirmada por los agentes (reproducida en vivo en el caso de DOC-01, contrastada contra `data/sql_queries.json` reales en el caso de SVC-02/MEO-02). Deben ir primero y cada uno con su propio test de regresión con payload adversarial, no solo con el fix.
- El patrón de interpolación insegura de identificadores/SQL aparece de forma **independiente** en al menos 6 módulos no relacionados (query/resolver, validators, mariadb helpers, sqlite pragmas, sql_reporter, connection strings) — no es un bug puntual sino la ausencia de una política de proyecto. Una vez cerrados los P0, se recomienda una pasada `/security-review` dedicada a "todo identificador se cita, todo valor se bindea" en todo `src/`, en vez de asumir que este backlog agota el problema.
- **MDC-01**: si se decide conectar `DDLBuilder` a la ruta real en vez de deprecarlo, su `_quote_identifier` (sin escapar comillas embebidas) debe corregirse **antes**, no después, de exponerlo a un caso de uso real.

### Dependencias entre ítems (orden obligatorio, no solo preferido)
1. **MDC-05** antes de (o junto con) **MEO-01** + **MSS-01** + **MEO-03**.
2. Métodos públicos nuevos en `metadata/cache.py` antes de **MGR-03**.
3. Decisión sobre **MDC-01** antes de decidir si `builder.py::_quote_identifier` se corrige (deprecar) o se corrige y se conecta (usar).
4. Decisión sobre **MIG-02** antes de tocar `emitters/mariadb.py` (no hay ambigüedad técnica, es puramente una decisión de producto).

### Detección de expansión
El alcance es, por decisión explícita del usuario, "todas las condiciones de las 12 franjas" — no se ha añadido ningún hallazgo fuera de los ya reportados por los 12 agentes. Se excluyen expresamente los ítems específicos de `metadata/redshift`/`metadata/snowflake`. Los tests de la Tabla P3 son los ya señalados por los agentes como ausentes, no casos nuevos inventados en esta fase de planificación.

---

## Veredicto: GO_CONDICIONAL → decisiones resueltas el 2026-09-22

1. **MIG-02** — **RESUELTO: preservar el ancho del tipo origen** (`INT`/`BIGINT`/`SMALLINT AUTO_INCREMENT`) en vez de fijar siempre `INT(11)`. Pendiente de implementar (P1, no incluido en la tanda P0 de hoy salvo que se pida explícitamente); revisar los 3 tests de `a950d18` al tocarlo.
2. **MDC-01** — **RESUELTO: conectar `MetadataManager`/`MetadataFetcher`/`DDLBuilder` a la ruta real de producción** (no deprecar). Esto amplía el esfuerzo de MDC-01: hay que decidir qué managers los exponen y con qué contrato, y corregir `builder.py::_quote_identifier` (no escapa comillas embebidas) y el `DEFAULT` sin comillas **antes** de conectarlo a un caso de uso real. Queda como su propio `/refactor` en una sesión futura (P1, fuera de la tanda P0 de hoy); no reabrir esta decisión.
3. **Agrupación MDC-05 + MEO-01 + MSS-01 + MEO-03** — **RESUELTO: un solo ciclo `/refactor` agrupado.** Sustituye a los hotfixes individuales MEO-01/MSS-01 en la secuencia P0 de hoy: se ejecuta como el último paso de la tanda de hoy (o en sesión aparte si el tiempo no alcanza), ampliando `test_protocol_conformance.py` a `SourceAdapterSync/Async`+`RoutineAdapterSync/Async` para los 9 motores y corrigiendo Oracle async, SQL Server sync y MariaDB firma reducida en el mismo commit.
4. **Orden de ejecución P0** — **RESUELTO: todos en esta misma sesión, uno tras otro, cada uno con su propio commit.** Secuencia acordada (severidad de seguridad primero): DOC-01 → MEO-02 → SVC-02 → SVC-01 → CNX-01 → CNX-02 → CMP-01 → DOC-02 → (grupo MDC-05+MEO-01+MSS-01+MEO-03).
5. **Alcance redshift/snowflake en documentación** — sin resolver explícitamente; por defecto se mantiene la recomendación original (no tocar documentación pública en esta ronda). Confirmar si surge la necesidad.

Cada ítem P0 se implementa como `/hotfix` independiente (RCA→FIX→AUDIT_CODE→VERSION), commit
propio en Conventional Commits, referenciando su ID de esta tabla (p. ej.
`fix(doc): activar autoescape Jinja2 en template_engine.py [DOC-01]`). Progreso registrado en
`TRACEABILITY.md` de esta sesión conforme se completa cada uno.
