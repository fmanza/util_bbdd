# Banco de pruebas bulk

- Fecha: 2026-10-01T10:44:38 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 3

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
| mariadb | insert | 1,000,000 | baseline | 15.483 | 64,586 |  | 3/0 |  |
| mariadb | update | 1,000,000 | baseline | 21.091 | 47,413 |  | 3/0 |  |
| mariadb | delete | 1,000,000 | baseline | 6.711 | 149,009 |  | 3/0 |  |
| mssql | insert | 1,000,000 | baseline | 14.238 | 70,234 |  | 3/0 |  |
| mssql | update | 1,000,000 | baseline | 22.547 | 44,352 |  | 3/0 |  |
| mssql | delete | 1,000,000 | baseline | 2.743 | 364,551 |  | 3/0 |  |
| mysql | insert | 1,000,000 | baseline | 15.774 | 63,396 |  | 3/0 |  |
| mysql | update | 1,000,000 | baseline | 22.434 | 44,576 |  | 3/0 |  |
| mysql | delete | 1,000,000 | baseline | 7.171 | 139,454 |  | 3/0 |  |
| oracle | insert | 1,000,000 | baseline | 9.589 | 104,287 |  | 3/0 |  |
| oracle | update | 1,000,000 | baseline | 15.030 | 66,535 |  | 3/0 |  |
| oracle | delete | 1,000,000 | baseline | 16.776 | 59,607 |  | 3/0 |  |
| postgresql | insert | 1,000,000 | baseline | 4.045 | 247,249 |  | 3/0 |  |
| postgresql | update | 1,000,000 | baseline | 10.768 | 92,870 |  | 3/0 |  |
| postgresql | delete | 1,000,000 | baseline | 1.859 | 537,895 |  | 3/0 |  |
| sqlite | insert | 1,000,000 | baseline | 6.574 | 152,121 |  | 3/0 |  |
| sqlite | update | 1,000,000 | baseline | 9.520 | 105,044 |  | 3/0 |  |
| sqlite | delete | 1,000,000 | baseline | 2.796 | 357,590 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
