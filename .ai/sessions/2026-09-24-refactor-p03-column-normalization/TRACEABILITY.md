# TRACEABILITY

## Session metadata
- id: 2026-09-24-refactor-p03-column-normalization
- fecha: 2026-09-24
- rama: develop
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Continúo con P-03, que beneficia a todos los motores?")

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-03, prototipo 4,6×)
- `src/util_bbdd/bulk/normalize.py`, `src/util_bbdd/bulk/crud.py`
- pandas 3.0.3 `core/methods/to_dict.py` (cómo produce `to_dict(orient="records")` los valores) y `core/dtypes/cast.py::maybe_box_native`

## AI output summary
- **Estudio previo de la referencia**:
  - `to_dict(orient="records")` itera con `itertuples` (escalares Python en columnas numpy; `Timestamp`/`NaT` en fechas).
  - Aplica `maybe_box_native` a las columnas object **y** de tipo extensión (`Int64`, `boolean`, `str`, `category`, fechas con zona).
- **Diseño** (`dataframe_to_sql_records` en `normalize.py`):
  - En bloque: numpy int/uint/bool (`tolist`), float (`tolist` + NaN → None) y fechas con y sin zona (`array.to_pydatetime` + NaT → None).
  - Resto: mismos pasos que la referencia (iterar la serie, `maybe_box_native` en object/extensión, `normalize_sql_literal`).
  - `maybe_box_native` se importa de `pandas.core.dtypes.cast` (privado, no está en pandas-stubs). Si pandas lo cambiara, el test de equivalencia lo detectaría.
- **Equivalencia estricta** (`tests/unit/bulk/test_dataframe_to_sql_records.py`, 31 tests):
  - Mismas claves, orden, valores y **tipo Python** que `normalize_records_for_sql(df.to_dict("records"))`.
  - 25 dtypes: int/uint/float32/NaN/inf, bool, fechas ns/s/tz con cambios de horario/UTC, timedelta, Int64/Float64/boolean, `str`/`string[python]`, `category`, object mixto, escalares numpy y `datetime64` en object, bytes UTF-8, Decimal (incl. NaN), fechas mixtas.
  - Más nombres de columna no-str y duplicados, DataFrame vacío/sin filas/sin columnas/índice duplicado, y porción de un DataFrame.
  - Corregido durante el desarrollo: con filas pero sin columnas, `to_dict` devuelve `[]` (había supuesto `[{}, …]`).
- **crud.py**: los 3 puntos (`bulk_insert_from_df`, `bulk_insert_from_chunks`, `bulk_update_from_df`) usan `dataframe_to_sql_records`. `restore_binary_values` (P-21) sigue a continuación. El UPDATE sigue preparando todas las columnas del DataFrame, como antes (P-09 fuera de alcance).
- **Medición**:
  - La primera A/B de 1M con servidores (una repetición, `git stash` antes/después) **no era fiable**: la ruta anterior salió mucho más lenta que la línea base de la mañana (SQLite INSERT 24,3 s frente a 13,7 s). Descartada y no publicada.
  - Microbenchmark de preparación, alternado, 5 repeticiones, salida idéntica verificada: 100K 0,87 → 0,29 s (3,0×); **1M 8,58 → 2,95 s (2,9×)**.
  - Extremo a extremo en SQLite (sin servidor), 1M, alternado, medianas de 3: **INSERT 13,79 → 8,35 s (1,65×)**, **UPDATE 17,05 → 11,65 s (1,46×)**. La mediana "antes" coincide con la línea base de la mañana.
  - El ahorro (~5,6 s por millón de filas) es CPU de Python, igual en todos los motores. No se publican cifras por motor de servidor porque la medición con servidores fue ruidosa.
- **Validación**:
  - `ruff check src tests` y `mypy src` limpios.
  - Suite: 4531 passed / 58 skipped.
  - Integración: 6 motores 42 passed / 18 skipped; SQL Server con pyodbc 10 passed; `mariadbconnector` 10 passed.

## AUDIT_CODE
- Regresiones potenciales: ninguna observable. El resultado es idéntico por construcción en la vía de respaldo y por test en las vías en bloque.
- Dependencia privada: `maybe_box_native` (pandas interno). Riesgo ante una actualización de pandas; mitigado con el test de equivalencia.
- Contratos públicos: `normalize_records_for_sql`, `normalize_sql_literal` y `bulk/__init__` sin cambios. `dataframe_to_sql_records` no se exporta en `bulk/__init__`.
- Cobertura: preservada, más 31 tests.
- Tipado: mypy limpio (un `type: ignore[attr-defined]` justificado).

## Directrices para Futuras IAs
- **[bench]**: con los 5 servidores en Docker, una A/B de una sola repetición en tandas separadas no es fiable. Para cambios de CPU en Python, mide la fase aislada (microbenchmark alternado) y el extremo a extremo en SQLite con repeticiones alternadas.
- **[bulk/normalización]**: cualquier nueva vía en bloque en `_normalize_column` debe añadirse a la matriz de `test_dataframe_to_sql_records.py`, que compara también el tipo Python.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
