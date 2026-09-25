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

## Adenda — P-34 y P-35 (misma fecha, después del hotfix dde13b2)

**P-35 (plantilla entre bloques)**: medida y descartada. Construir la plantilla cuesta 0,16–0,19 ms por bloque de 5000
filas: entre el 0,45 % y el 1,06 % del render, por debajo del umbral del 2 % del PLAN.

**P-34 (bloques por columnas)**: `SqlColumns` + `dataframe_to_sql_columns`. `BulkCrud` los usa al generar el SQL de
INSERT y UPDATE; la ejecución real y DELETE no cambian. El banco (`scripts/bench_sqlgen.py`) mide ahora ese mismo camino.

| 100K filas, total (s) | Paso 3 (P-32) | P-34 | Mejora |
|---|---:|---:|---:|
| sqlite INSERT / UPDATE | 0,59 / 0,66 | 0,50 / 0,55 | −15 % / −17 % |
| oracle INSERT / UPDATE | 0,54 / 0,60 | 0,44 / 0,48 | −19 % / −20 % |
| mssql INSERT / UPDATE | 0,53 / 0,58 | 0,42 / 0,48 | −21 % / −17 % |
| postgresql INSERT / UPDATE | 0,88 / 0,93 | 0,81 / 0,84 | −8 % / −10 % |
| mysql INSERT / UPDATE | 0,89 / 0,94 | 0,80 / 0,84 | −10 % / −11 % |

Normalización: de 1,5–1,7 a 0,83–0,87 µs/fila (ya no se construye el diccionario de cada fila).

**E2E, SQLite, 1M filas** (`validation/e2e_1m_p34.txt`):

| Operación | Baseline de la sesión | Tras P-31/32/33 | Tras P-34 |
|---|---:|---:|---:|
| INSERT | 12,63 s | 6,09 s | **4,91 s** (−61 % total) |
| UPDATE | 12,99 s | 6,64 s | **5,36 s** (−59 % total) |
| DELETE | 2,14 s | 1,89 s | 1,89 s |

**Equivalencia**: SHA-256 idéntico entre `HEAD` (dde13b2) y P-34 en 15 ficheros. Son 5 generados de extremo a extremo
con `BulkCrud` en SQLite (INSERT, UPDATE, DELETE y una tabla con binarios UTF-8, no UTF-8 y NULL) y 10 generados con
los helpers por dialecto (INSERT y UPDATE × 5). Tests nuevos: `SqlColumns` genera lo mismo que los registros en los 8
drivers, con y sin binarios; clave ausente en el bloque → camino anterior; `SqlColumns` equivale a la lista de
registros (claves repetidas, índices negativos, cortes, sin columnas).

**Suite**: ruff y mypy en verde; `pytest` 4938 passed, 165 skipped (integración sin servidor).
