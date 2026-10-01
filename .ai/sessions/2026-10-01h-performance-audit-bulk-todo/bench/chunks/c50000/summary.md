# Banco de pruebas bulk

- Fecha: 2026-10-01T04:18:33 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 50000 · repeticiones 1

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
| mariadb | insert | 1,000,000 | baseline | 16.600 | 60,242 |  | 1/0 |  |
| mariadb | update | 1,000,000 | baseline | 22.868 | 43,728 |  | 1/0 |  |
| mariadb | delete | 1,000,000 | baseline | 9.907 | 100,935 |  | 1/0 |  |
| mssql | insert | 1,000,000 | baseline | 13.364 | 74,829 |  | 1/0 |  |
| mssql | update | 1,000,000 | baseline | 21.439 | 46,645 |  | 1/0 |  |
| mssql | delete | 1,000,000 | baseline | 8.564 | 116,764 |  | 1/0 |  |
| mysql | insert | 1,000,000 | baseline | 18.844 | 53,068 |  | 1/0 |  |
| mysql | update | 1,000,000 | baseline | 21.447 | 46,626 |  | 1/0 |  |
| mysql | delete | 1,000,000 | baseline | 12.010 | 83,264 |  | 1/0 |  |
| oracle | insert | 1,000,000 | baseline | 9.562 | 104,585 |  | 1/0 |  |
| oracle | update | 1,000,000 | baseline | 15.373 | 65,048 |  | 1/0 |  |
| oracle | delete | 1,000,000 | baseline | 15.959 | 62,662 |  | 1/0 |  |
| postgresql | insert | 1,000,000 | baseline | 4.852 | 206,096 |  | 1/0 |  |
| postgresql | update | 1,000,000 | baseline | 25.021 | 39,967 |  | 1/0 |  |
| postgresql | delete | 1,000,000 | baseline | 1.855 | 539,025 |  | 1/0 |  |
| sqlite | insert | 1,000,000 | baseline | 6.737 | 148,436 |  | 1/0 |  |
| sqlite | update | 1,000,000 | baseline | 12.194 | 82,011 |  | 1/0 |  |
| sqlite | delete | 1,000,000 | baseline | 3.496 | 286,066 |  | 1/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
