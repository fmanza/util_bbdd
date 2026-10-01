# Banco de pruebas bulk

- Fecha: 2026-10-01T03:12:53 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 3

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
| mariadb | insert | 1,000 | baseline | 0.037 | 26,810 |  | 3/0 |  |
| mariadb | insert | 10,000 | baseline | 0.244 | 40,933 |  | 3/0 |  |
| mariadb | insert | 100,000 | baseline | 1.728 | 57,874 |  | 3/0 |  |
| mariadb | update | 1,000 | baseline | 0.029 | 34,602 |  | 3/0 |  |
| mariadb | update | 10,000 | baseline | 0.229 | 43,649 |  | 3/0 |  |
| mariadb | update | 100,000 | baseline | 2.178 | 45,912 |  | 3/0 |  |
| mariadb | delete | 1,000 | baseline | 0.009 | 108,696 |  | 3/0 |  |
| mariadb | delete | 10,000 | baseline | 0.062 | 162,075 |  | 3/0 |  |
| mariadb | delete | 100,000 | baseline | 0.709 | 140,984 |  | 3/0 |  |
| mssql | insert | 1,000 | baseline | 0.056 | 17,794 |  | 3/0 |  |
| mssql | insert | 10,000 | baseline | 0.163 | 61,237 |  | 3/0 |  |
| mssql | insert | 100,000 | baseline | 1.440 | 69,449 |  | 3/0 |  |
| mssql | update | 1,000 | baseline | 0.064 | 15,625 |  | 3/0 |  |
| mssql | update | 10,000 | baseline | 0.240 | 41,632 |  | 3/0 |  |
| mssql | update | 100,000 | baseline | 2.240 | 44,637 |  | 3/0 |  |
| mssql | delete | 1,000 | baseline | 0.214 | 4,677 |  | 3/0 |  |
| mssql | delete | 10,000 | baseline | 0.810 | 12,347 |  | 3/0 |  |
| mssql | delete | 100,000 | baseline | 1.163 | 85,984 |  | 3/0 |  |
| mysql | insert | 1,000 | baseline | 0.054 | 18,484 |  | 3/0 |  |
| mysql | insert | 10,000 | baseline | 0.288 | 34,770 |  | 3/0 |  |
| mysql | insert | 100,000 | baseline | 1.848 | 54,116 |  | 3/0 |  |
| mysql | update | 1,000 | baseline | 0.036 | 27,548 |  | 3/0 |  |
| mysql | update | 10,000 | baseline | 0.226 | 44,189 |  | 3/0 |  |
| mysql | update | 100,000 | baseline | 2.294 | 43,588 |  | 3/0 |  |
| mysql | delete | 1,000 | baseline | 0.024 | 41,667 |  | 3/0 |  |
| mysql | delete | 10,000 | baseline | 0.092 | 108,814 |  | 3/0 |  |
| mysql | delete | 100,000 | baseline | 0.682 | 146,671 |  | 3/0 |  |
| oracle | insert | 1,000 | baseline | 0.055 | 18,315 |  | 3/0 |  |
| oracle | insert | 10,000 | baseline | 0.111 | 89,767 |  | 3/0 |  |
| oracle | insert | 100,000 | baseline | 1.101 | 90,843 |  | 3/0 |  |
| oracle | update | 1,000 | baseline | 0.024 | 42,194 |  | 3/0 |  |
| oracle | update | 10,000 | baseline | 0.262 | 38,168 |  | 3/0 |  |
| oracle | update | 100,000 | baseline | 1.601 | 62,461 |  | 3/0 |  |
| oracle | delete | 1,000 | baseline | 0.026 | 38,462 |  | 3/0 |  |
| oracle | delete | 10,000 | baseline | 0.161 | 61,958 |  | 3/0 |  |
| oracle | delete | 100,000 | baseline | 1.961 | 51,000 |  | 3/0 |  |
| postgresql | insert | 1,000 | baseline | 0.018 | 55,866 |  | 3/0 |  |
| postgresql | insert | 10,000 | baseline | 0.064 | 156,494 |  | 3/0 |  |
| postgresql | insert | 100,000 | baseline | 0.524 | 190,803 |  | 3/0 |  |
| postgresql | update | 1,000 | baseline | 0.040 | 24,876 |  | 3/0 |  |
| postgresql | update | 10,000 | baseline | 0.281 | 35,638 |  | 3/0 |  |
| postgresql | update | 100,000 | baseline | 2.597 | 38,510 |  | 3/0 |  |
| postgresql | delete | 1,000 | baseline | 0.005 | 181,818 |  | 3/0 |  |
| postgresql | delete | 10,000 | baseline | 0.021 | 467,290 |  | 3/0 |  |
| postgresql | delete | 100,000 | baseline | 0.215 | 464,900 |  | 3/0 |  |
| sqlite | insert | 1,000 | baseline | 0.016 | 61,728 |  | 3/0 |  |
| sqlite | insert | 10,000 | baseline | 0.097 | 103,306 |  | 3/0 |  |
| sqlite | insert | 100,000 | baseline | 0.727 | 137,570 |  | 3/0 |  |
| sqlite | update | 1,000 | baseline | 0.015 | 68,966 |  | 3/0 |  |
| sqlite | update | 10,000 | baseline | 0.112 | 89,445 |  | 3/0 |  |
| sqlite | update | 100,000 | baseline | 0.996 | 100,361 |  | 3/0 |  |
| sqlite | delete | 1,000 | baseline | 0.007 | 144,928 |  | 3/0 |  |
| sqlite | delete | 10,000 | baseline | 0.027 | 364,964 |  | 3/0 |  |
| sqlite | delete | 100,000 | baseline | 0.308 | 324,992 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
