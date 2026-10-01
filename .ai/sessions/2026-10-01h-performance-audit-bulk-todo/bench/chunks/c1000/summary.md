# Banco de pruebas bulk

- Fecha: 2026-10-01T04:10:02 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 1000 · repeticiones 1

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
| mariadb | insert | 1,000,000 | baseline | 19.029 | 52,551 |  | 1/0 |  |
| mariadb | update | 1,000,000 | baseline | 24.935 | 40,104 |  | 1/0 |  |
| mariadb | delete | 1,000,000 | baseline | 7.790 | 128,375 |  | 1/0 |  |
| mssql | insert | 1,000,000 | baseline | 17.149 | 58,312 |  | 1/0 |  |
| mssql | update | 1,000,000 | baseline | 25.571 | 39,107 |  | 1/0 |  |
| mssql | delete | 1,000,000 | baseline | 9.865 | 101,365 |  | 1/0 |  |
| mysql | insert | 1,000,000 | baseline | 17.547 | 56,991 |  | 1/0 |  |
| mysql | update | 1,000,000 | baseline | 26.677 | 37,486 |  | 1/0 |  |
| mysql | delete | 1,000,000 | baseline | 8.230 | 121,504 |  | 1/0 |  |
| oracle | insert | 1,000,000 | baseline | 10.854 | 92,129 |  | 1/0 |  |
| oracle | update | 1,000,000 | baseline | 16.871 | 59,273 |  | 1/0 |  |
| oracle | delete | 1,000,000 | baseline | 18.143 | 55,118 |  | 1/0 |  |
| postgresql | insert | 1,000,000 | baseline | 8.034 | 124,468 |  | 1/0 |  |
| postgresql | update | 1,000,000 | baseline | 26.589 | 37,610 |  | 1/0 |  |
| postgresql | delete | 1,000,000 | baseline | 2.937 | 340,495 |  | 1/0 |  |
| sqlite | insert | 1,000,000 | baseline | 7.202 | 138,850 |  | 1/0 |  |
| sqlite | update | 1,000,000 | baseline | 10.566 | 94,642 |  | 1/0 |  |
| sqlite | delete | 1,000,000 | baseline | 3.833 | 260,899 |  | 1/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
