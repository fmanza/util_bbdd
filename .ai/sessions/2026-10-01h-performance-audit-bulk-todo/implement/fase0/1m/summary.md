# Banco de pruebas bulk

- Fecha: 2026-10-01T08:16:42 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 1

| Motor | Servidor | Driver |
|---|---|---|
| postgresql | 17.11 | postgresql+psycopg |
| mysql | 8.4.11 | mysql+pymysql |
| mariadb | 11.4.13 | mariadb+pymysql |
| mssql | 16.0.4295.3 | mssql+pyodbc |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mariadb | insert | 1,000,000 | baseline | 17.224 | 58,058 |  | 1/0 |  |
| mariadb | update | 1,000,000 | baseline | 20.757 | 48,177 |  | 1/0 |  |
| mariadb | delete | 1,000,000 | baseline | 6.750 | 148,148 |  | 1/0 |  |
| mssql | insert | 1,000,000 | baseline | 15.094 | 66,252 |  | 1/0 |  |
| mssql | update | 1,000,000 | baseline | 22.439 | 44,566 |  | 1/0 |  |
| mssql | delete | 1,000,000 | baseline | 2.771 | 360,946 |  | 1/0 |  |
| mysql | insert | 1,000,000 | baseline | 15.901 | 62,888 |  | 1/0 |  |
| mysql | update | 1,000,000 | baseline | 22.493 | 44,459 |  | 1/0 |  |
| mysql | delete | 1,000,000 | baseline | 7.592 | 131,714 |  | 1/0 |  |
| postgresql | insert | 1,000,000 | baseline | 4.348 | 229,964 |  | 1/0 |  |
| postgresql | update | 1,000,000 | baseline | 25.713 | 38,891 |  | 1/0 |  |
| postgresql | delete | 1,000,000 | baseline | 2.010 | 497,438 |  | 1/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
