# TRACEABILITY

## Session metadata
- id: 2026-09-26v-hotfix-pymssql-decimal
- fecha: 2026-09-26
- rama: develop (base `6a6ce66`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-13, detectado por `tests/integration/test_dump_engines.py` (sesión `2026-09-26u-tests-integracion-dump`)

## RCA
- SQLAlchemy agrupa el lote en un `INSERT … VALUES (…), (…)` (insertmanyvalues). **pymssql incrusta los parámetros en el SQL con `str()`**, y `str(Decimal("-1E-10"))` es `-1E-10`; un cero leído de una columna `DECIMAL(p,10)` llega como `Decimal("0E-10")`.
- SQL Server lee `0E-10`/`-1E-10` como `float` y, en el `VALUES` multi-fila, convierte a `float` toda la columna: los DECIMAL de más de ~15 dígitos del lote se redondean sin aviso. El orden de las filas influye; pymssql directo (una sentencia por fila) es exacto.
- Afecta a `bulk` con pymssql en general (INSERT; también las claves de UPDATE/DELETE que pasan por el mismo camino).

## Opciones medidas (SQL Server 2022 + pymssql 2.3.13, 20K filas con valores grandes, ceros `0E-10` y NULL)

| Opción | Tiempo | Resultado |
|---|---|---|
| Actual | 0,79 s | 6.667 valores distintos |
| a1: `Decimal` → texto en notación fija | 0,90 s (+14 %) | exacto |
| **a2: `Decimal` con notación fija (subclase)** | **0,69 s** | **exacto** |
| b: sin insertmanyvalues (una fila por sentencia) | 14,06 s (18×) | exacto |

Elegida **a2**: exacta y sin coste; el valor sigue siendo un `Decimal` (numérico para SQL Server).

## FIX (mínimo)
- `bulk/_execution/batch.py`: `_PlainDecimal` (subclase de `Decimal` con `__str__`/`__repr__` en notación fija) y `_pymssql_plain_decimals(engine, records)`, aplicado en `BatchStatementExecutor._execute_on_connection` solo si el driver es pymssql.
- `tests/integration/test_dump_engines.py`: fuera el `xfail` estricto de PD-13 (salió `XPASS(strict)` con el arreglo).
- `CHANGELOG.md` (`[Unreleased]` → *Fixed*).

## Validación
- **Tests**: `TestPymssqlPlainDecimals` (2): con pymssql, notación fija, mismo valor, sigue siendo `Decimal`; otros drivers reciben los mismos registros. `test_dump_copies_values_exactly[mssql]` (pymssql) pasa.
- **SQL Server real con `BulkCrud`** (PK `DECIMAL(38,10)` con `12345678901234567.89`, `0E-10`, `-1E-10`, `1.5`): sin el arreglo, el INSERT redondea la clave (el script falla con `KeyError`); con él, INSERT, UPDATE y DELETE correctos.
- **Rendimiento** (`scripts/bench_bulk.py`, pymssql, 20K filas, A/B intercalado): INSERT 3,16 · 3,12 s → 3,19 · 3,12 s; UPDATE 15,9 · 13,6 s → 13,5 · 15,2 s (ruido igual en ambos lados).
- **Calidad**: `ruff` y `mypy` limpios. Con las URLs del banco: **5251 passed**; sin URLs: **5058 passed, 193 skipped**.

## AUDIT_CODE
- **Otros drivers**: sin cambios (reciben la misma lista).
- **Tipos**: `_PlainDecimal` es `Decimal` (`isinstance`); la aritmética devuelve `Decimal` normal.
- **Dependencia**: se apoya en que pymssql renderice el valor con `str()`; lo protege el test de integración con pymssql.
- **Alcance**: registros de INSERT/UPDATE del ejecutor por lotes; el DELETE por clave decimal ya era correcto en la prueba real.

## VERSION
- Commit: `fix(bulk): DECIMAL exacto con pymssql en lotes con valores en notación exponencial (PD-13)`
- Rollback: `git revert <commit>` (vuelve a poner el `xfail` del test).

## Directrices para Futuras IAs
- **[bulk/mssql]**: pymssql incrusta los parámetros en el SQL; cualquier valor cuyo `str()` no sea un literal SQL válido del tipo destino (p. ej. `Decimal` en notación exponencial) se reinterpreta. pyodbc no tiene este problema.

## Veredicto final
Veredicto: CLOSED
