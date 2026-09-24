# Banco de pruebas bulk

- Fecha: 2026-09-24T07:58:40 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 3

| Motor | Servidor | Driver |
|---|---|---|
| mysql | 8.4.11 | mysql+pymysql |
| mariadb | 11.4.13 | mariadb+pymysql |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mariadb | insert | 1,000 | baseline | 0.093 | 10,718 |  | 3/0 |  |
| mariadb | insert | 1,000 | mysql-multirow-legacy | 0.161 | 6,223 | 0.58× | 3/0 |  |
| mariadb | insert | 10,000 | baseline | 0.378 | 26,434 |  | 3/0 |  |
| mariadb | insert | 10,000 | mysql-multirow-legacy | 1.053 | 9,499 | 0.36× | 3/0 |  |
| mariadb | insert | 100,000 | baseline | 2.915 | 34,302 |  | 3/0 |  |
| mariadb | insert | 100,000 | mysql-multirow-legacy | 5.242 | 19,078 | 0.56× | 3/0 |  |
| mysql | insert | 1,000 | baseline | 0.109 | 9,141 |  | 3/0 |  |
| mysql | insert | 1,000 | mysql-multirow-legacy | 0.119 | 8,382 | 0.92× | 3/0 |  |
| mysql | insert | 10,000 | baseline | 0.404 | 24,759 |  | 3/0 |  |
| mysql | insert | 10,000 | mysql-multirow-legacy | 0.664 | 15,069 | 0.61× | 3/0 |  |
| mysql | insert | 100,000 | baseline | 2.693 | 37,129 |  | 3/0 |  |
| mysql | insert | 100,000 | mysql-multirow-legacy | 5.813 | 17,202 | 0.46× | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
