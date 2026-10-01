# P-1 · Filtro de OPENJSON por columna — informe

- Cambio: `bulk/_execution/delete_strategies.py`: `_column_fits(values, column_type)` (vías rápidas para columnas de un
  solo tipo; `_fits` como referencia para tipos mezclados y decimales con más decimales que la escala) y `_to_json`;
  se elimina `_json_value`.
- Test: `tests/unit/bulk/test_openjson_column_fits.py` (equivalencia exacta con `_fits`: 13 tipos × 2000 listas
  aleatorias + listas homogéneas + valores sueltos con bordes exactos; JSON idéntico al anterior). Siguen pasando los 27
  tests de dominio del hotfix y los 6 de integración.

## CPU (1M claves en lotes de 20 000, mediana de 3)

| PK | Hotfix (por valor) | P-1 total | Suelo sin filtro (`tolist` + JSON) | Filtro P-1 | Objetivo |
|---|---|---|---|---|---|
| INT | 0,401 s | 0,114 s | 0,036 s | 0,078 s | ≤ 0,10 ✔ |
| VARCHAR(10) | 0,310 s | 0,139 s | 0,050 s | 0,089 s | ≤ 0,10 ✔ |
| NUMERIC(12,2) | 2,059 s | 0,588 s | 0,190 s | 0,398 s | ≤ 0,40 ✔ |

## Banco (SQL Server 2022 + pyodbc, PK entera, mediana de 3; `p1/bench_mssql_final/`)

| DELETE | B-04 (antes del hotfix) | Hotfix | P-1 |
|---|---|---|---|
| 10K | 0,040 s | 0,044 s | 0,034 s |
| 1M | 2,20 s | 2,47 s | **2,17 s** |

## Validación
`ruff`/`mypy` limpios; `pytest` 5912 passed; `tests/integration` 455 passed (pyodbc) y 67 passed con pymssql (`-k mssql`).
