# TRACEABILITY

## Session metadata
- id: 2026-09-25d-hotfix-bulk-column-case
- fecha: 2026-09-25
- rama: develop (base `c18bd0b`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-01 (CRÍTICA) de `2026-09-25-performance-audit-dump`; roadmap `2026-09-25b-performance-audit-dump-delta`, paso 0.1

## Prompt issued
```
/hotfix PD-01 (CRÍTICA): en SQL Server BulkCrud pasa a MAYÚSCULAS las columnas del DataFrame y las compara, distinguiendo
mayúsculas, con las reflejadas. Con columnas en minúsculas o mixtas falla cada tabla ("No hay columnas válidas para
INSERT"). Afecta a dump y a BulkCrud directo.
Criterios: dump y BulkCrud a SQL Server con columnas en minúsculas y mixtas: 3/3 success; test; banco de dump con
columnas en minúsculas en mssql.
```

## RCA
- `BulkCrud.__actualizar_df` aplica `normalize_dataframe_columns`: MAYÚSCULAS en SQL Server, minúsculas en PostgreSQL/Oracle/SQLite (MySQL/MariaDB se saltan).
- `get_insert_columns`, `build_update_plan` y `get_pk_columns` comparan después con `Column.name` reflejado **distinguiendo mayúsculas**. SQL Server refleja los nombres tal como se crearon: con `customer_id` en la tabla, `CUSTOMER_ID` no casa y la operación falla.
- Mismo tipo de fallo, más raro, en PostgreSQL/Oracle/SQLite con columnas mixtas citadas (`"CustomerName"` → `customername`). SQLite lo reproduce sin servidor.
- No se detectó antes porque los bancos de `bulk` (`scripts/bench_bulk.py::physical_name`) y de `dump` creaban las columnas en MAYÚSCULAS en SQL Server.

## FIX (mínimo)
- `bulk/_support/validation.py`: `align_dataframe_columns(df, table)` (nuevo). Tras la normalización, renombra al nombre reflejado las columnas **sin coincidencia exacta** cuya coincidencia sin distinguir mayúsculas es **única**. Si ya coinciden, o la coincidencia es ambigua (`Name` y `NAME` en la misma tabla), no toca nada.
- `bulk/crud.py`: `__actualizar_df(df, tabla)` llama a la normalización de siempre y luego a `align_dataframe_columns`. En `__run_bulk_pipeline` la llamada (con `reflect_table`, cacheado) pasa dentro del `try`, para que un fallo al reflejar se registre como antes. Cubre INSERT, UPDATE, DELETE (ejecución y `generar_sql`) y `bulk_insert_from_chunks`.
- `scripts/bench_dump.py`: el destino de SQL Server se crea con columnas en minúsculas y mixtas (`customer_id`, `Name`, `Country`, `Order_Date`, `Quantity`…); el origen conserva MAYÚSCULAS. El banco registra `skipped_columns` por tabla (la verificación COUNT/SUM(PK) no detecta una columna omitida).
- `CHANGELOG.md` (`[Unreleased]` → *Fixed*).

## Validación
- **Tests**:
  - `tests/unit/bulk/test_column_case_alignment.py` (nuevo, E2E con SQLite y columnas mixtas): INSERT + UPDATE + DELETE, `bulk_insert_from_chunks`, el DataFrame del llamador no se renombra, y `dump` a un destino con columnas mixtas. Los 4 fallan sin el arreglo.
  - `tests/unit/test_bulk_crud_helpers.py::test_actualizar_df_aligns_columns_with_reflected_table` (4 casos: mssql minúsculas/mixtas, PostgreSQL mixtas, sin cambios si ya coinciden, ambigua). Los 2 tests que llamaban a `__actualizar_df` directamente pasan ahora la tabla.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src tests/unit/test_protocol_conformance.py` limpio; `pytest tests/unit`: **4502 passed**.
- **SQL Server real** (pyodbc, `large` 3,5M filas; `results_antes/`, `results/`):

| Código | Repeticiones | Total | Tablas `success` | Verificación | Columnas omitidas | PK sync |
|---|---|---|---|---|---|---|
| Sin el arreglo (`git stash`) | 1 | 0,6 s | **0/3** (`No hay columnas válidas para INSERT en la tabla 'CUSTOMERS'`) | fallida | — | — |
| Con el arreglo | 3 | 66,3 s (mediana; 72,1 · 66,3 · 63,6) | **3/3** | 3/3 | ninguna | 3 × `synced` |

  El tiempo coincide con la línea base de la sesión delta (65,8 s con columnas en MAYÚSCULAS): el alineamiento se hace una vez por chunk sobre nombres de columna y no tiene coste medible.
- **`BulkCrud` directo contra SQL Server** (tabla temporal `dbo.zz_pd01_case` con `customer_id`, `CustomerName`, `country`, borrada al terminar): INSERT, UPDATE con `CUSTOMER_ID`/`customername` en el DataFrame, DELETE con `Customer_Id` y `bulk_insert_from_chunks`: los 4 OK.

## AUDIT_CODE
- **Sin cambio cuando ya coinciden**: solo se renombran columnas sin coincidencia exacta; toda carga que funcionaba antes produce el mismo DataFrame.
- **Nombres ambiguos**: con dos columnas de la tabla que solo difieren en mayúsculas (posible con collation case-sensitive), no se renombra; se mantiene el comportamiento anterior.
- **Columnas que no son `str`** (p. ej. enteros): se ignoran.
- **DataFrame del llamador**: se trabaja sobre la copia superficial de siempre (`copy(deep=False)`); `rename(inplace=True)` no afecta al original (test).
- **Orden de la reflexión**: en `__run_bulk_pipeline` la tabla se refleja antes de preparar la operación; es la misma consulta cacheada, dentro del mismo `try`, así que los errores (tabla inexistente) se registran y propagan igual.
- **Compatibilidad**: sin cambios de API pública. `normalize_dataframe_columns` y `normalize_identifier` no cambian.
- **Fuera del alcance**: `scripts/bench_bulk.py::physical_name` sigue creando columnas en MAYÚSCULAS en SQL Server; conviene añadir una variante en minúsculas en una sesión aparte.

## VERSION
- Commit: `fix(bulk): casar columnas del DataFrame con la tabla sin distinguir mayúsculas (PD-01)`
- Changelog: una entrada en `[Unreleased]` → *Fixed*.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[bulk]**: el nombre de columna que llega al INSERT/UPDATE/DELETE es el reflejado cuando la coincidencia es solo sin mayúsculas (`align_dataframe_columns`). No reintroduzcas comparaciones que distingan mayúsculas contra `Column.name` antes de ese paso.
- **[bench]**: el destino de SQL Server en `scripts/bench_dump.py` tiene columnas en minúsculas y mixtas a propósito; el origen, en MAYÚSCULAS. Los nombres solo difieren en mayúsculas (`Order_Date` ↔ `ORDER_DATE`); si difieren en algo más, `dump` omite la columna (revisa `skipped_columns`).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Resto de la Fase 0: PD-04, PD-05, PD-06 (parte de SQLite con rangos), PD-07, PD-08, PD-09.
