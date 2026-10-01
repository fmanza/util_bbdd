# Banco de pruebas bulk

- Fecha: 2026-10-01T08:15:43 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 3

| Motor | Servidor | Driver |
|---|---|---|
| postgresql | 17.11 | postgresql+psycopg |
| mysql | 8.4.11 | mysql+pymysql |
| mariadb | 11.4.13 | mariadb+pymysql |
| mssql | 16.0.4295.3 | mssql+pyodbc |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mariadb | insert | 10,000 | baseline | 0.250 | 40,000 |  | 3/0 |  |
| mariadb | insert | 100,000 | baseline | 1.592 | 62,830 |  | 3/0 |  |
| mariadb | update | 10,000 | baseline | 0.220 | 45,558 |  | 3/0 |  |
| mariadb | update | 100,000 | baseline | 2.044 | 48,921 |  | 3/0 |  |
| mariadb | delete | 10,000 | baseline | 0.060 | 165,838 |  | 3/0 |  |
| mariadb | delete | 100,000 | baseline | 0.739 | 135,355 |  | 3/0 |  |
| mssql | insert | 10,000 | baseline | 0.247 | 40,552 |  | 3/0 |  |
| mssql | insert | 100,000 | baseline | 1.417 | 70,587 |  | 3/0 |  |
| mssql | update | 10,000 | baseline | 0.253 | 39,526 |  | 3/0 |  |
| mssql | update | 100,000 | baseline | 2.209 | 45,259 |  | 3/0 |  |
| mssql | delete | 10,000 | baseline | 0.040 | 248,139 |  | 3/0 |  |
| mssql | delete | 100,000 | baseline | 0.331 | 301,841 |  | 3/0 |  |
| mysql | insert | 10,000 | baseline | 0.311 | 32,175 |  | 3/0 |  |
| mysql | insert | 100,000 | baseline | 1.734 | 57,660 |  | 3/0 |  |
| mysql | update | 10,000 | baseline | 0.238 | 42,017 |  | 3/0 |  |
| mysql | update | 100,000 | baseline | 2.269 | 44,074 |  | 3/0 |  |
| mysql | delete | 10,000 | baseline | 0.090 | 111,235 |  | 3/0 |  |
| mysql | delete | 100,000 | baseline | 0.719 | 139,121 |  | 3/0 |  |
| postgresql | insert | 10,000 | baseline | 0.047 | 213,675 |  | 3/0 |  |
| postgresql | insert | 100,000 | baseline | 0.438 | 228,154 |  | 3/0 |  |
| postgresql | update | 10,000 | baseline | 0.283 | 35,336 |  | 3/0 |  |
| postgresql | update | 100,000 | baseline | 2.531 | 39,515 |  | 3/0 |  |
| postgresql | delete | 10,000 | baseline | 0.021 | 469,484 |  | 3/0 |  |
| postgresql | delete | 100,000 | baseline | 0.210 | 476,872 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
