# Banco de pruebas bulk

- Fecha: 2026-10-01T11:44:10 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size 50000 · repeticiones 3

| Motor | Servidor | Driver |
|---|---|---|
| mysql | 8.4.11 | mysql+pymysql |
| mariadb | 11.4.13 | mariadb+pymysql |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mariadb | delete | 1,000,000 | baseline | 6.567 | 152,272 |  | 3/0 |  |
| mysql | delete | 1,000,000 | baseline | 6.821 | 146,602 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
