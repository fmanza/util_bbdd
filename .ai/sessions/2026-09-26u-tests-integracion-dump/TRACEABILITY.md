# TRACEABILITY

## Session metadata
- id: 2026-09-26u-tests-integracion-dump
- fecha: 2026-09-26
- rama: develop (base `d510d1b`, v0.16.0)
- skill: tests de integración (sin cambios en `src/`)
- origen: recomendación 1 tras el cierre de v0.16.0 («llevar las correcciones a la suite de tests»), aceptada por el usuario

## Objetivo
Varias correcciones de v0.16.0 solo estaban verificadas con scripts del scratchpad contra servidores reales. Llevarlas a
`tests/integration/`, que se ejecuta contra los 5 servidores del banco, y que el banco de `bulk` deje de ocultar PD-01.

## Restricción descubierta
Los usuarios de las URLs de pruebas (`scripts/bench_env.example.*`) no pueden crear esquemas o bases propias en MySQL,
MariaDB (1044) ni Oracle (`ORA-01031`); PostgreSQL (`bench`) y SQL Server (`sa`) sí. Diseño: **origen PostgreSQL** (esquema
temporal con BIGINT de 64 bits y DECIMAL(38,10)) y **volcado entre motores** a cada servidor, con las tablas destino en el
esquema por defecto del usuario (nombres únicos, borradas al terminar) y `target_schema` explícito (ruta `esquema.tabla`).

## Cambios
- `tests/integration/test_dump_engines.py` (nuevo, 28 tests):
  - `test_dump_copies_values_exactly` (PD-05, PD-10, PD-01, PF-09) en PostgreSQL, MySQL, MariaDB (PyMySQL y Connector/Python), SQL Server y Oracle;
  - `test_identity_is_resynced_after_dump` con tabla entera y con 2 rangos (PD-02, PD-11);
  - `test_redump_with_foreign_keys` (PD-03);
  - `test_orphan_rows_mark_the_foreign_key_as_failed` (PD-04, PostgreSQL);
  - `test_staging_update_with_schema_and_no_default_database` (PD-12, MySQL, MariaDB con ambos drivers).
  - Sin URLs se saltan los 28 (como el resto de la integración).
- `scripts/bench_bulk.py`: `physical_column` — columnas en minúsculas en SQL Server (las MAYÚSCULAS ocultaban PD-01); prueba de humo en SQL Server, SQLite y PostgreSQL: 9/9 operaciones OK. `tests/unit/test_bench_bulk_script.py` adaptado (+ test de `physical_column`).

## Validación de que los tests detectan los fallos
Ejecutados contra el código de **v0.15.0** (worktree temporal, `PYTHONPATH` a su `src/`), excluyendo el caso de rangos:
**14 fallan** (fidelidad en todos los motores, identidad en todos, volcado repetido en PostgreSQL y SQL Server, FK huérfana)
y los 3 de PD-12 fallan (tras corregir el test, ver abajo). Con el código actual pasan.

## Hallazgos durante la sesión
- **PD-13 (nuevo, abierto)**: con **pymssql** (la URL de pruebas de SQL Server), un DECIMAL grande pierde precisión si el lote contiene un `Decimal` en notación exponencial (`-1E-10`, y también un cero leído de `DECIMAL(p,10)`: `0E-10`). SQLAlchemy agrupa el lote en un `INSERT … VALUES (…), (…)` (insertmanyvalues); pymssql incrusta los parámetros en el SQL y SQL Server lee `-1E-10` como `float`, lo que convierte toda la columna del INSERT multi-fila. Reproducido: `[V, -1E-10]` → redondeo; `[-1E-10, V]` → exacto; pymssql directo (una sentencia por fila) → exacto; con `BulkCrud`, `12345678901234567.89` + `0E-10` → `12345678901234568`. Afecta a `bulk` con pymssql en general. El test queda `xfail(strict=True)` para pymssql hasta corregirlo.
- **v0.15.0 dejaba conexiones colgadas**: con `parallel_pk_ranges`, los lectores de rangos quedaban `idle in transaction` en PostgreSQL y bloqueaban el `DROP SCHEMA` del test (colgado > 10 min). Con el código actual el mismo test pasa en segundos (lo resolvieron los cambios de lectura de la sesión). Se limpiaron las sesiones, el esquema y el worktree.
- **Error propio corregido**: el test de PD-12 usaba `URL.set(database=None)`, que no cambia nada (SQLAlchemy ignora los `None` en `set`); pasaba también con v0.15.0. Ahora construye la URL con `URL.create(..., database=None)` y comprueba que no hay base por defecto.

## Validación final
- `ruff` (src, tests, scripts) limpio; `mypy` limpio.
- Con las URLs del banco: **5250 passed, 1 xfailed** (PD-13). Sin URLs: **5058 passed, 193 skipped** (165 previos + 28 nuevos).

## Directrices para Futuras IAs
- **[tests/integración]**: el usuario de pruebas solo puede crear esquemas en PostgreSQL y SQL Server; para probar `dump` en otros motores, origen PostgreSQL y destino en el esquema por defecto.
- **[tests]**: `URL.set()` ignora los `None`; para quitar la base de datos usa `URL.create(..., database=None)`.
- **[tests]**: comprueba un test de regresión contra el código anterior al arreglo (worktree de la versión previa + `PYTHONPATH`); uno que pasa en ambos no protege nada.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- PD-13 (DECIMAL con pymssql + insertmanyvalues).
