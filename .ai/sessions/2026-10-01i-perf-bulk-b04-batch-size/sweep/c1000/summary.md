# Banco de pruebas bulk

- Fecha: 2026-10-01T11:16:41 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 1000 · repeticiones 3

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
| mariadb | insert | 1,000,000 | baseline | 15.382 | 65,013 |  | 3/0 |  |
| mariadb | update | 1,000,000 | baseline | 24.000 | 41,666 |  | 3/0 |  |
| mariadb | delete | 1,000,000 | baseline | 7.665 | 130,472 |  | 3/0 |  |
| mssql | insert | 1,000,000 | baseline | 17.318 | 57,744 |  | 3/0 |  |
| mssql | update | 1,000,000 | baseline | 25.681 | 38,940 |  | 3/0 |  |
| mssql | delete | 1,000,000 | baseline | 5.920 | 168,930 |  | 3/0 |  |
| mysql | insert | 1,000,000 | baseline | 16.436 | 60,843 |  | 3/0 |  |
| mysql | update | 1,000,000 | baseline | 26.455 | 37,800 |  | 3/0 |  |
| mysql | delete | 1,000,000 | baseline | 8.280 | 120,780 |  | 3/0 |  |
| oracle | insert | 1,000,000 | baseline | 10.716 | 93,314 |  | 3/0 |  |
| oracle | update | 1,000,000 | baseline | 16.101 | 62,106 |  | 3/0 |  |
| oracle | delete | 1,000,000 | baseline | 17.804 | 56,168 |  | 3/0 |  |
| postgresql | insert | 1,000,000 | baseline | 6.332 | 157,928 |  | 3/0 |  |
| postgresql | update | 1,000,000 | baseline | 15.219 | 65,706 |  | 3/0 |  |
| postgresql | delete | 1,000,000 | baseline | 2.810 | 355,821 |  | 3/0 |  |
| sqlite | insert | 1,000,000 | baseline | 6.995 | 142,963 |  | 3/0 |  |
| sqlite | update | 1,000,000 | baseline | 10.254 | 97,520 |  | 3/0 |  |
| sqlite | delete | 1,000,000 | baseline | 3.361 | 297,522 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
