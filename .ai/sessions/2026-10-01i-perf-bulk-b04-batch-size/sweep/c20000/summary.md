# Banco de pruebas bulk

- Fecha: 2026-10-01T10:55:10 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 20000 · repeticiones 3

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
| mariadb | insert | 1,000,000 | baseline | 15.908 | 62,860 |  | 3/0 |  |
| mariadb | update | 1,000,000 | baseline | 20.005 | 49,989 |  | 3/0 |  |
| mariadb | delete | 1,000,000 | baseline | 7.022 | 142,416 |  | 3/0 |  |
| mssql | insert | 1,000,000 | baseline | 13.581 | 73,630 |  | 3/0 |  |
| mssql | update | 1,000,000 | baseline | 21.823 | 45,824 |  | 3/0 |  |
| mssql | delete | 1,000,000 | baseline | 2.192 | 456,100 |  | 3/0 |  |
| mysql | insert | 1,000,000 | baseline | 16.227 | 61,626 |  | 3/0 |  |
| mysql | update | 1,000,000 | baseline | 22.109 | 45,230 |  | 3/0 |  |
| mysql | delete | 1,000,000 | baseline | 7.498 | 133,372 |  | 3/0 |  |
| oracle | insert | 1,000,000 | baseline | 9.624 | 103,903 |  | 3/0 |  |
| oracle | update | 1,000,000 | baseline | 14.651 | 68,253 |  | 3/0 |  |
| oracle | delete | 1,000,000 | baseline | 16.522 | 60,525 |  | 3/0 |  |
| postgresql | insert | 1,000,000 | baseline | 3.530 | 283,310 |  | 3/0 |  |
| postgresql | update | 1,000,000 | baseline | 14.072 | 71,065 |  | 3/0 |  |
| postgresql | delete | 1,000,000 | baseline | 1.671 | 598,301 |  | 3/0 |  |
| sqlite | insert | 1,000,000 | baseline | 6.400 | 156,255 |  | 3/0 |  |
| sqlite | update | 1,000,000 | baseline | 9.734 | 102,734 |  | 3/0 |  |
| sqlite | delete | 1,000,000 | baseline | 2.836 | 352,647 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
