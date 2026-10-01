# Banco de pruebas bulk

- Fecha: 2026-10-01T08:33:42 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 1

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
| mariadb | insert | 1,000,000 | baseline | 15.567 | 64,238 |  | 1/0 |  |
| mariadb | update | 1,000,000 | baseline | 20.771 | 48,143 |  | 1/0 |  |
| mariadb | delete | 1,000,000 | baseline | 6.595 | 151,637 |  | 1/0 |  |
| mssql | insert | 1,000,000 | baseline | 14.129 | 70,776 |  | 1/0 |  |
| mssql | update | 1,000,000 | baseline | 22.423 | 44,597 |  | 1/0 |  |
| mssql | delete | 1,000,000 | baseline | 2.713 | 368,528 |  | 1/0 |  |
| mysql | insert | 1,000,000 | baseline | 16.744 | 59,725 |  | 1/0 |  |
| mysql | update | 1,000,000 | baseline | 23.090 | 43,309 |  | 1/0 |  |
| mysql | delete | 1,000,000 | baseline | 7.091 | 141,022 |  | 1/0 |  |
| oracle | insert | 1,000,000 | baseline | 10.921 | 91,562 |  | 1/0 |  |
| oracle | update | 1,000,000 | baseline | 14.915 | 67,048 |  | 1/0 |  |
| oracle | delete | 1,000,000 | baseline | 16.388 | 61,019 |  | 1/0 |  |
| postgresql | insert | 1,000,000 | baseline | 4.439 | 225,281 |  | 1/0 |  |
| postgresql | update | 1,000,000 | baseline | 10.893 | 91,805 |  | 1/0 |  |
| postgresql | delete | 1,000,000 | baseline | 1.947 | 513,505 |  | 1/0 |  |
| sqlite | insert | 1,000,000 | baseline | 6.619 | 151,092 |  | 1/0 |  |
| sqlite | update | 1,000,000 | baseline | 9.893 | 101,086 |  | 1/0 |  |
| sqlite | delete | 1,000,000 | baseline | 2.785 | 359,002 |  | 1/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
