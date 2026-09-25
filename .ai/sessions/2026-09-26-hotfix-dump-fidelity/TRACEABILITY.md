# TRACEABILITY

## Session metadata
- id: 2026-09-26-hotfix-dump-fidelity
- fecha: 2026-09-26
- rama: develop (base `28666ce`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-05 (ALTA) de `2026-09-25-performance-audit-dump`; roadmap `2026-09-25b-performance-audit-dump-delta`, paso 0.6

## Prompt issued
```
/hotfix PD-05: la ruta pandas de dump altera datos sin avisar: BIGINT > 2^53 en columna con NULL → float64; DECIMAL de
más de 15 dígitos → float (coerce_float=True); strip() de toda cadena. Criterios: round-trip exacto de BIGINT > 2^53 con
NULL, DECIMAL(38,10) y cadenas con espacios; read + prep no empeora > 10 % (banco large).
```

Decisión del usuario (preguntada durante el PLAN): **opt-out solo para `dump`** del `strip()` de `bulk` (`BulkCrud(strip_strings=True)` por defecto; `dump` pasa `False`), frente a quitar el strip en todo `bulk` o dejarlo.

## RCA
- **Enteros**: `pd.read_sql` construye el DataFrame con `from_records`; una columna de enteros con algún `None` pasa a `float64` **dentro de pandas** (también un INT normal: `1` → `1.0`). La precisión se pierde antes de que `dump` vea el dato; ninguna conversión posterior la recupera.
- **Decimales**: `coerce_float=True` (valor por defecto de `read_sql`) convierte `Decimal` a `float`.
- **Opciones de `read_sql` medidas** (PostgreSQL real): `coerce_float=False` arregla solo `Decimal`; `dtype_backend="numpy_nullable"` o `"pyarrow"` conservan los enteros pero entregan los `Decimal` como **texto**. Ninguna es exacta y con el tipo correcto.
- **Cadenas**: `normalize_sql_literal` (y la vía rápida P-33) aplica `strip()` a toda cadena; es comportamiento general de `bulk` desde v0.5.0, con test explícito (`tests/unit/test_normalize.py:99`).
- **Efecto real** (round-trip con `DumpOrchestrator` en servidores, sin el arreglo): PostgreSQL y MySQL → tabla en `error`; MariaDB, SQL Server y Oracle → corrupción silenciosa (BIGINT redondeado; en SQL Server `9223372036854775807` → `-9223372036854775808`; DECIMAL a 15–17 dígitos; espacios eliminados).

## FIX
- `dump/orchestrator.py`: `_read_chunks(conn, sql, chunk_size, params)` (nuevo) construye cada chunk con `fetchmany` + `pd.DataFrame(rows, dtype=object)`: cada valor tal como lo da el driver (`int`, `Decimal`, `str`, `None`, `datetime`). Sustituye a `pd.read_sql` en `_load_whole_table` y en los lectores de `_load_in_pk_ranges`. Las `BulkCrud` del volcado y el `ParallelBulkLoader` se crean con `strip_strings=False`.
- `bulk/normalize.py`:
  - `strip_strings` (por defecto `True`) en `dataframe_to_sql_records` / `dataframe_to_sql_columns`, hasta la vía de texto y el camino general.
  - Vía rápida `_is_passthrough` para columnas object cuyos valores `normalize_sql_literal` devuelve sin cambios (`None`, `int`, `bool`, `float`/`Decimal` no NaN, `datetime`/`date`/`time`/`timedelta`, por tipo exacto). **Necesaria para el criterio de rendimiento**: sin ella, leer con `dtype=object` subía `read` + `prep` un 52–65 % (el camino celda a celda); con ella, baja. Salida idéntica al camino general (test parametrizado, incluidos los casos que no la toman).
- `bulk/crud.py`, `bulk/_execution/parallel_loader.py`: parámetro público `strip_strings: bool = True`, propagado a la normalización (INSERT, UPDATE, DELETE, chunks y `generar_sql`).
- `scripts/bench_dump.py`: la fase `read` instrumenta `_read_chunks`; la copia de `prefetch` lo usa.
- Docs: `docs/api/bulk-crud.md`, `docs/api/bulk-parallel.md`; `CHANGELOG.md` (*Fixed* + *Added*).

## Validación
- **Tests**: `tests/unit/dump/test_dump_fidelity.py` (nuevo, 16): `strip_strings` en columnas de texto y mixtas; la vía rápida da la misma salida (valor y tipo) que el camino general en 11 casos; `_read_chunks` (tipos Python, troceo, parámetros); E2E SQLite con BIGINT ±(2^53+1), NULL y cadenas con espacios. El mismo escenario E2E sin el arreglo: `9007199254740992` y `'padded'`; con él, exacto.
  - Adaptados: 21 `patch("pandas.read_sql")` → `patch("util_bbdd.dump.orchestrator._read_chunks")` en `test_orchestrator.py` (era la costura para simular el origen); 2 espías de `dataframe_to_sql_records` aceptan `**kwargs`.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src tests/unit/test_protocol_conformance.py` limpio; `pytest tests/unit`: **4520 passed**.
- **Round-trip en servidores reales** (`zz_pd05` en `dump_src`/`dump_dst`, borrada al terminar; BIGINT 2^53+1, ±(2^63−1) y NULL; DECIMAL(38,10) con 38 dígitos, 27 dígitos y −1E-10; cadenas `'  padded  '`, `' x'`, `'y '`):

| Motor | Sin el arreglo | Con el arreglo |
|---|---|---|
| PostgreSQL | tabla en `error` | **exacto** |
| MySQL | tabla en `error` | **exacto** |
| MariaDB | BIGINT, DECIMAL y cadenas alterados | **exacto** |
| SQL Server (pyodbc) | ídem + `9223372036854775807` → `-9223372036854775808` | **exacto salvo DECIMAL de 38 dígitos** (PD-10) |
| Oracle | BIGINT y DECIMAL redondeados, cadenas recortadas | **exacto** |

- **Rendimiento** (`large`, 3,5M filas, mediana de 3; `results/`; referencia: sesión delta):

| Motor | read + prep antes → después | Total antes → después |
|---|---|---|
| PostgreSQL | 9,86 → 7,55 s (−23 %) | 19,1 → 16,4 s |
| MySQL | 24,63 → 22,81 s (−7 %) | 57,0 → 55,4 s |
| MariaDB | 24,38 → 22,01 s (−10 %) | 52,9 → 49,1 s |
| SQL Server | 15,84 → 13,32 s (−16 %) | ver A/B |
| Oracle | 27,05 → 26,11 s (−3 %) | 57,6 → 53,4 s |
| SQLite (desde PG) | 9,79 → 7,71 s (−21 %) | 21,3 → 20,5 s |

  Criterio (read + prep ≤ +10 %): cumplido en los 6 motores (mejora en todos).
  - **SQL Server, A/B intercalado** (misma ventana, `ab_antes/`, `ab_despues/`): total 68,3 · 66,6 s → 65,9 · 72,8 s; `read` −3 s, `write` +5 s (≈ +10 %): pyodbc con `fast_executemany` convierte `Decimal` más despacio que `float` (microbanco: +13 % en una tabla de 2 columnas). Neto ≈ +3 %, dentro del ruido. La primera comparación (+14 % en total) mezclaba deriva del servidor a lo largo del día.
  - SQLite: `write` ≈ +1 s por la misma razón; total −4 %.

## Hallazgo nuevo: PD-10 (fuera del alcance)
- **SQL Server + `fast_executemany`: un DECIMAL de 38 dígitos significativos se redondea al escribir** (`…678.9012345678` → `…679.0000000000`; 27 dígitos llegan exactos). Aislado: con `insert()` de SQLAlchemy es exacto; con `dialect.fast_executemany = True` (P-18/P-01 de `bulk`) SQLAlchemy omite `setinputsizes` y pyodbc infiere el tipo del parámetro desde el valor. Preexistente e independiente de pandas; afecta también a `bulk` directo. Antes de este arreglo `dump` enviaba `float` (15 dígitos), así que la precisión mejora de 15 a ≥ 27 dígitos. Microbanco: enviar el `Decimal` como `str` cuesta lo mismo que `float` (2,39 frente a 2,30 s por 300K filas); es una vía a estudiar en su propio hotfix.

## AUDIT_CODE
- **Sin cambio para quien usa `bulk` directamente**: `strip_strings=True` por defecto; la vía rápida devuelve los mismos valores y tipos (test). La normalización de columnas numpy/datetime/texto no cambia.
- **Tipos en `dump`**: los valores llegan como los da el driver. `Decimal` en lugar de `float` hacia el destino (exacto; cuesta ≈ +10 % de escritura en SQL Server). Fechas: `datetime` del driver, igual que antes tras `to_pydatetime`. Binarios: `bytes`, que la normalización trata igual que antes.
- **Memoria**: sin cambio (RSS pico igual en los 6 motores; la lectura sigue por chunks).
- **Errores de lectura**: ahora llegan como `SQLAlchemyError` de `conn.execute`, ya capturado en `_load_whole_table` (se mantiene `pd.errors.DatabaseError` en el `except`).
- **Edge cases**: tabla vacía (sin chunks: `bulk_insert_from_chunks` inserta 0 filas); `Decimal('NaN')`, `float('nan')`, `pd.NA`, `pd.Timestamp` y `bytes` no toman la vía rápida y siguen el camino general (test).
- **Compatibilidad**: parámetro nuevo (`strip_strings`) con el comportamiento anterior por defecto. `dump` deja de recortar cadenas: es la corrección pedida, anotada en el CHANGELOG.

## VERSION
- Commit: `fix(dump): copiar los valores del origen sin alterarlos (PD-05)`
- Changelog: *Fixed* (dump) + *Added* (`strip_strings`).
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump]**: no vuelvas a `pd.read_sql` en la carga. Pierde precisión en enteros con NULL y en `Decimal`; `dtype_backend` entrega los `Decimal` como texto. `_read_chunks` (`dtype=object`) es la lectura exacta.
- **[bulk/normalize]**: cualquier columna object nueva de tipos "pasivos" debe pasar por `_is_passthrough`; el camino celda a celda cuesta ~4 veces más.
- **[tests dump]**: para simular el origen, parchea `util_bbdd.dump.orchestrator._read_chunks` (args: `conn, sql, chunk_size, params`).
- **[bench mssql]**: el rendimiento de SQL Server deriva a lo largo de una sesión larga (log de transacciones). Para atribuir diferencias < 15 % haz A/B intercalado en la misma ventana.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- PD-10 (nuevo): DECIMAL de 38 dígitos en SQL Server con `fast_executemany`.
- Resto de la Fase 0: PD-04, PD-06 (SQLite con rangos), PD-07, PD-09.
