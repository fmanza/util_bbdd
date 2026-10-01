# Banco de pruebas bulk

- Fecha: 2026-10-01T14:21:22 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size auto · repeticiones 3

| Motor | Servidor | Driver |
|---|---|---|
| mssql | 16.0.4295.3 | mssql+pyodbc |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mssql | insert | 10,000 | baseline | 0.155 | 64,516 |  | 3/0 |  |
| mssql | insert | 1,000,000 | baseline | 14.095 | 70,948 |  | 3/0 |  |
| mssql | delete | 10,000 | baseline | 0.044 | 225,734 |  | 3/0 |  |
| mssql | delete | 1,000,000 | baseline | 2.474 | 404,204 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
