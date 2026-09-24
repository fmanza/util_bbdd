# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-p05-mssql-delete
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase: RCA + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Empiezo el `/hotfix` de P-05, el DELETE que falla en SQL Server?")

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- **RCA**: `SqlBasedDeleteStrategy` trataba `mssql` igual que MySQL.
  - (a) Todas las PK del lote (`chunk_size`, 5000 por defecto) en un único `IN (...)`; SQL Server admite como máximo 2100 parámetros por petición.
  - (b) Con PK compuesta, constructor de fila `(a, b) IN ((..), (..))`, que SQL Server no admite.
  - Reproducido sin servidor: 4500 PKs → 1 sentencia con 4500 parámetros; PK compuesta → `DELETE FROM [T] WHERE ([K1], [K2]) IN ((:pk_0_0, :pk_0_1))`.
- **AUDIT_PLAN**: GO.
  - En SQL Server el DELETE pasa a ⌈filas/2000⌉ sentencias por lote, en la misma transacción.
  - PK compuesta con pymssql: correcta pero fila a fila (lento, como P-04).
  - El resto de dialectos no cambia.
- **IMPLEMENT**:
  - `src/util_bbdd/bulk/_execution/batch.py`: constante `_MSSQL_MAX_DELETE_PARAMS = 2000`. `SqlBasedDeleteStrategy.execute` despacha por dialecto:
    - no `mssql`: comportamiento anterior;
    - `mssql` con PK compuesta: `GenericDeleteStrategy`;
    - `mssql` con PK simple: sublotes de 2000.
  - El cuerpo anterior pasa, sin cambios, a `_execute_statement`.
  - `tests/unit/bulk/test_delete_mssql.py` (nuevo, 4 tests): troceo 2000/2000/500 con todas las PK borradas una vez; PK compuesta sin constructor de fila; MySQL sigue con una sentencia y con constructor de fila.
  - `tests/integration/test_bulk_engines.py`: retirados los dos `xfail` de P-05 y el helper `_xfail_if_mssql`.
  - `CHANGELOG.md` (Fixed) y `docs/guides/benchmarks.md` (solución de problemas).
- **Validación**:
  - `ruff check src tests` limpio; `mypy src tests/unit/test_protocol_conformance.py tests/unit/bulk/test_delete_mssql.py` limpio.
  - `pytest`: 4466 passed / 19 skipped. Tests unitarios de DELETE (nuevos + `test_bulk_internal_helpers.py`): 19 passed.
  - Integración, sin ningún `xfail`: 6 motores con pymssql 18 passed; SQL Server con pyodbc + ODBC 18 8 passed.
  - Banco, SQL Server con pyodbc:
    - DELETE 10K 0,83 s y 100K 1,21 s (antes fallaban);
    - ciclo de 1M completo: INSERT 21,1 s, UPDATE 30,3 s, DELETE 8,9 s.
  - Banco, SQL Server con pymssql: DELETE 100K 4,91 s (antes 4,71 s; +4 %, dentro del ruido).

## AUDIT_CODE
- Regresiones potenciales:
  - En SQL Server, un lote de 5000 PKs pasa de 1 sentencia a 3. Con pymssql, +4 % a 100K (ruido); con pyodbc antes no funcionaba.
  - PK compuesta con pymssql: executemany fila a fila; lento en grandes volúmenes pero correcto (antes fallaba siempre).
- Edge cases:
  - Lote vacío: el troceo no itera y `_execute_statement` conserva su guarda.
  - Lote ≤ 2000: una sentencia, como antes.
  - Conexión simulada con dialecto no mssql (tests existentes): camino anterior.
- Compatibilidad: sin cambio de API pública. `DeleteStrategyResolver` y `_DEFAULT_SQL_BASED_DELETE_DIALECTS` no cambian.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix | `src/util_bbdd/bulk/_execution/batch.py` | completado |
| Test unitario | `tests/unit/bulk/test_delete_mssql.py` | nuevo |
| Regresión integración | `tests/integration/test_bulk_engines.py` | `xfail` P-05 retirados |
| Changelog / guía | `CHANGELOG.md`, `docs/guides/benchmarks.md` | actualizados |

## Directrices para Futuras IAs
- **[bulk/SQL Server]**: toda sentencia con parámetros por lote en `mssql` debe quedarse por debajo de 2100 parámetros (`_MSSQL_MAX_DELETE_PARAMS = 2000` en `batch.py`). No uses constructores de fila en `IN`.
- **[tests/integration]**: `test_bulk_engines.py` ya no tiene `xfail`. Cualquier fallo en SQL Server (pymssql o pyodbc) es una regresión.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (no realizado; pendiente de petición del usuario).
