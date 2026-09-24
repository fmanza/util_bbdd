# Banco de pruebas bulk

- Fecha: 2026-09-24T00:54:50 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 1

| Motor | Servidor | Driver |
|---|---|---|
| sqlite | 3.50.4 | sqlite |
| postgresql | 17.11 | postgresql+psycopg |
| mysql | 8.4.11 | mysql+pymysql |
| mariadb | 11.4.13 | mariadb+pymysql |
| mssql | 16.0.4295.3 | mssql+pymssql |
| oracle | 23.26.3.0.0 | oracle+oracledb |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mariadb | insert | 1,000,000 | baseline | 50.218 | 19,913 |  | 1/0 |  |
| mariadb | insert | 1,000,000 | p02-mysql-executemany | 24.533 | 40,761 | 2.05× | 1/0 |  |
| mariadb | update | 1,000,000 | baseline | 338.950 | 2,950 |  | 1/0 |  |
| mariadb | update | 1,000,000 | p02-mysql-executemany | 342.993 | 2,916 | 0.99× | 1/0 |  |
| mariadb | delete | 1,000,000 | baseline | 14.960 | 66,845 |  | 1/0 |  |
| mariadb | delete | 1,000,000 | p02-mysql-executemany | 15.412 | 64,885 | 0.97× | 1/0 |  |
| mssql | insert | 1,000,000 | baseline | 376.447 | 2,656 |  | 1/0 |  |
| mssql | update | 1,000,000 | baseline | 556.064 | 1,798 |  | 1/0 |  |
| mssql | delete | 1,000,000 | baseline | 45.571 | 21,944 |  | 1/0 |  |
| mysql | insert | 1,000,000 | baseline | 50.774 | 19,695 |  | 1/0 |  |
| mysql | insert | 1,000,000 | p02-mysql-executemany | 26.721 | 37,423 | 1.90× | 1/0 |  |
| mysql | update | 1,000,000 | baseline | 378.547 | 2,642 |  | 1/0 |  |
| mysql | update | 1,000,000 | p02-mysql-executemany | 380.630 | 2,627 | 0.99× | 1/0 |  |
| mysql | delete | 1,000,000 | baseline | 15.691 | 63,729 |  | 1/0 |  |
| mysql | delete | 1,000,000 | p02-mysql-executemany | 16.016 | 62,439 | 0.98× | 1/0 |  |
| oracle | insert | 1,000,000 | baseline | 24.456 | 40,890 |  | 1/0 |  |
| oracle | update | 1,000,000 | baseline | 28.279 | 35,362 |  | 1/0 |  |
| oracle | delete | 1,000,000 | baseline | 23.427 | 42,686 |  | 1/0 |  |
| postgresql | insert | 1,000,000 | baseline | 20.108 | 49,732 |  | 1/0 |  |
| postgresql | update | 1,000,000 | baseline | 40.537 | 24,669 |  | 1/0 |  |
| postgresql | delete | 1,000,000 | baseline | 28.186 | 35,479 |  | 1/0 |  |
| sqlite | insert | 1,000,000 | baseline | 13.698 | 73,004 |  | 1/0 |  |
| sqlite | update | 1,000,000 | baseline | 17.035 | 58,704 |  | 1/0 |  |
| sqlite | delete | 1,000,000 | baseline | 2.830 | 353,332 |  | 1/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
