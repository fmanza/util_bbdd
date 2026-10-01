# Banco de pruebas bulk

- Fecha: 2026-10-01T15:00:24 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size auto · repeticiones 3

| Motor | Servidor | Driver |
|---|---|---|
| mssql | 16.0.4295.3 | mssql+pyodbc |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mssql | insert | 10,000 | baseline | 0.156 | 64,062 |  | 3/0 |  |
| mssql | insert | 1,000,000 | baseline | 13.883 | 72,028 |  | 3/0 |  |
| mssql | delete | 10,000 | baseline | 0.035 | 283,286 |  | 3/0 |  |
| mssql | delete | 1,000,000 | baseline | 2.210 | 452,468 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
