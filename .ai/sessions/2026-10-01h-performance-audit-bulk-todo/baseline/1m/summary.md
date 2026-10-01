# Banco de pruebas bulk

- Fecha: 2026-10-01T03:14:27 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 1

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
| mariadb | insert | 1,000,000 | baseline | 16.694 | 59,900 |  | 1/0 |  |
| mariadb | update | 1,000,000 | baseline | 21.856 | 45,754 |  | 1/0 |  |
| mariadb | delete | 1,000,000 | baseline | 6.873 | 145,497 |  | 1/0 |  |
| mssql | insert | 1,000,000 | baseline | 15.290 | 65,400 |  | 1/0 |  |
| mssql | update | 1,000,000 | baseline | 23.029 | 43,423 |  | 1/0 |  |
| mssql | delete | 1,000,000 | baseline | 9.273 | 107,845 |  | 1/0 |  |
| mysql | insert | 1,000,000 | baseline | 17.598 | 56,826 |  | 1/0 |  |
| mysql | update | 1,000,000 | baseline | 23.110 | 43,271 |  | 1/0 |  |
| mysql | delete | 1,000,000 | baseline | 6.907 | 144,774 |  | 1/0 |  |
| oracle | insert | 1,000,000 | baseline | 11.162 | 89,586 |  | 1/0 |  |
| oracle | update | 1,000,000 | baseline | 17.557 | 56,958 |  | 1/0 |  |
| oracle | delete | 1,000,000 | baseline | 17.578 | 56,891 |  | 1/0 |  |
| postgresql | insert | 1,000,000 | baseline | 6.002 | 166,611 |  | 1/0 |  |
| postgresql | update | 1,000,000 | baseline | 26.428 | 37,838 |  | 1/0 |  |
| postgresql | delete | 1,000,000 | baseline | 2.097 | 476,872 |  | 1/0 |  |
| sqlite | insert | 1,000,000 | baseline | 7.112 | 140,605 |  | 1/0 |  |
| sqlite | update | 1,000,000 | baseline | 10.252 | 97,540 |  | 1/0 |  |
| sqlite | delete | 1,000,000 | baseline | 3.039 | 329,088 |  | 1/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
