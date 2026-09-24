# TRACEABILITY

## Session metadata
- id: 2026-09-24-audit-code-bulk
- fecha: 2026-09-24
- rama: develop
- skill: audit_code → hotfix (hallazgos 1, 2 y 3)
- fase: PLAN + AUDIT_PLAN + AUDIT_CODE + IMPLEMENT (hotfix) + VERSION

## Prompt issued
```
/audit-code src\util_bbdd\bulk
```
```
Adelante con todo lo propuesto
```
(Lo propuesto: guardar la auditoría en `.ai/sessions/` y corregir con `/hotfix` los hallazgos 1 y 2, y también el 3.)

## Context supplied
- `src/util_bbdd/bulk/` completo: 21 ficheros, 5.401 líneas.
- Sin contexto ni foco indicados: se auditó todo (fallos, casos límite, seguridad, tipado, tests), con prioridad al código de 0.12.0, 0.13.0 y `[Unreleased]`.

## Auditoría (veredicto: APROBADO CON CONDICIONES)

| # | Sev. | Dónde | Hallazgo | Evidencia | Estado |
|---|---|---|---|---|---|
| 1 | ALTA | `crud.py:186`, `batch.py` (ejecutores) | `chunk_size` sin validar: con -5, 0 filas insertadas, sin error, y auditoría "INSERT 3"; con 0, `range() arg 3 must not be zero` al ejecutar | Reproducido (SQLite) | **CORREGIDO** |
| 2 | MEDIA | `crud.py` `maintenance_scope` (`finally`) | En PostgreSQL, un error dentro del bloque llegaba como `InternalError (InFailedSqlTransaction)`. Al corregirlo aparecieron dos casos más: con `commit_every_n_chunks` los triggers (PostgreSQL) y la FK (SQL Server) quedaban deshabilitados | Reproducido (PostgreSQL 17; SQL Server 2022 con `commit_every_n_chunks`) | **CORREGIDO** |
| 3 | MEDIA | `parallel_loader.py` `_hoist_constraints_for_workers` | En PostgreSQL sin privilegios, `yield False` dentro de `engine.begin()`: conexión retenida con transacción abierta durante toda la carga | Test con eventos: `begin, SELECT, workers, end` | **CORREGIDO** |
| 4 | BAJA | `parallel_loader.py:61` `_quote_pg_table` | No normaliza a minúsculas como `BulkCrud`: con `"Usuarios"` la comprobación de propietario falla sin avisar, o el ALTER da error con superusuario | Por código | Pendiente |
| 5 | BAJA | `pk_sync.py:163`, `:304`/`:313` | `pg_get_serial_sequence` con `esquema.tabla` sin comillas y `UPPER(:tbl)` en Oracle: tablas con mayúsculas o en minúsculas entre comillas → `error`/`unsupported` | Por código | Pendiente |
| 6 | BAJA | `sql_helpers.py:110` | Nombre de tabla sin sanear en el nombre del fichero de `generar_sql` (`/`, `:`, `..`) | Por código | Pendiente |
| 7 | BAJA | `batch.py` `DeleteBatchExecutor.execute` | Fuera de `bulk_session`, el DELETE ignora `commit_every_n_chunks` (una sola transacción); incoherente con INSERT/UPDATE y sin documentar | Por código | Pendiente |
| 8 | BAJA (nuevo) | `crud.py` `maintenance_scope` en MySQL/MariaDB con `disable_indexes=True` | `ALTER TABLE … DISABLE/ENABLE KEYS` es DDL con commit implícito: rompe la atomicidad de la sesión (antes y después de este cambio) | Por código (documentación de MySQL) | Pendiente |

- **Seguridad**: sin inyección:
  - identificadores escapados por el dialecto (`quote`, `format_table`, `_qt`, `_qi`);
  - valores enlazados o `int()`;
  - `DBCC CHECKIDENT` con comillas escapadas;
  - tablas temporales con UUID.

  Credenciales ocultas en la URL, HTML de auditoría escapado (`to_html`) y CSV con bloqueo por fichero.
- **Tipado**: 3 anotaciones incompletas (`crud.py` `__init__`, `__obtener_pk_cols`, `__ejecutar_delete_batch`) y `connection: Any` en las estrategias; mypy limpio.
- **Rendimiento**: sin problemas nuevos. `HashPartitioner` compara dos veces por bucket (menor).

## Hotfix aplicado
- **1**: `batch.validate_chunk_size()` (usa `operator.index`: acepta enteros de numpy; rechaza `bool`, decimales, 0 y negativos), llamado en `BulkCrud.__init__`, `ParallelBulkLoader.__init__` (antes del pool) y los dos ejecutores. Test `tests/unit/bulk/test_chunk_size_validation.py` (22).
- **2**: `maintenance_scope` sustituye el `finally` por `except BaseException` + `__maintenance_restore_after_error` y deja la restauración normal para cuando no hay error.
  - Atómico: intenta restaurar; si la transacción no lo admite, registra un aviso sin ocultar el error, porque el rollback de la sesión deshace la desactivación.
  - Con `commit_every_n_chunks`: `rollback`, pone a cero los contadores pendientes del ejecutor, restaura y hace `commit`.
  - Test de integración `test_maintenance_scope_error_keeps_original_exception_and_restores`: 6 motores × {atómico, `commit_every_n_chunks=1`}, tabla hija con FK. Comprueba que llega `IntegrityError`, que la FK queda activa y fiable, y las filas esperadas. Con el código anterior fallaban `postgresql-None`, `postgresql-1` y `mssql-1`.
- **3**: la conexión de la comprobación de privilegios se cierra antes de `yield False`. Test `tests/unit/bulk/test_parallel_loader_hoist.py` (2): orden de eventos con y sin privilegios; sin el fix falla el de "sin privilegios".
- **Validación**:
  - `ruff check src tests` y `mypy` limpios;
  - suite sin URLs 4764 passed / 149 skipped (todos por servidor sin URL);
  - con las URLs del banco 4913 passed, 0 skipped, 0 warnings.

## AUDIT_CODE del hotfix
- **Regresión posible (2)**: con `commit_every_n_chunks`, si alguien captura la excepción dentro de la sesión y sigue cargando, lo no confirmado antes del fallo se ha deshecho. Antes, en PostgreSQL la transacción quedaba igualmente inutilizable, y en SQL Server quedaba la FK deshabilitada.
- **Contrato (1)**: `BulkCrud(chunk_size=...)` inválido lanza `ValueError` al construir; antes fallaba al ejecutar (0) o no escribía nada (negativo).

## Observación
- En el repositorio apareció un fichero ajeno a esta sesión, `.github/prompts/performance_audit_dump.prompt.md` (sin seguimiento). No se toca ni se incluye en los commits.

## Directrices para Futuras IAs
- **[bulk/validación]**: todo parámetro de tamaño o bucle (`chunk_size`, `commit_every_n_chunks`, `max_workers`) se valida en el constructor. Un `range` con paso inválido falla sin avisar (negativo) o tarde (0).
- **[bulk/transacciones]**: no ejecutar SQL de limpieza en un `finally` sobre una transacción que puede estar abortada (PostgreSQL), y no tapar la excepción original. Con commit-as-you-go, la limpieza debe confirmarse en su propia transacción.
- **[bulk/paralelo]**: nunca ceder el control (`yield`) dentro de un `engine.begin()`/`connect()` que abarque el trabajo de los workers.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- Hallazgos 4–8 (BAJA).
