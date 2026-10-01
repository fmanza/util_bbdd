# Banco de pruebas bulk

- Fecha: 2026-10-01T04:14:31 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 20000 · repeticiones 1

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
| mariadb | insert | 1,000,000 | baseline | 20.117 | 49,710 |  | 1/0 |  |
| mariadb | update | 1,000,000 | baseline | 19.999 | 50,002 |  | 1/0 |  |
| mariadb | delete | 1,000,000 | baseline | 7.066 | 141,531 |  | 1/0 |  |
| mssql | insert | 1,000,000 | baseline | 13.738 | 72,792 |  | 1/0 |  |
| mssql | update | 1,000,000 | baseline | 21.909 | 45,644 |  | 1/0 |  |
| mssql | delete | 1,000,000 | baseline | 8.563 | 116,777 |  | 1/0 |  |
| mysql | insert | 1,000,000 | baseline | 17.744 | 56,356 |  | 1/0 |  |
| mysql | update | 1,000,000 | baseline | 22.024 | 45,405 |  | 1/0 |  |
| mysql | delete | 1,000,000 | baseline | 7.159 | 139,682 |  | 1/0 |  |
| oracle | insert | 1,000,000 | baseline | 9.736 | 102,710 |  | 1/0 |  |
| oracle | update | 1,000,000 | baseline | 15.117 | 66,152 |  | 1/0 |  |
| oracle | delete | 1,000,000 | baseline | 17.907 | 55,843 |  | 1/0 |  |
| postgresql | insert | 1,000,000 | baseline | 4.836 | 206,765 |  | 1/0 |  |
| postgresql | update | 1,000,000 | baseline | 26.019 | 38,434 |  | 1/0 |  |
| postgresql | delete | 1,000,000 | baseline | 1.771 | 564,685 |  | 1/0 |  |
| sqlite | insert | 1,000,000 | baseline | 6.697 | 149,318 |  | 1/0 |  |
| sqlite | update | 1,000,000 | baseline | 10.961 | 91,228 |  | 1/0 |  |
| sqlite | delete | 1,000,000 | baseline | 2.857 | 350,030 |  | 1/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
