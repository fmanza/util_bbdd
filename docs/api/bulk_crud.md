# CRUD Masivo (BulkCrud)

Proporciona operaciones de INSERT, UPDATE y DELETE masivo sobre tablas existentes usando DataFrames de pandas como fuente, con normalización de identificadores por motor, procesamiento por lotes y auditoría opcional.

## 1. Arquitectura y Diseño

```mermaid
flowchart TD
    A[BulkCrud] --> B[validate_engine]
    B -->|OK| C{Operación}
    C -->|insert| D["bulk_insert_from_df()"]
    C -->|update| E["bulk_update_from_df()"]
    C -->|delete| F["bulk_delete_from_df()"]
    D & E & F --> G{generar_sql?}
    G -->|Sí| H[Generar fichero .sql]
    G -->|No| I[BatchStatementExecutor]
    H --> I
    I --> J[SQLAlchemy → BD por lotes]
    J --> K["AuditManager.registrar\n(tabla, motor, filas, tiempo_seg)"]
```

## 2. Modelo de Datos / Contratos

### API pública

| Método | Firma simplificada | Descripción | Retorna |
|---|---|---|---|
| `BulkCrud` | `(engine, chunk_size?, audit_csv_path?, enable_fast_executemany?, insert_resolver?, commit_every_n_chunks?, update_via_staging?, audit_strict?, warn_if_audit_disabled?, strip_strings?, reflect_foreign_keys?, prefetch_blocks?, on_error?, rejects_csv_path?, max_rejects?)` | Crea instancia con engine SQLAlchemy | `BulkCrud` |
| `bulk_insert_from_df` | `(df, tabla_destino, generar_sql?, path_sql?)` | INSERT masivo desde DataFrame | `None` |
| `bulk_insert_from_chunks` | `(chunks, tabla_destino, *, override_identity?, exclude_autoincrement_pk?)` | INSERT streaming de iterable de DataFrames; resuelve columnas/identidad una sola vez | `int` (filas insertadas) |
| `bulk_update_from_df` | `(df, tabla_destino, generar_sql?, path_sql?)` | UPDATE masivo desde DataFrame | `None` |
| `bulk_delete_from_df` | `(df, tabla_destino, generar_sql?, path_sql?)` | DELETE masivo desde DataFrame | `None` |
| `bulk_update_from_chunks` | `(chunks, tabla_destino)` | UPDATE en streaming: `bulk_update_from_df` por chunk dentro de una sola sesión; lee el iterable de forma perezosa y lo cierra al terminar | `int` (filas enviadas) |
| `bulk_delete_from_chunks` | `(chunks, tabla_destino)` | DELETE en streaming, como `bulk_update_from_chunks` | `int` (filas enviadas) |
| `last_operation_rows_committed` | propiedad | Con `commit_every_n_chunks`: filas de la última operación (o de la que falló) confirmadas por commits periódicos, es decir, su prefijo confirmado. Para reanudar: `df.iloc[n:]`, o saltar `n` filas de la secuencia en `*_from_chunks` (cuentan como una operación). 0 en modo atómico | `int` |
| `rows_rejected` | propiedad | Con `on_error="isolate"`: filas rechazadas por la instancia (acumulado), escritas en `rejects_csv_path`. No están en la BD ni en la auditoría, pero sí cuentan en `rows_committed` y `last_operation_rows_committed`, que son posiciones de la entrada para reanudar | `int` |
| `bulk_session` | `(*, atomic=True)` | Context manager para loop de inserts con 1 transacción | `Generator[None, None, None]` |
| `maintenance_scope` | `(tabla_destino, *, disable_constraints=True, disable_indexes=False)` | Context manager que deshabilita FKs/triggers e índices para cargas >1 M filas; restaura siempre al salir. Requiere `bulk_session` activo | `Generator[None, None, None]` |
| `reflect_table` | `(tabla_destino)` | Refleja tabla SQLAlchemy (con caché interno) | `Table` |
| `sync_pk_sequences` | `(tables=None)` | Resincroniza contadores PK al `MAX` actual | `list[PKSyncResult]` |
| `audit_failures` | propiedad | Registros de auditoría que no se pudieron escribir en el CSV (con `audit_strict=False`) | `int` |
| `audited_rows` | propiedad | Filas de los registros escritos en el CSV de auditoría (incluye `generar_sql=True`) | `int` |
| `unaudited_committed_rows` | propiedad | Con `commit_every_n_chunks`: filas confirmadas por commits periódicos que no constan en el CSV porque la sesión falló antes de confirmar entera su operación | `int` |
| `audit_uncommitted_records` | propiedad | Con `audit_strict=True`: registros escritos en el CSV antes de un commit que falló | `int` |

### Contrato de entrada

| Parámetro | Tipo | Descripción | Restricciones |
|---|---|---|---|
| `engine` | `Engine` | Engine síncrono de SQLAlchemy | No puede ser `None`; lanza `ValueError` si es `None` |
| `chunk_size` | `int \| None` | Filas por lote. `None` elige el lote por motor y operación: 20 000 en el INSERT y el DELETE de PostgreSQL y en el DELETE de SQL Server, 5000 en el resto; con `commit_every_n_chunks`, 5000 en todas. Un entero se usa en todas las operaciones. `batch_sizes` devuelve los lotes resueltos | Default `None` (hasta v0.24.x, `5000`) |
| `audit_csv_path` | `Path \| None` | Ruta del CSV de auditoría | `None` desactiva la auditoría |
| `enable_fast_executemany` | `bool` | Si `True` (default) y el engine es `mssql+pyodbc`, activa `fast_executemany` en el dialecto, igual que `create_engine(..., fast_executemany=True)` (INSERT ~12× más rápido). Sin efecto en otros motores | Default `True` |
| `insert_resolver` | `InsertStrategyResolver \| None` | Estrategia INSERT personalizada | Default `None` (resolución automática por motor) |
| `commit_every_n_chunks` | `int \| None` | Commit cada N lotes en lugar de una sola transacción. La carga deja de ser atómica | Default `None` (una sola transacción) |
| `update_via_staging` | `bool` | MySQL/MariaDB y PostgreSQL: `bulk_update_from_df` carga cada lote en una tabla temporal y aplica un único `UPDATE` con join en lugar de un UPDATE por fila (1M filas: MySQL/MariaDB ~12,5×, PostgreSQL 2,35×). Mismo resultado final; requiere el privilegio `CREATE TEMPORARY TABLES` (MySQL/MariaDB) o `TEMP` (PostgreSQL, se comprueba antes de intentarlo); sin él, vuelve al UPDATE fila a fila y registra un WARNING (una vez por instancia). Ignorado en otros motores | Default `True` |
| `prefetch_blocks` | `bool` | Prepara el lote siguiente de INSERT y UPDATE en un hilo (cola de 2) mientras se envía el actual. Mismo resultado. 1M filas: SQL Server INSERT −10,6 % / UPDATE −6,2 %, MySQL y MariaDB −2 % a −6 %, Oracle/PostgreSQL/SQLite sin cambio medible | Default `False` |
| `on_error` | `"raise" \| "isolate"` | `"raise"`: un error en un lote hace fallar la operación. `"isolate"`: cada lote va en un SAVEPOINT; si falla con `IntegrityError` o `DataError` (PK duplicada, FK, valor demasiado largo...), se reenvía por mitades hasta aislar las filas que fallan, que se omiten y se escriben en `rejects_csv_path`; el resto se aplica. Otros errores se propagan. Solo INSERT, UPDATE y DELETE ejecutados (no `generar_sql`); no en `ParallelBulkLoader` ni `dump`. Coste: sin filas malas, un SAVEPOINT por lote; cada fila mala reenvía unas 2 veces su lote (ver [benchmarks](../guides/benchmarks.md#tuning-de-carga-masiva-bulk)) | Default `"raise"` |
| `rejects_csv_path` | `Path \| None` | CSV de filas rechazadas (UTF-8, tabuladores; se crea con cabecera o se añade): `timestamp`, `tabla`, `operacion`, `fila` (posición base 0 en la entrada; en `*_from_chunks`, en la secuencia), `error` (clase y primera línea del error del driver) y `valores` (JSON con las columnas de la tabla). **Contiene datos de las filas**; las celdas que empiezan como una fórmula (`=`, `+`, `-`, `@`) llevan un `'` delante | Obligatorio con `on_error="isolate"`; `ValueError` sin él o si se pasa con `"raise"` |
| `max_rejects` | `int \| None` | Filas que una operación (un `*_from_chunks` es una) puede rechazar; la siguiente hace fallar la operación con su error y una nota, como sin aislamiento (lo ya escrito en el CSV se queda) | Default `None` (sin límite); entero ≥ 0; solo con `on_error="isolate"` |
| `audit_strict` | `bool` | Qué hacer si falla la escritura del CSV de auditoría (fichero abierto en Excel, disco lleno, permisos). `False`: la operación sigue, porque sus datos ya están en la BD; se registra un ERROR con los registros perdidos y se cuentan en `audit_failures`. `True`: se propaga `AuditError`/`OSError`; dentro de `bulk_session` la auditoría se escribe antes del commit y el fallo deshace la sesión. Si lo que falla es el commit, lo ya escrito se cuenta en `audit_uncommitted_records` | Default `False` |
| `warn_if_audit_disabled` | `bool` | Sin `audit_csv_path`, avisar una vez con un WARNING de que la auditoría está deshabilitada. `ParallelBulkLoader` y `dump` pasan `False` a sus instancias y avisan una sola vez por carga | Default `True` |
| `strip_strings` | `bool` | Si `True`, quita los espacios de los extremos de las cadenas antes de enviarlas (INSERT, UPDATE, DELETE y SQL generado). `dump` pasa `False` para copiar el origen sin alterarlo | Default `True` |
| `reflect_foreign_keys` | `bool` | Si `True`, la `Table` de `reflect_table` incluye las claves foráneas de la tabla. `BulkCrud` no las usa: con `False` no se leen y la reflexión es más barata (SQL Server: ≈ 32 → 16 ms por tabla). `dump` pasa `False` | Default `True` |
| `df` | `pd.DataFrame` | Datos fuente | No puede estar vacío; columnas deben coincidir con tabla destino |
| `tabla_destino` | `str` | Nombre de la tabla en BD | Debe existir; se normaliza mayúsculas/minúsculas por motor |
| `generar_sql` | `bool` | Escribir el SQL generado en fichero | Si `True`, `path_sql` es obligatorio |
| `path_sql` | `Path \| None` | Directorio base para el fichero SQL | Nombre generado automáticamente (tabla + operación + timestamp) |

### Contrato de salida

- Los métodos de escritura (`bulk_insert_from_df`, `bulk_update_from_df`, `bulk_delete_from_df`) retornan `None`.
- `bulk_insert_from_chunks` retorna `int` (filas insertadas); `bulk_update_from_chunks` y `bulk_delete_from_chunks`, las filas enviadas.
- El error de un lote lleva una nota (`exc.__notes__`) con la operación, la tabla, el lote (y el chunk en `*_from_chunks`) y las filas de la entrada: `bulk UPDATE en 'items': falló el lote 1 del chunk 3 (filas 4005–4009 de la entrada, base 0)`. El tipo y el mensaje de la excepción no cambian.
- `sync_pk_sequences` retorna `list[PKSyncResult]`; errores capturados en `PKSyncResult.status="error"`, nunca propagados.
- Efectos secundarios: filas modificadas en BD, fichero `.sql` opcional, entrada en CSV de auditoría.
- Auditoría y transacciones: fuera de `bulk_session` cada operación se anota al terminar, con sus datos ya confirmados. Dentro de `bulk_session` (y en `bulk_insert_from_chunks`, que abre la suya) se anota cuando un commit la confirma: al salir del bloque o, con `commit_every_n_chunks`, en el commit periódico. Si la sesión acaba en rollback no queda ninguna fila de auditoría de lo deshecho (se avisa con un WARNING), y reintentar la sesión no la duplica. Con `commit_every_n_chunks`, una operación que falla con parte de sus lotes ya confirmados no se anota; `rows_committed` da esas filas. Las operaciones con `generar_sql=True` no tocan la BD y se anotan al momento.

### Errores y casos especiales

| Error | Cuándo ocurre |
|---|---|
| `ValueError` | `engine=None`, DataFrame vacío, `generar_sql=True` sin `path_sql`, no hay PKs para UPDATE/DELETE |
| `SQLAlchemyError` | Error al reflejar la tabla, timeout de BD, violación de constraint |
| `AuditError` / `OSError` | Solo con `audit_strict=True`: no se pudo escribir el CSV de auditoría. Con el valor por defecto (`False`) no se lanza |
| `RuntimeError` | `bulk_insert_from_chunks`, `bulk_update_from_chunks` o `bulk_delete_from_chunks` dentro de un `bulk_session` abierto: gestionan su propia transacción (dentro de la sesión, usar `*_from_df` por chunk) |

**Aislamiento de filas (`on_error="isolate"`), límites:**

- Solo se aíslan `IntegrityError` y `DataError`. Un error estructural (columna inexistente, permisos, sintaxis) se propaga: aislarlo rechazaría todas las filas.
- Algunos drivers no clasifican el valor demasiado largo como `DataError` y entonces la operación falla como sin aislamiento: Oracle (ORA-12899 llega como `DatabaseError`), SQL Server con pyodbc y `fast_executemany` (`ProgrammingError` en el cliente) y con pymssql (2628 como `OperationalError`). PK duplicada y FK sí se aíslan en los 6 motores.
- Si casi todas las filas fallan (p. ej. recargar datos ya cargados), la bisección acaba enviando fila a fila: usar `max_rejects`.
- La auditoría registra las filas aplicadas (enviadas − rechazadas).
- Los rechazos se escriben al detectarse: si después la operación o la sesión se deshacen por otra causa, el CSV los conserva.
- Si no se puede escribir el CSV de rechazos (p. ej. abierto en Excel), la operación falla con `OSError` y la nota «bulk: no se pudo escribir el CSV de rechazos»: no se pierde ningún rechazo en silencio. El detalle por fila va al log en DEBUG; el resumen de la operación, en WARNING.
- Con la misma PK repetida en un lote, aislar puede cambiar cuál de las filas se aplica.
- En SQLite (pysqlite), si la transacción aún no ha empezado se emite `BEGIN` antes del primer SAVEPOINT; si no, el `RELEASE` del SAVEPOINT confirmaba el lote fuera de la sesión.

**Estrategias INSERT por motor** (cuando `insert_resolver=None`):

| Motor / driver | Estrategia |
|---|---|
| `postgresql` + `psycopg` (psycopg3) | `COPY ... FROM STDIN` — vía más rápida de PostgreSQL |
| `postgresql` + `psycopg2` | `psycopg2.extras.execute_values` — un único `INSERT ... VALUES` multi-fila por chunk |
| `mysql` / `mariadb` + `pymysql` | `executemany` del driver sin procesadores de tipo (PyMySQL lo envía como `INSERT ... VALUES` multi-fila) |
| `mysql` / `mariadb` + `mariadbconnector` | `executemany` del driver (envío masivo) si cada columna del lote tiene un único tipo Python (sin contar `None`); si no, `INSERT ... VALUES` multi-fila |
| `mysql` / `mariadb` + otro driver | `INSERT ... VALUES` multi-fila sub-loteado en grupos de 1000 filas |
| `oracle`, `mssql`, `sqlite`, `hsqldb` | `executemany` estándar de SQLAlchemy |

## 3. Componentes y Clases

| Clase | Responsabilidad |
|---|---|
| `BulkCrud` | Fachada pública para operaciones bulk; gestiona normalización, lotes y auditoría |
| `BatchStatementExecutor` | Ejecuta sentencias SQL por lotes sobre una conexión SQLAlchemy |
| `Isolator` / `RejectsWriter` (`bulk/_support/rejects.py`, internos) | SAVEPOINT por lote y bisección de `on_error="isolate"`; escritura del CSV de rechazos |
| `InsertStrategyResolver` | Selecciona la estrategia INSERT óptima según motor y driver |

## 4. Dependencias y Requisitos

| Dependencia | Propósito | Requerida | Comportamiento sin ella |
|---|---|---|---|
| `util.timing.medir_tiempo` | Decorator para capturar duración de operaciones bulk | Sí (incluida en pyproject.toml) | Fallback: decorator placeholder; timing=0 ms en CSV de auditoría |
| `pandas` | DataFrame como fuente de datos | Sí | Sin pandas no hay datos para insertar |
| `sqlalchemy` | Reflexión de tabla, ejecución de sentencias | Sí | Módulo no funciona sin SQLAlchemy |

## 5. Ejemplos Relacionados

- [Ejemplo: Bulk Insert desde CSV con Auditoría](../examples/bulk_insert_csv.md) — Carga un CSV con `BulkCrud`, auditoría incluida
- [Ejemplo: Carga Paralela de Millones de Filas](../examples/parallel_bulk_insert.md) — Uso de `bulk_insert_from_chunks` con particionado
- [Ejemplo: Benchmark — Impacto de commit_every_n_chunks](../examples/benchmark_commit_cadence.md) — Ajuste de cadencia de commit para alto volumen
