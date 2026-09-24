# Banco de pruebas bulk

- Fecha: 2026-09-24T08:30:48 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 5000 · repeticiones 3

| Motor | Servidor | Driver |
|---|---|---|
| mysql | 8.4.11 | mysql+pymysql |
| mariadb | 11.4.13 | mariadb+pymysql |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mariadb | update | 10,000 | baseline | 3.356 | 2,980 |  | 3/0 |  |
| mariadb | update | 10,000 | p04-mysql-staging-update | 0.262 | 38,124 | 12.79× | 3/0 |  |
| mariadb | update | 100,000 | baseline | 33.585 | 2,978 |  | 3/0 |  |
| mariadb | update | 100,000 | p04-mysql-staging-update | 2.662 | 37,569 | 12.62× | 3/0 |  |
| mysql | update | 10,000 | baseline | 3.792 | 2,637 |  | 3/0 |  |
| mysql | update | 10,000 | p04-mysql-staging-update | 0.284 | 35,211 | 13.35× | 3/0 |  |
| mysql | update | 100,000 | baseline | 37.428 | 2,672 |  | 3/0 |  |
| mysql | update | 100,000 | p04-mysql-staging-update | 2.923 | 34,209 | 12.80× | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
