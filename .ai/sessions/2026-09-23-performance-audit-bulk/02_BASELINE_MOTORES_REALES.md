# Línea base con motores reales (Fase 0)

- Fecha: 2026-09-24 · Herramienta: `scripts/bench_bulk.py` (sesión `2026-09-24-bulk-bench-harness`)
- Entorno: Windows 11, Python 3.14.2, pandas 3.0.3, SQLAlchemy 2.0.50; servidores en Docker local (`docker-compose.bench.yml`), `chunk_size=5000`
- Motores: SQLite 3.50.4 · PostgreSQL 17.11 (psycopg 3) · MySQL 8.4.11 (PyMySQL) · MariaDB 11.4.13 (PyMySQL) · SQL Server 2022 16.0.4295 con **pymssql 2.3.13** y con **pyodbc 5.3.0 + ODBC Driver 18** · Oracle 23 Free (oracledb thin)
- Tamaños: 1K/10K/100K con 3 repeticiones (mediana); 1M con 1 repetición
- Resultado de verificación:
  - 6 motores (SQL Server con pymssql): 240/240 mediciones con verificación SQL correcta (96 combinaciones motor × operación × tamaño × variante), 0 errores.
  - SQL Server con pyodbc: 33 mediciones correctas, 17 errores esperados y reproducibles: UPDATE `baseline` por P-18; DELETE ≥ 10K por P-05.
- Datos completos (P-02 y P-04 aplicados: `baseline/*_p02_*`, `baseline/*_p04_*`):
  - `baseline/summary_{small,1m}.md`, `baseline/results_{small,1m}.csv`, `baseline/environment_{small,1m}.json`
  - SQL Server con pyodbc: `baseline/*_mssql_pyodbc_{small,1m}.*`

**Límite**: servidores en Docker en la misma máquina, con latencia de red casi nula. Contra un servidor remoto, las operaciones con una ida y vuelta por fila (UPDATE en MySQL/MariaDB/SQL Server con pymssql) serán proporcionalmente mucho más lentas.

## Tiempos a 1M filas (segundos)

| Motor | INSERT | UPDATE | DELETE |
|---|---|---|---|
| SQLite | 13,7 | 17,0 | 2,8 |
| PostgreSQL | 20,1 | 40,5 | 28,2 |
| Oracle | 24,5 | 28,3 | 23,4 |
| MySQL | 50,8 (26,7 con P-02) | **378,5** | 15,7 |
| MariaDB | 50,2 (24,5 con P-02) | **339,0** | 15,0 |
| SQL Server (pymssql) | **376,4** | **556,1** | 45,6 |
| SQL Server (pyodbc) `baseline` | **245,5** | **falla (P-18)** | no medido¹ |
| SQL Server (pyodbc) con P-01 | 20,4 | 29,8 | **falla (P-05)** |

¹ El ciclo se corta al fallar el UPDATE; el DELETE falla igualmente por P-05 en la variante P-01.

## Filas por segundo a 100K (mediana de 3)

| Motor | INSERT | UPDATE | DELETE |
|---|---|---|---|
| SQLite | 70.151 | 54.145 | 257.732 |
| PostgreSQL | 47.849 | 23.696 | 35.351 |
| Oracle | 40.284 | 36.283 | 45.255 |
| MySQL | 17.410 → 32.192 (P-02) | 2.627 | 61.406 |
| MariaDB | 19.813 → 38.156 (P-02) | 2.930 | 67.083 |
| SQL Server (pymssql) | 2.702 | 1.728 | 21.250 |
| SQL Server (pyodbc) | 3.841 → **45.842 (P-01)** | falla (P-18) → **33.459 (P-01)** | falla (P-05) a partir de 10K |

## Estado de los hallazgos tras la medición

| ID | Antes | Ahora | Evidencia |
|---|---|---|---|
| P-01 | ALTA · confirmada en código | **CORREGIDA** (hotfix 2026-09-24; antes CONFIRMADA — CRÍTICA) | INSERT con `create_engine(fast_executemany=True)`: 11,55× (1K), 11,83× (10K), 11,93× (100K), **12,06× (1M: 245,5 s → 20,4 s)**. Además corrige P-18: el UPDATE pasa de fallar a 33.500 filas/s. |
| P-02 | CRÍTICA · hipótesis contra servidor | **APLICADA** (refactor 2026-09-24, solo PyMySQL; 1M: MySQL 2,09×, MariaDB 2,09×) | INSERT con executemany del driver: MySQL 1,85× (100K) y 1,90× (1M); MariaDB 1,93× (100K) y 2,05× (1M). A 1K es ruido (0,67×–1,18×). UPDATE y DELETE sin cambios (esperado: la variante solo afecta al INSERT). |
| P-04 | ALTA · hipótesis | **APLICADA, activa por defecto** (`update_via_staging=True`, 2026-09-24): 1M filas MySQL 376,0 s → 29,5 s (12,8×), MariaDB 331,4 s → 27,1 s (12,2×); antes CONFIRMADA | UPDATE a ~2.600–2.950 filas/s en MySQL/MariaDB y 1.800 en SQL Server con pymssql, frente a 35.000 en Oracle, 24.700 en PostgreSQL y 33.500 en SQL Server con pyodbc + P-01. 1M filas: 339–556 s frente a 28–41 s. |
| P-05 | CRÍTICA · confirmada en código | **CORREGIDA** (hotfix 2026-09-24; DELETE 1M con pyodbc en 8,9 s; antes CONFIRMADA en ambas partes) | Sintaxis de PK compuesta: falla con pymssql y con pyodbc. Límite de parámetros: con pyodbc el DELETE de ≥ 10K filas falla con `07002 COUNT field incorrect or syntax error` (lotes de 5000 parámetros); con pymssql no aplica (sustitución en cliente). Tests `xfail(strict=True)` con los dos drivers. |
| P-03 | ALTA | **APLICADA** (refactor 2026-09-24): preparación de 1M filas 8,58 s → 2,95 s (2,9×); SQLite INSERT 1M 13,8 → 8,4 s, UPDATE 17,1 → 11,7 s; antes Coherente | SQLite 1M INSERT 13,7 s (13,3 s en la medición del 23-09): la preparación en Python sigue siendo el suelo del resto de motores. |

## Hallazgos nuevos

### P-18: `bulk_update_from_df` falla en SQL Server + pyodbc con columnas DATETIME
**Severidad**: CRÍTICA (fallo funcional con la configuración por defecto)
**Área**: 8 (específico de motor)
**Archivo/Función**: `_execution/batch.py:19-42` (`_fast_executemany_listener`, `_register_fast_executemany`), activado por defecto desde `BulkCrud(enable_fast_executemany=True)`
**Descripción**: con `mssql+pyodbc` y ODBC Driver 18, todo `bulk_update_from_df` sobre una tabla con una columna `DATETIME` falla con `HY104 Invalid precision value (0) (SQLBindParameter)`. El listener activa `cursor.fast_executemany` a espaldas de SQLAlchemy, así que el dialecto no ajusta los tipos de los parámetros (`setinputsizes`) y pyodbc enlaza el `datetime` con precisión 0. El INSERT no falla porque, por P-01, nunca llega a usar fast_executemany.
**Evidencia** (bisección de columnas, 20 filas, tabla con PK + columnas indicadas):

| Columnas además de la PK | Listener (por defecto) | `enable_fast_executemany=False` | `create_engine(fast_executemany=True)` |
|---|---|---|---|
| A INT, F FLOAT, S VARCHAR | OK | — | — |
| solo D DATETIME | **FALLA** | — | — |
| A,D / F,D / S,D | **FALLA** | — | — |
| A, F, S, D | **FALLA** | OK | OK |

Los NULL en la primera fila no influyen: con A, F y S el UPDATE funciona con y sin NULL.

- Banco: UPDATE `baseline` falla en 10 de 10 ejecuciones (1K a 1M).
- Test de integración `test_insert_and_update_roundtrip[mssql]`: falla con pyodbc (marcado `xfail(strict=True)`, P-18) y pasa con pymssql.

**Confirmación**: CONFIRMADA. **CORREGIDA** en la sesión `2026-09-24-hotfix-p18-mssql-fast-executemany`: `baseline` con pyodbc hace el UPDATE de 100K en 2,98 s y el INSERT en 2,03 s.
**Remediación propuesta** (aplicada): la de P-01. Que `BulkCrud` no dependa del listener y use fast_executemany a través de SQLAlchemy (`create_engine(fast_executemany=True)` o una estrategia con cursor crudo y `setinputsizes`). Ambas medidas funcionan. Mientras tanto, los usuarios pueden:
- crear el engine con `create_engine(..., fast_executemany=True)`, o
- usar `BulkCrud(..., enable_fast_executemany=False)`.

### P-17: SQL Server + pymssql inserta a ~2.700 filas/s
**Severidad**: ALTA (CRÍTICA para cargas de 1M: 376 s)
**Estado**: **DESCARTADA** (2026-09-24, decisión del usuario, opción A). `bulk_copy` de pymssql no guarda lo mismo que un INSERT normal. Verificado en SQL Server 2022:

| Caso | INSERT actual | `bulk_copy` (pymssql 2.3.13) |
|---|---|---|
| Rollback de la transacción | se deshace | se deshace |
| Subconjunto/orden de columnas (`column_ids`), omitida con DEFAULT | — | correcto |
| Columna `DATE` | correcto | falla: solo acepta `datetime` |
| `NULL` explícito en columna con DEFAULT | `NULL` | valor por defecto (sin `KEEPNULLS`) |
| IDENTITY con id explícito 100 | 100 | 1 (sin `KEEPIDENTITY`) |
| CHECK violado, `check_constraints=True` | error | **aceptado** |
| FK a fila inexistente, `check_constraints=True` | error | **aceptado** |
| Estado de CHECK/FK tras la carga | confiables | **`is_not_trusted = 1`** |
| Triggers con `fire_triggers=True` | se disparan | se disparan |

No aplicar CHECK/FK (y degradarlos) no se puede resolver desde pymssql, así que usar BCP obligaría a excluir toda tabla con restricciones. En su lugar, `BulkCrud` registra un INFO al detectar `mssql+pymssql` recomendando `mssql+pyodbc` + ODBC Driver 17/18 (tras P-01: INSERT ~49.000 filas/s, UPDATE ~33.500, frente a ~2.700 y ~1.800 con pymssql).
**Área**: 8 (específico de motor)
**Archivo/Función**: `_execution/batch.py` `InsertStrategyResolver.resolve` (mssql → `DefaultInsertStrategy`)
**Descripción**: con pymssql, SQLAlchemy aplica insertmanyvalues (sentencias multi-VALUES de ≤ 2099 parámetros, ~233 filas con 9 columnas). cProfile sobre 20K filas: 6,16 s de 6,31 s en `do_execute` (driver + servidor), unos 72 ms por sentencia; SQLAlchemy es despreciable. El `executemany` crudo de pymssql es aún más lento (9,68 s).
**Evidencia**: prueba en el contenedor del banco, tabla temporal de 9 columnas y 20K filas:
- SQLAlchemy (actual): 6,31 s
- `cursor.executemany` de pymssql: 9,68 s
- **`connection.bulk_copy()` de pymssql (BCP/TDS bulk load): 0,94 s (6,7×)**, 20K filas verificadas.
**Confirmación**: CONFIRMADA (medición real).
**Remediación propuesta**: estrategia `MSSQLBulkCopyStrategy` para `mssql+pymssql` cuando `stmt` es `Insert`, con `check_constraints=True` y `fire_triggers=True` para conservar la semántica de un INSERT normal (por defecto BCP no comprueba constraints ni dispara triggers). Hay que verificar:
- atomicidad dentro de `bulk_session` (misma transacción);
- tablas con IDENTITY (`KEEPIDENTITY`);
- tipos (fechas, NULL, Unicode).

Con pyodbc + P-01 el INSERT ya alcanza 49.000 filas/s; para quien pueda elegir driver, pyodbc + ODBC 18 es hoy la mejor vía en SQL Server.

### P-19: `bulk_update_from_df` corrompe columnas JSON (MySQL `JSON`, PostgreSQL `JSONB`)
**Severidad**: CRÍTICA (corrupción silenciosa de datos)
**Área**: 3 (normalización) / 7 (generación SQL)
**Archivo/Función**: `crud.py` `__prepare_update_operation` (`update(tabla).values({col: bindparam(col)})`) + `normalize.py` `normalize_sql_literal` (dict/list → `json.dumps`)
**Descripción**: `normalize_sql_literal` convierte los dict/list a texto JSON. En el UPDATE, los parámetros van tipados con la columna reflejada, y el tipo `JSON` de SQLAlchemy vuelve a serializar ese texto: se guarda un *string* JSON en lugar del objeto, y `None` se guarda como el literal JSON `null` en lugar de `NULL` SQL. El INSERT no se ve afectado: COPY en PostgreSQL y `exec_driver_sql` / `text()` en MySQL no aplican procesadores de tipo.
**Evidencia** (servidores del banco, 2026-09-24): INSERT `{"k": 1}` → `{"k": 1}` en MySQL y PostgreSQL. UPDATE `{"k": 10}` → `"{\"k\": 10}"`; UPDATE `None` → `null` (no NULL), en los dos motores.
**Confirmación**: CONFIRMADA. Hallazgo previo, no introducido por P-02. **CORREGIDA** en la sesión `2026-09-24-hotfix-p19-json-double-encoding`. El alcance real era mayor: también el INSERT en SQLite (tipo `JSON` reflejado y parámetros tipados). Oracle (`NullType`) y MariaDB (`LONGTEXT`) no estaban afectados.
**Remediación propuesta**: `/hotfix`: no serializar dos veces en columnas de tipo JSON (p.ej. no convertir a texto los valores destinados a columnas JSON, o enlazar esos parámetros sin tipo). Hay que revisar también el INSERT de otros motores con tipo JSON (SQLite, Oracle).

### P-22: `MySQLMultiRowInsertStrategy` inserta en la tabla equivocada
**Severidad**: CRÍTICA (corrupción silenciosa: filas en otra tabla)
**Área**: 7 (generación SQL)
**Archivo/Función**: `_execution/batch.py` `MySQLMultiRowInsertStrategy._build_sql_template` (clave de `_sql_template_cache`)
**Descripción**: la clave de la caché de plantillas era `(num_rows, cols)`, sin la tabla. Una misma instancia (una por `BulkCrud`) que insertaba en dos tablas con las mismas columnas y el mismo tamaño de sub-lote reutilizaba la plantilla de la primera. `dump` en modo secuencial comparte una `BulkCrud` para todas las tablas (`orchestrator.py:165`).
**Evidencia**: MariaDB 11.4 + `mariadbconnector`: `bulk_insert_from_df` a `zz_util_bbdd_a` y después a `zz_util_bbdd_b` (mismas columnas, 2 filas): las 4 filas quedaron en `a` y `b` vacía. Detectado al verificar P-04 (la carga en tablas temporales con el mismo esquema fallaba con "Table … doesn't exist").
**Alcance**: desde P-02 (`9bc03de`, 2026-09-24), solo MySQL/MariaDB con drivers distintos de PyMySQL. Antes, todos los usuarios de MySQL/MariaDB desde la caché introducida en la sesión `2026-06-01f`.
**Confirmación**: CONFIRMADA. **CORREGIDA** en `2026-09-24-hotfix-p22-mysql-template-cache` (la tabla forma parte de la clave).

### P-21: `bulk_update_from_df` falla con BLOB si el valor binario es UTF-8 válido
**Severidad**: ALTA (fallo funcional con error visible)
**Área**: 3 (normalización)
**Archivo/Función**: `normalize.py` `_decode_bytes_to_string` + UPDATE con parámetros tipados (`LargeBinary`)
**Descripción**: `normalize_sql_literal` convierte a `str` los `bytes` decodificables como UTF-8 (`b"q"` → `"q"`). El parámetro tipado `LargeBinary` del UPDATE hace `bytes("q")` → `TypeError: string argument without an encoding`. El INSERT por vías sin tipo no falla.
**Evidencia**: MySQL 8.4 y MariaDB 11.4 con PyMySQL, UPDATE de una columna BLOB con `b""` y `b"q"`: `StatementError (TypeError) string argument without an encoding`.
**Confirmación**: CONFIRMADA. **CORREGIDA** en `2026-09-24-hotfix-p21-binary-utf8`. El alcance real era mayor: INSERT en SQLite y SQL Server (ambos drivers), UPDATE en PostgreSQL y MySQL/MariaDB sin staging, y pérdida silenciosa (NULL) en Oracle con cierta mezcla de valores.

### P-25: `bulk_update_from_df` sobrescribe una columna llamada `pk_<columna PK>`
**Severidad**: ALTA (corrupción silenciosa, aunque requiere un nombre de columna concreto)
**Área**: 3 (normalización)
**Archivo/Función**: `_support/validation.py` `build_update_plan` (`pk_param_map = {col: f"pk_{col}"}`); `crud.py` `__prepare_update_operation` (copia de la PK al alias en cada registro)
**Descripción**: el valor de la PK se enlaza en el WHERE con el alias `pk_<col>`, que se añade a cada registro. Si la tabla tiene además una columna real con ese nombre y se actualiza, las dos comparten clave en el registro: la columna recibe el valor de la PK.
**Evidencia**: SQLite, tabla `(id PK, pk_id, v)`, UPDATE de `pk_id` a 111/222: queda `pk_id = 1/2` (el valor de `id`), sin error. Reproducido también en PostgreSQL, MySQL, MariaDB y Oracle (UPDATE directo, por staging y SQL generado); SQL Server no (columnas en mayúsculas: `PK_ID` ≠ `pk_ID`).
**Confirmación**: CONFIRMADA (detectado en el refactor P-09, 2026-09-24). **CORREGIDA** en `2026-09-24-hotfix-p25-p26-pk-alias-delete-session` (sufijo numérico si el alias coincide con una columna).

### P-26: `bulk_delete_from_df` no participa en `bulk_session`
**Severidad**: MEDIA (bloqueo o falta de atomicidad dentro de una sesión)
**Área**: 4 (conexiones)
**Archivo/Función**: `_execution/batch.py` `DeleteBatchExecutor.execute` (siempre `engine.begin()`); `crud.py` `bulk_session` (solo inyecta la conexión en `BatchStatementExecutor`)
**Descripción**: INSERT y UPDATE usan la conexión de la sesión; DELETE abre su propia transacción. Dentro de `bulk_session` no es atómico con el resto, y si borra filas bloqueadas por la sesión espera su propio bloqueo.
**Evidencia**: SQLite, `with crud.bulk_session(): bulk_insert_from_df(...); bulk_delete_from_df(...)` → `OperationalError: database is locked` al agotar el timeout.
**Confirmación**: CONFIRMADA (detectado en el refactor P-09, 2026-09-24): falta de atomicidad en los 6 motores (el DELETE seguía aplicado tras fallar la sesión) y bloqueo en SQLite. **CORREGIDA** en `2026-09-24-hotfix-p25-p26-pk-alias-delete-session` (`bulk_session` inyecta su conexión también en `DeleteBatchExecutor`).

### P-27: PostgreSQL + `commit_every_n_chunks` pierde todas las filas del INSERT
**Severidad**: CRÍTICA (pérdida silenciosa de datos; `rows_committed` las da por confirmadas)
**Área**: 4 (conexiones) y 8 (específico de motor)
**Archivo/Función**: `_execution/batch.py` `PostgresCopyStrategy.execute` (y por el mismo patrón `PostgreSQLExecuteValuesStrategy`); `BatchStatementExecutor.execute` / `BulkCrud.bulk_session` en modo `commit_every_n_chunks`
**Descripción**: con `commit_every_n_chunks` la conexión se abre con `engine.connect()` (commit-as-you-go). El INSERT de PostgreSQL escribe por un cursor del driver (`connection.connection.cursor()`), que SQLAlchemy no ve: no hay transacción iniciada, `connection.commit()` no hace nada y al devolver la conexión al pool se deshace todo. Con `engine.begin()` (sin `commit_every_n_chunks`) no pasa, porque la transacción se abre explícitamente.
**Evidencia** (código anterior y actual): PostgreSQL 17 + psycopg 3.3, `BulkCrud(chunk_size=2, commit_every_n_chunks=1 o 2)`, `bulk_insert_from_df` + `bulk_insert_from_chunks` de 5 filas cada uno: **0 filas** guardadas (10 sin `commit_every_n_chunks`). MySQL, MariaDB, SQL Server (pymssql y pyodbc) y Oracle: 10 de 10. Dentro de `bulk_session` también se pierden, salvo que otra sentencia de SQLAlchemy (p.ej. un DELETE, tras P-26) inicie la transacción en la misma conexión.
**Alcance**: opt-in, pero ofrecido y recomendado para cargas grandes en `BulkCrud`, `ParallelBulkLoader` y `DumpConfig.commit_every_n_chunks`. psycopg2 2.9.13 (`PostgreSQLExecuteValuesStrategy`): mismo resultado, 0 de 10 filas, también dentro de `bulk_session`.
**Confirmación**: CONFIRMADA en psycopg 3 y psycopg2 (detectado en el hotfix P-25/P-26, 2026-09-24). **CORREGIDA** en `2026-09-24-hotfix-p27-pg-commit-every-n-chunks` (`_begin_if_needed` antes de usar el cursor del driver).

### P-28: en PostgreSQL los errores del INSERT llegan como excepción del driver, no como `SQLAlchemyError`
**Severidad**: MEDIA (el error no se pierde, pero se salta el manejo de errores de la librería)
**Área**: 8 (específico de motor)
**Archivo/Función**: `_execution/batch.py` `PostgresCopyStrategy` y `PostgreSQLExecuteValuesStrategy` (cursor del driver); consumidores que capturan `SQLAlchemyError`: `crud.py` `__run_bulk_pipeline` (log), `_execution/parallel_loader.py` (resultado de partición con error), `dump/orchestrator.py` (errores por tabla)
**Descripción**: lo que se ejecuta por el cursor del driver no pasa por SQLAlchemy, que es quien envuelve los errores del driver en `DBAPIError`. Una clave duplicada en el COPY llega como `psycopg.errors.UniqueViolation`. Los docstrings de `BulkCrud` prometen `SQLAlchemyError`.
**Evidencia**: `test_commit_every_n_chunks_keeps_committed_chunks_on_failure[postgresql]` con `pytest.raises(SQLAlchemyError)`: `psycopg.errors.UniqueViolation` sin envolver.
**Consecuencias**:
- `ParallelBulkLoader.load()` con una partición que repite una PK: con psycopg 3 y psycopg2 se aborta entero con `UniqueViolation`; con PyMySQL devuelve `total_rows=3` y 1 error.
- `dump`: no registra el error como error de la tabla (por deducción del código).
- `OperationalError` del driver: `ParallelBulkLoader` no lo reintenta (por deducción del código).

**Confirmación**: CONFIRMADA (hotfix P-27 y P-28, 2026-09-24). **CORREGIDA** en `2026-09-24-hotfix-p28-pg-driver-errors` (`_wrap_driver_error` con `DBAPIError.instance`).

## Prioridad revisada (por impacto medido)

0. ~~**P-19**~~: corregido (hotfix 2026-09-24).
0a. ~~**P-22**~~: corregido (hotfix 2026-09-24).
0c. ~~**P-21**~~: corregido (hotfix 2026-09-24).
0b. ~~**P-20**~~: corregido (hotfix 2026-09-24): el SQL generado con columnas JSON se ejecuta y guarda los documentos (SQLite, PostgreSQL, MySQL, MariaDB).
0d. ~~**P-23**~~: corregido (hotfix 2026-09-24): el SQL generado ya no duplica `%` en PostgreSQL ni MySQL/MariaDB.
0e. ~~**P-24**~~: corregido (hotfix 2026-09-24): prefijo del fichero SQL desde base de datos, `service_name`/`sid` o nombre del motor; en SQLite el fichero queda siempre en `path_sql`.
0f. Observación (SQLAlchemy, no de la librería): en dialectos posicionales (SQLite `qmark`), `compile(literal_binds=True)` convierte en `?` un texto con forma `%(nombre)s` incluso dentro de un literal (`'%(name)s'` → `'?'`). Afecta al SQL generado con datos que contengan ese patrón. Pendiente de valorar.
1. ~~**P-01 + P-18**~~: corregidos (hotfix 2026-09-24).
2. ~~**P-05**~~: corregido (hotfix 2026-09-24).
3. ~~**P-04**~~: aplicado en MySQL/MariaDB, activo por defecto (`update_via_staging=True`, ~12,5×). SQL Server con pymssql queda fuera: su cuello de botella es el INSERT (P-17).
4. ~~**P-02**~~: aplicado (refactor 2026-09-24). No era un cambio de una línea: `DefaultInsertStrategy` habría serializado dos veces las columnas JSON de MySQL, y el conector `mariadb` rechaza tipos mezclados por columna.
5. ~~**P-17**~~: descartado (`bulk_copy` de pymssql no aplica CHECK/FK). Recomendación: pyodbc + ODBC 17/18.
6. ~~**P-03**~~: aplicado (refactor 2026-09-24), preparación 2,9× más rápida con resultado idéntico.
7. ~~**P-09**~~ y copia superficial de P-07: aplicados (refactor 2026-09-24): el UPDATE prepara solo PK + columnas actualizables (3,1× con 7 columnas sobrantes a 100K) y sin copia completa del DataFrame.
8. ~~**P-25**~~ y ~~**P-26**~~: corregidos (hotfix 2026-09-24).
9. ~~**P-27**~~: corregido (hotfix 2026-09-24).
10. ~~**P-28**~~: corregido (hotfix 2026-09-24).
11. ~~**P-13**~~: confirmado contra MariaDB 11.4 + conector `mariadb` 1.1.14 ("Prepared statement contains too many placeholders" con INSERT de 1000 filas × 71 columnas y DELETE de 40.000 PK compuestas) y corregido (hotfix 2026-09-24): INSERT multi-fila y `DELETE ... IN` troceados a ≤ 65.535 parámetros. PyMySQL no fallaba. La otra mitad del hallazgo (un único `chunk_size` para todos los motores) no se ha tocado: no hay medición que muestre beneficio.
12. ~~**P-10**~~: aplicado (2026-09-24). 100K filas, mediana de 3: PK simple con `= ANY(:ids)` 2,79 → 0,99 s (2,8×) con psycopg 3 y 27,35 → 1,01 s (27×) con psycopg2; PK compuesta con `USING unnest(...)` 2,72 → 1,18 s (2,3×) y 27,90 → 1,17 s (24×). `(a, b) IN (...)` se descartó: 35–47 s, más lento que el `executemany`.
