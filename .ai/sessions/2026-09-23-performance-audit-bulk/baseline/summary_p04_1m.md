# Banco de pruebas bulk

- Fecha: 2026-09-24T08:35:40 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 1

| Motor | Servidor | Driver |
|---|---|---|
| mysql | 8.4.11 | mysql+pymysql |
| mariadb | 11.4.13 | mariadb+pymysql |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mariadb | update | 1,000,000 | baseline | 331.402 | 3,018 |  | 1/0 |  |
| mariadb | update | 1,000,000 | p04-mysql-staging-update | 27.089 | 36,915 | 12.23× | 1/0 |  |
| mysql | update | 1,000,000 | baseline | 375.961 | 2,660 |  | 1/0 |  |
| mysql | update | 1,000,000 | p04-mysql-staging-update | 29.481 | 33,920 | 12.75× | 1/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
