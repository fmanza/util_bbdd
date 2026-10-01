# Banco de pruebas bulk

- Fecha: 2026-10-01T23:03:15 · Python 3.14.2 · pandas 3.0.3 · SQLAlchemy 2.0.50 · chunk_size auto · repeticiones 3

| Motor | Servidor | Driver |
|---|---|---|
| mariadb | 11.4.13 | mariadb+pymysql |
| mariadb_connector | 11.4.13 | mariadb+mariadbconnector |

| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |
|---|---|---|---|---|---|---|---|---|
| mariadb | insert | 1,000,000 | baseline | 15.180 | 65,874 |  | 3/0 |  |
| mariadb | update | 1,000,000 | baseline | 21.491 | 46,530 |  | 3/0 |  |
| mariadb | delete | 1,000,000 | baseline | 6.764 | 147,842 |  | 3/0 |  |
| mariadb_connector | insert | 1,000,000 | baseline | 7.969 | 125,493 |  | 3/0 |  |
| mariadb_connector | update | 1,000,000 | baseline | 12.889 | 77,587 |  | 3/0 |  |
| mariadb_connector | delete | 1,000,000 | baseline | 6.854 | 145,894 |  | 3/0 |  |

`vs baseline` > 1 significa que la variante es más rápida que `baseline`.
