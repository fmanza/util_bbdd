# Banco de pruebas bulk

- Fecha: 2026-10-01T08:32:20 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 3

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
| mariadb | insert | 1,000 | baseline | 0.044 | 22,472 |  | 3/0 |  |
| mariadb | insert | 10,000 | baseline | 0.286 | 34,904 |  | 3/0 |  |
| mariadb | insert | 100,000 | baseline | 1.608 | 62,193 |  | 3/0 |  |
| mariadb | update | 1,000 | baseline | 0.028 | 35,461 |  | 3/0 |  |
| mariadb | update | 10,000 | baseline | 0.209 | 47,801 |  | 3/0 |  |
| mariadb | update | 100,000 | baseline | 2.103 | 47,558 |  | 3/0 |  |
| mariadb | delete | 1,000 | baseline | 0.010 | 97,087 |  | 3/0 |  |
| mariadb | delete | 10,000 | baseline | 0.063 | 158,730 |  | 3/0 |  |
| mariadb | delete | 100,000 | baseline | 0.716 | 139,665 |  | 3/0 |  |
| mssql | insert | 1,000 | baseline | 0.030 | 33,003 |  | 3/0 |  |
| mssql | insert | 10,000 | baseline | 0.157 | 63,898 |  | 3/0 |  |
| mssql | insert | 100,000 | baseline | 1.480 | 67,577 |  | 3/0 |  |
| mssql | update | 1,000 | baseline | 0.043 | 23,095 |  | 3/0 |  |
| mssql | update | 10,000 | baseline | 0.227 | 43,975 |  | 3/0 |  |
| mssql | update | 100,000 | baseline | 2.310 | 43,294 |  | 3/0 |  |
| mssql | delete | 1,000 | baseline | 0.014 | 70,922 |  | 3/0 |  |
| mssql | delete | 10,000 | baseline | 0.040 | 250,000 |  | 3/0 |  |
| mssql | delete | 100,000 | baseline | 0.354 | 282,486 |  | 3/0 |  |
| mysql | insert | 1,000 | baseline | 0.044 | 22,779 |  | 3/0 |  |
| mysql | insert | 10,000 | baseline | 0.284 | 35,211 |  | 3/0 |  |
| mysql | insert | 100,000 | baseline | 1.738 | 57,521 |  | 3/0 |  |
| mysql | update | 1,000 | baseline | 0.035 | 28,329 |  | 3/0 |  |
| mysql | update | 10,000 | baseline | 0.235 | 42,499 |  | 3/0 |  |
| mysql | update | 100,000 | baseline | 2.285 | 43,758 |  | 3/0 |  |
| mysql | delete | 1,000 | baseline | 0.013 | 77,519 |  | 3/0 |  |
| mysql | delete | 10,000 | baseline | 0.086 | 116,686 |  | 3/0 |  |
| mysql | delete | 100,000 | baseline | 0.706 | 141,603 |  | 3/0 |  |
| oracle | insert | 1,000 | baseline | 0.023 | 44,053 |  | 3/0 |  |
| oracle | insert | 10,000 | baseline | 0.105 | 95,057 |  | 3/0 |  |
| oracle | insert | 100,000 | baseline | 0.931 | 107,423 |  | 3/0 |  |
| oracle | update | 1,000 | baseline | 0.017 | 57,471 |  | 3/0 |  |
| oracle | update | 10,000 | baseline | 0.120 | 83,333 |  | 3/0 |  |
| oracle | update | 100,000 | baseline | 1.601 | 62,465 |  | 3/0 |  |
| oracle | delete | 1,000 | baseline | 0.015 | 66,225 |  | 3/0 |  |
| oracle | delete | 10,000 | baseline | 0.098 | 102,041 |  | 3/0 |  |
| oracle | delete | 100,000 | baseline | 1.736 | 57,587 |  | 3/0 |  |
| postgresql | insert | 1,000 | baseline | 0.017 | 58,824 |  | 3/0 |  |
| postgresql | insert | 10,000 | baseline | 0.055 | 181,818 |  | 3/0 |  |
| postgresql | insert | 100,000 | baseline | 0.428 | 233,372 |  | 3/0 |  |
| postgresql | update | 1,000 | baseline | 0.022 | 46,296 |  | 3/0 |  |
| postgresql | update | 10,000 | baseline | 0.103 | 97,371 |  | 3/0 |  |
| postgresql | update | 100,000 | baseline | 1.264 | 79,095 |  | 3/0 |  |
| postgresql | delete | 1,000 | baseline | 0.006 | 172,414 |  | 3/0 |  |
| postgresql | delete | 10,000 | baseline | 0.018 | 558,659 |  | 3/0 |  |
| postgresql | delete | 100,000 | baseline | 0.211 | 473,709 |  | 3/0 |  |
| sqlite | insert | 1,000 | baseline | 0.017 | 59,524 |  | 3/0 |  |
| sqlite | insert | 10,000 | baseline | 0.081 | 123,153 |  | 3/0 |  |
| sqlite | insert | 100,000 | baseline | 0.680 | 147,016 |  | 3/0 |  |
| sqlite | update | 1,000 | baseline | 0.014 | 71,429 |  | 3/0 |  |
| sqlite | update | 10,000 | baseline | 0.107 | 93,545 |  | 3/0 |  |
| sqlite | update | 100,000 | baseline | 0.983 | 101,781 |  | 3/0 |  |
| sqlite | delete | 1,000 | baseline | 0.007 | 144,928 |  | 3/0 |  |
| sqlite | delete | 10,000 | baseline | 0.026 | 380,228 |  | 3/0 |  |
| sqlite | delete | 100,000 | baseline | 0.280 | 356,761 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
