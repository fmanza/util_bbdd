# Banco de pruebas bulk

- Fecha: 2026-09-24T02:00:28 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 1

| Motor | Servidor | Driver |
|---|---|---|
| mssql | 16.0.4295.3 | mssql+pyodbc |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mssql | insert | 1,000,000 | baseline | 245.524 | 4,073 |  | 1/0 |  |
| mssql | insert | 1,000,000 | p01-mssql-engine-fast-executemany | 20.359 | 49,118 | 12.06× | 1/0 |  |
| mssql | update | 1,000,000 | baseline | — | — |  | 0/1 | DBAPIError: (pyodbc.Error) ('HY104', '[HY104] [Microsoft][ODBC Driver 18 for SQL Server]Invalid precision value (0) (SQL |
| mssql | update | 1,000,000 | p01-mssql-engine-fast-executemany | 29.785 | 33,574 |  | 1/0 |  |
| mssql | delete | 1,000,000 | p01-mssql-engine-fast-executemany | — | — |  | 0/1 | DBAPIError: (pyodbc.Error) ('07002', '[07002] [Microsoft][ODBC Driver 18 for SQL Server]COUNT field incorrect or syntax  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
