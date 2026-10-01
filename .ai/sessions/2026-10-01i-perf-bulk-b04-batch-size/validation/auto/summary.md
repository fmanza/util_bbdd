# Banco de pruebas bulk

- Fecha: 2026-10-01T11:33:37 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size auto · repeticiones 3

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
| mariadb | insert | 1,000,000 | baseline | 15.450 | 64,726 |  | 3/0 |  |
| mariadb | update | 1,000,000 | baseline | 21.327 | 46,888 |  | 3/0 |  |
| mariadb | delete | 1,000,000 | baseline | 6.783 | 147,434 |  | 3/0 |  |
| mssql | insert | 1,000,000 | baseline | 14.043 | 71,207 |  | 3/0 |  |
| mssql | update | 1,000,000 | baseline | 22.232 | 44,981 |  | 3/0 |  |
| mssql | delete | 1,000,000 | baseline | 2.202 | 454,133 |  | 3/0 |  |
| mysql | insert | 1,000,000 | baseline | 15.767 | 63,424 |  | 3/0 |  |
| mysql | update | 1,000,000 | baseline | 22.649 | 44,151 |  | 3/0 |  |
| mysql | delete | 1,000,000 | baseline | 7.137 | 140,115 |  | 3/0 |  |
| oracle | insert | 1,000,000 | baseline | 9.259 | 107,998 |  | 3/0 |  |
| oracle | update | 1,000,000 | baseline | 14.949 | 66,895 |  | 3/0 |  |
| oracle | delete | 1,000,000 | baseline | 16.512 | 60,560 |  | 3/0 |  |
| postgresql | insert | 1,000,000 | baseline | 3.452 | 289,679 |  | 3/0 |  |
| postgresql | update | 1,000,000 | baseline | 10.939 | 91,418 |  | 3/0 |  |
| postgresql | delete | 1,000,000 | baseline | 1.658 | 602,991 |  | 3/0 |  |
| sqlite | insert | 1,000,000 | baseline | 6.643 | 150,537 |  | 3/0 |  |
| sqlite | update | 1,000,000 | baseline | 10.146 | 98,562 |  | 3/0 |  |
| sqlite | delete | 1,000,000 | baseline | 2.798 | 357,411 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
