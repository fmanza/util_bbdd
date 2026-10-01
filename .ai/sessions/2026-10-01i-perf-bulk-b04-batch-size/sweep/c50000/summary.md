# Banco de pruebas bulk

- Fecha: 2026-10-01T11:05:43 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 50000 · repeticiones 3

| Motor | Servidor | Driver |
|---|---|---|
| sqlite | 3.50.4 | sqlite |
| postgresql | 17.11 | postgresql+psycopg |
| mysql | 8.4.11 | mysql+pymysql |
| mariadb | 11.4.13 | mariadb+pymysql |
| mssql | 16.0.4295.3 | mssql+pyodbc |
| oracle | 23.26.3.0.0 | oracle+oracledb |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mariadb | insert | 1,000,000 | baseline | 14.583 | 68,572 |  | 3/0 |  |
| mariadb | update | 1,000,000 | baseline | 23.122 | 43,249 |  | 3/0 |  |
| mariadb | delete | 1,000,000 | baseline | 9.499 | 105,275 |  | 3/0 |  |
| mssql | insert | 1,000,000 | baseline | 13.235 | 75,558 |  | 3/0 |  |
| mssql | update | 1,000,000 | baseline | 21.547 | 46,409 |  | 3/0 |  |
| mssql | delete | 1,000,000 | baseline | 3.449 | 289,964 |  | 3/0 |  |
| mysql | insert | 1,000,000 | baseline | 16.278 | 61,433 |  | 3/0 |  |
| mysql | update | 1,000,000 | baseline | 21.682 | 46,122 |  | 3/0 |  |
| mysql | delete | 1,000,000 | baseline | 11.817 | 84,623 |  | 3/0 |  |
| oracle | insert | 1,000,000 | baseline | 9.437 | 105,972 |  | 3/0 |  |
| oracle | update | 1,000,000 | baseline | 15.184 | 65,860 |  | 3/0 |  |
| oracle | delete | 1,000,000 | baseline | 15.918 | 62,823 |  | 3/0 |  |
| postgresql | insert | 1,000,000 | baseline | 3.260 | 306,720 |  | 3/0 |  |
| postgresql | update | 1,000,000 | baseline | 12.210 | 81,901 |  | 3/0 |  |
| postgresql | delete | 1,000,000 | baseline | 2.005 | 498,753 |  | 3/0 |  |
| sqlite | insert | 1,000,000 | baseline | 6.591 | 151,727 |  | 3/0 |  |
| sqlite | update | 1,000,000 | baseline | 10.490 | 95,326 |  | 3/0 |  |
| sqlite | delete | 1,000,000 | baseline | 2.587 | 386,623 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
