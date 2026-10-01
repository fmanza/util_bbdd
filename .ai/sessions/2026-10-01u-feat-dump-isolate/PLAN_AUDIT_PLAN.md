# PLAN + AUDIT_PLAN — `DumpConfig(on_error="isolate", rejects_csv_path, max_rejects)` (Fase 4, P-B)

- Base: `develop` (`6e7d9be`, Fase 3 hecha). Origen: `../2026-10-01p-plan-bulk-pending-2/PLAN_AUDIT_PLAN.md` (P-B).
- Flujo: `/new-feature`. Sin refactor.

## Contexto verificado
- `dump` **desactiva las constraints del destino** antes de cargar (`ConstraintManager.disable_all`,
  `orchestrator.py:180-183`) y las rehabilita al final. Durante la carga **no fallan las FK ni los CHECK**; sí: PK
  duplicada (`truncate_target=False` o filas repetidas en un origen sin PK), NOT NULL, y sobre todo **tipos más estrechos
  en el destino** entre motores distintos (demasiado largo, precisión, conversión). En SQL Server el demasiado largo no se
  aísla (R-1 de S-2); en Oracle sí, con `batcherrors` (sesión `2026-10-01s`).
- Carga por tabla: `_load_whole_table` → `crud.bulk_insert_from_chunks` con una `BulkCrud` **reutilizada** por el hilo
  para varias tablas (`_make_worker_crud`, `orchestrator.py:762`); con `parallel_pk_ranges > 1`, `_load_in_pk_ranges` →
  `ParallelBulkLoader.load` (una partición por rango). Opciones comunes en `_bulk_options()` (`orchestrator.py:779`).
- Errores de carga: `_load_whole_table` captura `SQLAlchemyError`, `ValueError`, `AuditError`, `OSError` → error de la
  tabla y el volcado sigue (cubre `max_rejects` superado y el CSV de rechazos no escribible, M-1).
- Informe: hoja «Auditoría Tablas» (`reporters.py:328`), columnas Tabla … Filas Origen, Filas Destino Antes, Filas
  Destino Después, Estado, Columnas Omitidas, Error; `tests/unit/dump/test_reporters.py:191` y `:467` las leen por
  posición.

## Inputs (supuestos explícitos)
- **Objetivo**: que unas pocas filas que el destino no admite no hagan fallar la tabla entera del volcado: se apartan al
  CSV de rechazos y el resto se copia.
- **Módulos**: `dump/_models.py` (`DumpConfig`, `TableDumpResult`, `DumpResult`), `dump/orchestrator.py`
  (`_bulk_options`, `_load_whole_table`, `_load_in_pk_ranges`, `_process_table_with_columns`), `dump/reporters.py`;
  tests `tests/unit/dump/` y `tests/integration/` de dump; docs `docs/api/dump.md` (y la funcional de dump si existe);
  CHANGELOG.
- **API pública**: `DumpConfig(..., on_error="raise", rejects_csv_path=None, max_rejects=None)`;
  `TableDumpResult.rows_rejected: int = 0`; `DumpResult.rows_rejected` (propiedad, suma). Con los valores por defecto,
  nada cambia.

## PLAN
1. `DumpConfig`: tres campos nuevos; `__post_init__` llama a `validate_isolation` (antes de tocar el destino, como el
   resto de validaciones).
2. `_bulk_options()`: añade `on_error`, `rejects_csv_path`, `max_rejects` (llegan a `BulkCrud` y `ParallelBulkLoader`).
3. Rechazos por tabla:
   - Tabla entera: `rows_rejected` = diferencia de `crud.rows_rejected` antes y después de `bulk_insert_from_chunks`
     (la `BulkCrud` se reutiliza entre tablas del mismo hilo).
   - Por rangos: `_load_in_pk_ranges` devuelve también `ParallelLoadResult.rows_rejected` (método privado).
   - `TableDumpResult.rows_rejected`; si > 0, WARNING por tabla con la ruta del CSV.
4. Estado de la tabla (D-1): sigue `success` si no hubo error; los rechazos se ven en `rows_rejected`.
5. Informe (D-2): columna «Filas Rechazadas» en «Auditoría Tablas» tras «Filas Destino Después» (Filas Origen −
   Filas Rechazadas = filas copiadas, con destino vacío); se actualizan los dos tests que leen por posición.
6. Docs: parámetros, qué se aísla en un volcado (constraints desactivadas: no FK/CHECK), posición = orden de lectura del
   origen (`SELECT` sin `ORDER BY`; con rangos, dentro del rango, columna `particion` = rango), `max_rejects` por tabla o
   por rango; CHANGELOG *Added*.

## AUDIT_PLAN

### Riesgos y condiciones
- **R-1 Posición no reproducible**: el `SELECT` del origen no lleva `ORDER BY`; la posición identifica la fila en esa
  lectura, no en una futura. Los valores van en la columna `valores` del CSV, que es lo que sirve para corregirla.
  Documentar; no añadir `ORDER BY` (coste en tablas grandes).
- **R-2 FK huérfanas**: con constraints desactivadas, una fila con FK inexistente se copia (como hoy) y falla al
  rehabilitar la constraint (`constraint_results`); `isolate` no lo cambia. Documentar.
- **R-3 `max_rejects`**: se aplica por tabla (`bulk_insert_from_chunks` es una operación) o por rango con
  `parallel_pk_ranges`; superado, la tabla (o el rango) queda en error y el volcado sigue.
- **R-4 Concurrencia**: con `max_parallel_tables > 1` varias `BulkCrud` escriben el mismo CSV: lock por ruta (B-4).
- **R-5 Estado `success` con filas sin copiar** (D-1): quien solo mire `status` no verá los rechazos; mitigado con el
  WARNING por tabla, la columna del informe y `DumpResult.rows_rejected`. La alternativa (estado nuevo) cambiaría el
  `Literal` público de `status`.
- **R-6 Informe por posición**: insertar la columna desplaza Estado/Columnas Omitidas/Error una posición; un lector del
  Excel por posición se rompería (D-2).
- **R-7 Auditoría**: el CSV de auditoría de `bulk` ya registra filas aplicadas; `DumpAuditSummary` no cambia.

### Tests
- Unit (SQLite → SQLite): tabla con NOT NULL en destino y nulos en origen → rechazos, `rows_rejected`, estado
  `success`, filas copiadas; `truncate_target=False` con PK repetidas; con `parallel_pk_ranges=2` (columna `particion`);
  `max_rejects` → tabla en error y el resto del volcado sigue; validación en `DumpConfig`; columna en el informe;
  `on_error="raise"` sin cambios.
- Integración: volcado entre motores con destino más estrecho (p. ej. `VARCHAR(5)` en PostgreSQL/MySQL/MariaDB/Oracle
  desde un origen con textos más largos) → filas apartadas y resto copiado.

### Decisiones para el usuario
- **D-1 Estado de la tabla con rechazos**: (a) **`success` + `rows_rejected`** — recomendado (sin cambiar el `Literal`
  público); (b) estado nuevo `success_with_rejects`.
- **D-2 Columna del informe**: (a) **«Filas Rechazadas» tras «Filas Destino Después»** — recomendado (se lee junto a
  los recuentos; desplaza tres columnas); (b) al final, sin desplazar nada.

**Veredicto: GO_CONDICIONAL** (condiciones: D-1 y D-2)
