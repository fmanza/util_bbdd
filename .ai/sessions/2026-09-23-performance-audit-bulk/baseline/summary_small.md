# Banco de pruebas bulk

- Fecha: 2026-09-24T00:38:31 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 3

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
| mariadb | insert | 1,000 | baseline | 0.093 | 10,788 |  | 3/0 |  |
| mariadb | insert | 1,000 | p02-mysql-executemany | 0.078 | 12,771 | 1.18× | 3/0 |  |
| mariadb | insert | 10,000 | baseline | 0.806 | 12,408 |  | 3/0 |  |
| mariadb | insert | 10,000 | p02-mysql-executemany | 0.335 | 29,815 | 2.40× | 3/0 |  |
| mariadb | insert | 100,000 | baseline | 5.047 | 19,813 |  | 3/0 |  |
| mariadb | insert | 100,000 | p02-mysql-executemany | 2.621 | 38,156 | 1.93× | 3/0 |  |
| mariadb | update | 1,000 | baseline | 0.410 | 2,439 |  | 3/0 |  |
| mariadb | update | 1,000 | p02-mysql-executemany | 0.458 | 2,184 | 0.90× | 3/0 |  |
| mariadb | update | 10,000 | baseline | 3.332 | 3,002 |  | 3/0 |  |
| mariadb | update | 10,000 | p02-mysql-executemany | 3.410 | 2,932 | 0.98× | 3/0 |  |
| mariadb | update | 100,000 | baseline | 34.132 | 2,930 |  | 3/0 |  |
| mariadb | update | 100,000 | p02-mysql-executemany | 33.838 | 2,955 | 1.01× | 3/0 |  |
| mariadb | delete | 1,000 | baseline | 0.012 | 80,645 |  | 3/0 |  |
| mariadb | delete | 1,000 | p02-mysql-executemany | 0.011 | 91,743 | 1.14× | 3/0 |  |
| mariadb | delete | 10,000 | baseline | 0.177 | 56,593 |  | 3/0 |  |
| mariadb | delete | 10,000 | p02-mysql-executemany | 0.148 | 67,613 | 1.19× | 3/0 |  |
| mariadb | delete | 100,000 | baseline | 1.491 | 67,083 |  | 3/0 |  |
| mariadb | delete | 100,000 | p02-mysql-executemany | 1.532 | 65,266 | 0.97× | 3/0 |  |
| mssql | insert | 1,000 | baseline | 0.381 | 2,625 |  | 3/0 |  |
| mssql | insert | 10,000 | baseline | 3.732 | 2,679 |  | 3/0 |  |
| mssql | insert | 100,000 | baseline | 37.007 | 2,702 |  | 3/0 |  |
| mssql | update | 1,000 | baseline | 0.673 | 1,486 |  | 3/0 |  |
| mssql | update | 10,000 | baseline | 5.883 | 1,700 |  | 3/0 |  |
| mssql | update | 100,000 | baseline | 57.884 | 1,728 |  | 3/0 |  |
| mssql | delete | 1,000 | baseline | 0.082 | 12,270 |  | 3/0 |  |
| mssql | delete | 10,000 | baseline | 0.815 | 12,270 |  | 3/0 |  |
| mssql | delete | 100,000 | baseline | 4.706 | 21,250 |  | 3/0 |  |
| mysql | insert | 1,000 | baseline | 0.089 | 11,223 |  | 3/0 |  |
| mysql | insert | 1,000 | p02-mysql-executemany | 0.133 | 7,542 | 0.67× | 3/0 |  |
| mysql | insert | 10,000 | baseline | 0.812 | 12,312 |  | 3/0 |  |
| mysql | insert | 10,000 | p02-mysql-executemany | 0.431 | 23,196 | 1.88× | 3/0 |  |
| mysql | insert | 100,000 | baseline | 5.744 | 17,410 |  | 3/0 |  |
| mysql | insert | 100,000 | p02-mysql-executemany | 3.106 | 32,192 | 1.85× | 3/0 |  |
| mysql | update | 1,000 | baseline | 0.386 | 2,592 |  | 3/0 |  |
| mysql | update | 1,000 | p02-mysql-executemany | 0.389 | 2,573 | 0.99× | 3/0 |  |
| mysql | update | 10,000 | baseline | 3.773 | 2,651 |  | 3/0 |  |
| mysql | update | 10,000 | p02-mysql-executemany | 3.815 | 2,621 | 0.99× | 3/0 |  |
| mysql | update | 100,000 | baseline | 38.071 | 2,627 |  | 3/0 |  |
| mysql | update | 100,000 | p02-mysql-executemany | 37.712 | 2,652 | 1.01× | 3/0 |  |
| mysql | delete | 1,000 | baseline | 0.015 | 67,568 |  | 3/0 |  |
| mysql | delete | 1,000 | p02-mysql-executemany | 0.013 | 76,923 | 1.14× | 3/0 |  |
| mysql | delete | 10,000 | baseline | 0.174 | 57,339 |  | 3/0 |  |
| mysql | delete | 10,000 | p02-mysql-executemany | 0.196 | 51,125 | 0.89× | 3/0 |  |
| mysql | delete | 100,000 | baseline | 1.629 | 61,406 |  | 3/0 |  |
| mysql | delete | 100,000 | p02-mysql-executemany | 1.617 | 61,831 | 1.01× | 3/0 |  |
| oracle | insert | 1,000 | baseline | 0.092 | 10,917 |  | 3/0 |  |
| oracle | insert | 10,000 | baseline | 0.246 | 40,634 |  | 3/0 |  |
| oracle | insert | 100,000 | baseline | 2.482 | 40,284 |  | 3/0 |  |
| oracle | update | 1,000 | baseline | 0.073 | 13,755 |  | 3/0 |  |
| oracle | update | 10,000 | baseline | 0.261 | 38,329 |  | 3/0 |  |
| oracle | update | 100,000 | baseline | 2.756 | 36,283 |  | 3/0 |  |
| oracle | delete | 1,000 | baseline | 0.037 | 27,100 |  | 3/0 |  |
| oracle | delete | 10,000 | baseline | 0.291 | 34,317 |  | 3/0 |  |
| oracle | delete | 100,000 | baseline | 2.210 | 45,255 |  | 3/0 |  |
| postgresql | insert | 1,000 | baseline | 0.076 | 13,175 |  | 3/0 |  |
| postgresql | insert | 10,000 | baseline | 0.270 | 37,064 |  | 3/0 |  |
| postgresql | insert | 100,000 | baseline | 2.090 | 47,849 |  | 3/0 |  |
| postgresql | update | 1,000 | baseline | 0.128 | 7,837 |  | 3/0 |  |
| postgresql | update | 10,000 | baseline | 0.500 | 19,980 |  | 3/0 |  |
| postgresql | update | 100,000 | baseline | 4.220 | 23,696 |  | 3/0 |  |
| postgresql | delete | 1,000 | baseline | 0.097 | 10,341 |  | 3/0 |  |
| postgresql | delete | 10,000 | baseline | 0.375 | 26,652 |  | 3/0 |  |
| postgresql | delete | 100,000 | baseline | 2.829 | 35,351 |  | 3/0 |  |
| sqlite | insert | 1,000 | baseline | 0.018 | 54,054 |  | 3/0 |  |
| sqlite | insert | 10,000 | baseline | 0.185 | 53,937 |  | 3/0 |  |
| sqlite | insert | 100,000 | baseline | 1.425 | 70,151 |  | 3/0 |  |
| sqlite | update | 1,000 | baseline | 0.022 | 44,444 |  | 3/0 |  |
| sqlite | update | 10,000 | baseline | 0.194 | 51,493 |  | 3/0 |  |
| sqlite | update | 100,000 | baseline | 1.847 | 54,145 |  | 3/0 |  |
| sqlite | delete | 1,000 | baseline | 0.008 | 119,048 |  | 3/0 |  |
| sqlite | delete | 10,000 | baseline | 0.032 | 311,526 |  | 3/0 |  |
| sqlite | delete | 100,000 | baseline | 0.388 | 257,732 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
