# TRACEABILITY

## Session metadata
- id: 2026-09-24-refactor-p17-pymssql-bulk-copy-descartado
- fecha: 2026-09-24
- rama: develop
- skill: refactor (evaluación) → decisión del usuario: descartar
- fase: PLAN (verificación previa) + decisión + documentación

## Prompt issued
```
si
```
(Respuesta a "¿Sigo con P-17?". Tras la verificación, el usuario eligió "A": descartar y documentar, con recomendación de pyodbc.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` (P-17: prototipo `bulk_copy` 6,7×)
- pymssql 2.3.13 `_pymssql.pyx` / `_mssql.pyx` (`bulk_copy`, `bcp_sendrow`, `bcp_bind`): solo expone `column_ids`, `batch_size`, `tablock`, `check_constraints` y `fire_triggers`; no `KEEPNULLS` ni `KEEPIDENTITY`.

## AI output summary
- **Verificación previa en SQL Server 2022 + pymssql** (referencia: `BulkCrud.bulk_insert_from_df` actual):
  - Rollback de la transacción: correcto.
  - `column_ids` con subconjunto y orden distinto: correcto; la columna omitida recibe su DEFAULT.
  - `DATE`: `bulk_copy` falla ("value can only be a datetime.datetime").
  - `NULL` explícito en columna con DEFAULT: el INSERT guarda NULL; BCP guarda el DEFAULT.
  - IDENTITY con id explícito 100: el INSERT guarda 100; BCP genera 1.
  - CHECK y FK violados con `check_constraints=True`, repetido en tablas nuevas: **aceptados**, y ambas restricciones quedan con `is_not_trusted = 1`.
  - `fire_triggers=True`: los triggers se disparan.
- **Decisión**: no implementar BCP (la opción segura excluiría toda tabla con CHECK/FK). Recomendar pyodbc + ODBC 17/18, que tras P-01 va a ~49.000 filas/s en INSERT y ~33.500 en UPDATE.
- **Cambios**:
  - `crud.py` `__detectar_sqlserver_driver`: INFO al detectar `mssql+pymssql` recomendando pyodbc (una vez por instancia de `BulkCrud`).
  - `tests/unit/bulk/test_fast_executemany.py`: 2 tests (INFO con pymssql, sin INFO con pyodbc).
  - `CHANGELOG.md` (Changed); `docs/guides/benchmarks.md` (fila pymssql en la tabla de estrategias y en solución de problemas); `02_BASELINE_MOTORES_REALES.md` (P-17 DESCARTADA con tabla de evidencia).
- **Validación**: `ruff check src tests` y `mypy src` limpios; suite 4533 passed / 58 skipped; build de docs sin avisos en `benchmarks.md`.

## Directrices para Futuras IAs
- **[bulk/SQL Server]**: no uses `pymssql.Connection.bulk_copy` para cargas de `BulkCrud`: no aplica CHECK ni FK aunque se le pida (y las deja como no confiables), ignora NULL explícitos en columnas con DEFAULT e ignora ids de IDENTITY. La vía rápida y equivalente en SQL Server es pyodbc + ODBC 17/18 con `fast_executemany`.

## Veredicto final
Veredicto: CLOSED (P-17 descartada)
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
