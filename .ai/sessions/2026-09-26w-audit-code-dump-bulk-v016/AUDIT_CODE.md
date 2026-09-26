# AUDIT_CODE — `dump` y `bulk` desde v0.15.0 (`cfbbf05..c0b54e7`)

- Fecha: 2026-09-26 · Rama: `develop` · Skill: `/audit-code` (solo lectura: no se edita código)
- Contexto: recomendación 2 tras v0.16.0: revisión independiente de los cambios de la sesión (PD-01…PD-13, Q1–Q5, PF-09,
  2.3, 3.4) con foco en la concurrencia y los caminos de error.

## PLAN — alcance
`git diff cfbbf05..HEAD -- src/`: 8 ficheros, +618/−66.
- `dump/orchestrator.py` (+350): `_read_chunks`, `_execute_read`, `_prefetch`, `_rebatch`, `_resolve_write_batch_size`,
  `_single_writer_target`, `_warn_slow_pk_ranges`, `_warn_large_batch_with_lobs`, `_warn_sqlite_source`,
  `_truncate_together`, `_sync_pk_sequences`, `_reflect_loaded_tables` (ambas ramas), `_read_audit_csv`, `_file_size`.
- `dump/_constraints.py` (+61): `_find_fk_orphan_pg`, guarda `dbapi_conn is None`.
- `dump/_models.py` (+27): `write_batch_size`, docstrings.
- `bulk/_execution/batch.py` (+110): `_driver_decimal_context`, `_PlainDecimal`, `_pymssql_plain_decimals`,
  `MariaDBConnectorInsertStrategy`, `_uniform_column_types`, esquema de la tabla temporal de staging.
- `bulk/normalize.py` (+69), `bulk/crud.py` (+37), `bulk/_support/validation.py` (+25), `bulk/_execution/parallel_loader.py` (+5).

## AUDIT_PLAN — riesgos revisados
- Funcionales: resultado idéntico al de la vía anterior (cubierto por tests unitarios y por los 28 de integración).
- Técnicos: **concurrencia** (`_prefetch`, conexiones por hilo, listeners por conexión), cierre de recursos en los caminos
  de error, contratos de drivers (pymssql, Connector/Python, oracledb).
- Seguridad: SQL construido con identificadores citados (`quote_table`/`quote_identifier`, `quote_ident`/`regclass` del
  catálogo) y valores parametrizados; el nombre de FK va como parámetro.

## AUDIT_CODE — hallazgos

### A1 — MEDIA · la conexión de lectura se cierra con el hilo lector aún vivo si falla la escritura
- **Dónde**: `dump/orchestrator.py`, `_load_whole_table` (bloque `with cfg.source_engine.connect() as conn:` +
  `renamed = _prefetch(renamed)` + `crud.bulk_insert_from_chunks(renamed, …)`).
- **Qué**: si `bulk_insert_from_chunks` lanza, el `for` que consumía el generador no lo cierra; el `except` interno recoge
  el error y el `with` **cierra la conexión** mientras el generador sigue vivo (lo retiene la variable local `renamed`
  hasta que `_load_whole_table` retorna). El `finally` de `_prefetch` (`stop.set()` + `join()`) se ejecuta después.
  Contradice la garantía de su docstring.
- **Evidencia (PostgreSQL real)**: volcado con destino `VARCHAR(2)` (la escritura falla con
  `StringDataRightTruncation`): de 7 devoluciones de conexiones de origen al pool, **1 ocurrió con el hilo
  `dump-prefetch` vivo**; al final quedan 0 hilos (el recolector cierra el generador más tarde).
- **Riesgo**: si el lector está en un `fetchmany`, la conexión se cierra por debajo (drivers no seguros entre hilos, como
  PyMySQL); si está esperando en la cola, la conexión vuelve al pool mientras un hilo la retiene y puede entregarse a la
  siguiente tabla. Solo en el camino de error.
- **Remedio**: cerrar el generador antes de salir del `with` (p. ej. `try/finally` con `renamed.close()` o
  `contextlib.closing`), de modo que el `join()` ocurra antes de devolver la conexión.

### A2 — BAJA · los lectores de rangos no se cierran de forma determinista si falla la escritura
- **Dónde**: `bulk/_execution/parallel_loader.py` (`crud.bulk_insert_from_chunks(reader(), …)`) con los lectores de
  `dump._load_in_pk_ranges._make_reader` (`with cfg.source_engine.connect() as conn: yield from …`).
- **Qué**: el generador del lector no se cierra al fallar la escritura; su conexión (en PostgreSQL con cursor de servidor y
  transacción abierta) sigue ocupada hasta que el recolector libera la excepción. En CPython ocurre al terminar el
  `except`, así que la ventana es corta; no se observó ningún bloqueo con el código actual.
- **Remedio**: cerrar el iterador en el loader tras cada intento (`closing(reader())`).

### A3 — BAJA · `strip_strings=False` no respeta valores `numpy.str_` en columnas object
- **Dónde**: `bulk/normalize.py`, `_normalize_values` y `_normalize_text_values` (comparan con `type(value) is str`).
- **Evidencia**: `dataframe_to_sql_records(DataFrame({"s": Series([np.str_("  a  "), "  b  "], dtype=object)}),
  strip_strings=False)` → `[{"s": "a"}, {"s": "  b  "}]`: el `np.str_` se recorta. Un array numpy de cadenas no (pandas lo
  convierte a dtype `str`). No afecta a `dump` (recibe `str` del driver).
- **Remedio**: en la rama `strip_strings=False`, usar `isinstance(value, str)` (y devolver `str(value)` para no pasar
  `np.str_` al driver).

### Sin hallazgos (revisado)
- `_prefetch`: orden, propagación de errores del lector, parada con `stop` + `join` sin timeout, cola acotada (≤ 4 chunks en
  memoria), sin hilos vivos tras cada test.
- `_rebatch`: orden, resto, sin `concat` para un único chunk.
- `_execute_read`: listener Oracle en la conexión (no en el engine), retirado en `finally`, solo sube `arraysize`;
  `stream_results` por sentencia.
- `MariaDBConnectorInsertStrategy` / `_uniform_column_types`: criterio de tipo exacto (más estricto que el driver);
  `Update` → multi-fila.
- `_read_audit_csv`: desplazamiento en límite de fila (`\r\n`), fila parcial final filtrada por `timestamp`, fichero
  encogido → lectura completa.
- `_PlainDecimal` / `_pymssql_plain_decimals` (solo pymssql; sigue siendo `Decimal`), `_driver_decimal_context` (copia el
  contexto, restaura siempre).
- `align_dataframe_columns` (solo sin coincidencia exacta y con candidato único), `_truncate_together` (sin `CASCADE`,
  fallback con rollback), `_find_fk_orphan_pg` (savepoint, error → `failed`), `_resolve_write_batch_size`
  (`commit_every_n_chunks` respetado), guardas de SQLite, avisos.

### Tests
- **T1**: ningún test ejercita el orden cierre de conexión / fin del hilo lector en el camino de error de `_load_whole_table`
  (habría detectado A1). Sugerido: test unitario con un iterador de origen instrumentado y una escritura que falla,
  comprobando que el lector ha terminado antes de `conn.close()`/checkin.

### Tipado / deuda
- Sin `Any` nuevos injustificados (los `Any` son de conexiones/cursores DBAPI). `mypy src` limpio.

## Veredicto
**APROBADO CON CONDICIONES**: corregir **A1** con su test (T1) antes del próximo release. A2 y A3 son de baja severidad y
pueden ir en el mismo cambio o registrarse en el roadmap.

## VERSION (si se corrige)
- `fix(dump): cerrar el lector en paralelo antes de devolver la conexión si falla la escritura (A1)`
- Pruebas sugeridas: T1; volcado real con fallo de escritura comprobando 0 devoluciones con el hilo vivo (script
  `audit_prefetch_close.py` de esta sesión).

## Seguimiento
- **A1, A2, A3 corregidos** en `2026-09-26x-hotfix-audit-a1-a3` con el test T1 (`tests/unit/dump/test_failure_paths.py`).
  PostgreSQL real: 0 de 7 devoluciones con el hilo lector vivo (antes 1 de 7).
