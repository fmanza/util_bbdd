# Banco de pruebas bulk

- Fecha: 2026-09-24T01:58:37 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 3

| Motor | Servidor | Driver |
|---|---|---|
| mssql | 16.0.4295.3 | mssql+pyodbc |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mssql | insert | 1,000 | baseline | 0.439 | 2,278 |  | 3/0 |  |
| mssql | insert | 1,000 | p01-mssql-engine-fast-executemany | 0.038 | 26,316 | 11.55× | 3/0 |  |
| mssql | insert | 10,000 | baseline | 2.673 | 3,741 |  | 3/0 |  |
| mssql | insert | 10,000 | p01-mssql-engine-fast-executemany | 0.226 | 44,248 | 11.83× | 3/0 |  |
| mssql | insert | 100,000 | baseline | 26.034 | 3,841 |  | 3/0 |  |
| mssql | insert | 100,000 | p01-mssql-engine-fast-executemany | 2.181 | 45,842 | 11.93× | 3/0 |  |
| mssql | update | 1,000 | baseline | — | — |  | 0/3 | DBAPIError: (pyodbc.Error) ('HY104', '[HY104] [Microsoft][ODBC Driver 18 for SQL Server]Invalid precision value (0) (SQL |
| mssql | update | 1,000 | p01-mssql-engine-fast-executemany | 0.042 | 23,981 |  | 3/0 |  |
| mssql | update | 10,000 | baseline | — | — |  | 0/3 | DBAPIError: (pyodbc.Error) ('HY104', '[HY104] [Microsoft][ODBC Driver 18 for SQL Server]Invalid precision value (0) (SQL |
| mssql | update | 10,000 | p01-mssql-engine-fast-executemany | 0.338 | 29,630 |  | 3/0 |  |
| mssql | update | 100,000 | baseline | — | — |  | 0/3 | DBAPIError: (pyodbc.Error) ('HY104', '[HY104] [Microsoft][ODBC Driver 18 for SQL Server]Invalid precision value (0) (SQL |
| mssql | update | 100,000 | p01-mssql-engine-fast-executemany | 2.989 | 33,459 |  | 3/0 |  |
| mssql | delete | 1,000 | p01-mssql-engine-fast-executemany | 0.087 | 11,481 |  | 3/0 |  |
| mssql | delete | 10,000 | p01-mssql-engine-fast-executemany | — | — |  | 0/3 | DBAPIError: (pyodbc.Error) ('07002', '[07002] [Microsoft][ODBC Driver 18 for SQL Server]COUNT field incorrect or syntax  |
| mssql | delete | 100,000 | p01-mssql-engine-fast-executemany | — | — |  | 0/3 | DBAPIError: (pyodbc.Error) ('07002', '[07002] [Microsoft][ODBC Driver 18 for SQL Server]COUNT field incorrect or syntax  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
