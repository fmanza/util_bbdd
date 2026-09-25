# Validation report — serialización SQL de bulk (P-31, P-32, P-33)

<!-- arquetipo: informativo-libre -->

- **Fecha**: 2026-09-25 · **Rama**: develop · **Flujo**: `/refactor` sobre [PLAN](./PLAN.md) / [AUDIT_PLAN](./AUDIT_PLAN.md)
- **Entorno**: Windows 11, Python 3.14.2, SQLAlchemy 2.0.50, pandas 3.0.3 (dtype `str` respaldada por **pyarrow
  25.0.1**, instalado en esta sesión), numpy 2.4.6
- **Herramienta**: `scripts/bench_sqlgen.py` (nuevo). CSV y salidas de consola en `baseline/` y `validation/`.

> El baseline se tomó **con pyarrow ya instalado**. Con él, la normalización de texto era más lenta que en la
> auditoría (4,1 frente a 2,8 µs/fila), así que las cifras de la auditoría y las de este informe no se mezclan.

## Extremo a extremo — API pública, SQLite, 1M filas

| Operación | Baseline | Final | Mejora |
|---|---:|---:|---:|
| INSERT | 12,63 s | 6,09 s | **−52 %** |
| UPDATE | 12,99 s | 6,64 s | **−49 %** |
| DELETE | 2,14 s | 1,89 s | −12 % |

Tamaño de los ficheros sin cambios: 221,1 / 226,1 / 69,9 MB.

## Por paso — INSERT, 100K filas, mediana de 3 (µs/fila)

| Dialecto | Etapa | Baseline | P-33 | P-31 | P-32 | Total |
|---|---|---:|---:|---:|---:|---:|
| sqlite | normalización | 4,13 | 1,63 | 1,57 | 1,53 | −63 % |
| sqlite | render | 8,26 | 8,44 | 6,54 | 4,01 | −51 % |
| postgresql | normalización | 4,19 | 1,57 | 1,55 | 1,49 | −64 % |
| postgresql | render | 8,99 | 9,12 | 7,07 | 7,01 | −22 % |
| mysql | normalización | 4,17 | 1,61 | 1,58 | 1,61 | −61 % |
| mysql | render | 8,97 | 8,97 | 7,11 | 7,02 | −22 % |
| oracle | normalización | 4,27 | 1,74 | 1,69 | 1,65 | −61 % |
| oracle | render | 7,57 | 7,55 | 5,80 | 3,45 | −54 % |
| mssql | normalización | 4,12 | 1,61 | 1,57 | 1,54 | −63 % |
| mssql | render | 7,56 | 7,50 | 5,72 | 3,40 | −55 % |

La escritura no cambia (0,30–0,34 µs/fila). UPDATE sigue la misma proporción. DELETE: render de −27 a −28 %, con la
normalización intacta (DELETE no usa `dataframe_to_sql_records`).

**C3** (≥ 5 % por paso en su métrica): P-33 −61 % en normalización; P-31 −21 a −24 % en render; P-32 −39 a −41 % en
render en sqlite/oracle/mssql (en PG/MySQL no aplica, por diseño). ✅

## Equivalencia de salida (C1)

| Comprobación | Resultado |
|---|---|
| SHA-256 de los ficheros INSERT/UPDATE/DELETE, 100K filas × 5 dialectos: código de `HEAD` (worktree) frente al nuevo | ✅ 15/15 idénticos |
| `tests/unit/bulk/test_generate_sql_template.py`: 8 drivers, contra compilación por fila, sin cambiar ninguna expectativa | ✅ |
| `tests/unit/bulk/test_dataframe_to_sql_records.py`: igualdad de valor y tipo, 30 dtypes (6 nuevos, con `string[pyarrow]`) | ✅ |
| Tests nuevos: filas de plantilla y de camino anterior intercaladas; activación de P-32 por dialecto | ✅ 16 casos |

## Suite y calidad

| Comando | Resultado |
|---|---|
| `python -m ruff format --check src tests scripts` | 616 ficheros sin cambios |
| `python -m ruff check src tests scripts` | All checks passed |
| `python -m mypy src tests/unit/test_protocol_conformance.py` | Sin errores (342 ficheros) |
| `python -m pytest` | 4896 passed, 160 skipped (integración sin servidor; ninguno en `tests/unit/bulk`) |

## Objetivos del roadmap

| Métrica | Objetivo | Resultado |
|---|---:|---:|
| INSERT 1M SQLite | ≤ 7,5 s | 6,09 s ✅ |
| UPDATE 1M SQLite | ≤ 7,8 s | 6,64 s ✅ |
| Render INSERT sqlite / oracle / mssql | ≤ 5,5 / 5,0 / 5,0 µs | 4,01 / 3,45 / 3,40 ✅ |
| Render INSERT pg / mysql | ≤ 7,5 µs | 7,01 / 7,02 ✅ |
| Normalización de texto | ≤ 0,15 µs/celda | No medida por celda. Normalización total de la fila (10 columnas, 3 de texto): 4,13 → 1,53 µs ✅ |
| Diferencias de salida | 0 | 0 ✅ |
