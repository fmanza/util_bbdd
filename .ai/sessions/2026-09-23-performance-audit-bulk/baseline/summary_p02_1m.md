# Banco de pruebas bulk

- Fecha: 2026-09-24T07:59:42 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 1

| Motor | Servidor | Driver |
|---|---|---|
| mysql | 8.4.11 | mysql+pymysql |
| mariadb | 11.4.13 | mariadb+pymysql |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mariadb | insert | 1,000,000 | baseline | 24.038 | 41,602 |  | 1/0 |  |
| mariadb | insert | 1,000,000 | mysql-multirow-legacy | 50.352 | 19,860 | 0.48× | 1/0 |  |
| mysql | insert | 1,000,000 | baseline | 26.289 | 38,039 |  | 1/0 |  |
| mysql | insert | 1,000,000 | mysql-multirow-legacy | 54.856 | 18,230 | 0.48× | 1/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
