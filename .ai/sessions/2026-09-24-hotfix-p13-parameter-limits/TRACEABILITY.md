# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-p13-parameter-limits
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase: RCA + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Hago el commit y sigo con P-13 …?". Antes, commits `1656d97` y `5f852df` de P-28.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-13)
- `src/util_bbdd/bulk/_execution/batch.py` (`MySQLMultiRowInsertStrategy`, `SqlBasedDeleteStrategy`)

## AI output summary
- **Reproducción** (`scratchpad/p13_repro.py`, MariaDB 11.4):
  - conector `mariadb` 1.1.14: INSERT de 1000 filas × 71 columnas y DELETE de 40.000 PK compuestas → `OperationalError: Prepared statement contains too many placeholders`;
  - PyMySQL: correcto (sustituye en el cliente);
  - `mysql-connector` no instalado.
- **RCA**:
  - `MySQLMultiRowInsertStrategy` (drivers MySQL/MariaDB distintos de PyMySQL) pone `max_rows_per_statement=1000` filas por sentencia sin mirar el número de columnas: 1000 × 66 > 65.535;
  - `SqlBasedDeleteStrategy` solo troceaba en SQL Server; en MySQL/MariaDB el `IN` llevaba `chunk_size × columnas de la PK` parámetros.
  - El UPDATE por staging carga la temporal con la misma estrategia de INSERT, así que heredaba el fallo.
- **Fix**:
  - `_MYSQL_MAX_STATEMENT_PARAMS = 65_535`;
  - INSERT multi-fila: `min(max_rows_per_statement, 65535 // columnas)` filas por sentencia;
  - DELETE: `_MAX_DELETE_PARAMS` por dialecto (`mssql` 2000 como antes; `mysql`/`mariadb` 65.535) y troceo en `max_params // columnas de la PK` filas;
  - SQL Server con PK compuesta sigue delegando en `GenericDeleteStrategy`;
  - dialectos sin entrada (hsqldb): una sentencia por lote, como antes.
- **Sin cambios**: SQLite, PostgreSQL y Oracle no construyen sentencias con parámetros por fila (executemany/COPY). SQL Server INSERT: `insertmanyvalues` de SQLAlchemy ya respeta 2099.
- **No abordado**: la otra mitad de P-13 (un único `chunk_size` para todos los motores). No hay medición que muestre beneficio.
- **Tests**:
  - `tests/unit/bulk/test_parameter_limits.py` (5):
    - filas por sentencia con 3, 70 y 71 columnas y cada registro una vez;
    - DELETE compuesto de 40.000 filas en `mysql` y `mariadb` → 65.534 + 14.466 parámetros.
  - Integración:
    - `test_wide_table_insert_and_update` (6 motores; comparación completa tras INSERT + UPDATE);
    - `test_delete_composite_pk_over_parameter_limit` (MySQL/MariaDB, 34.000 PK compuestas);
    - en MariaDB también con el conector `mariadb`;
    - con el código anterior fallan los 2 casos de MariaDB.
- **Validación**:
  - `ruff check src tests` y `mypy src tests/unit/test_protocol_conformance.py` limpios;
  - suite 4599 passed / 149 skipped;
  - integración 6 motores 144 passed / 24 skipped.

## AUDIT_CODE
- Regresiones potenciales:
  - tablas anchas en MariaDB/MySQL con conectores distintos de PyMySQL: más sentencias (antes fallaban);
  - DELETE en MySQL/MariaDB con lotes > 65.535 parámetros: varias sentencias en la misma transacción (antes una; con PyMySQL funcionaba igual).
- Edge cases:
  - más de 65.535 columnas: imposible en MySQL (máximo 4096); `max(1, …)` evita 0 filas.
- Rendimiento: sin cambio con menos de 66 columnas (INSERT) o lotes por debajo del límite (DELETE).
- Compatibilidad: sin cambios de API; `MySQLMultiRowInsertStrategy(max_rows_per_statement=…)` sigue siendo el máximo.

## Directrices para Futuras IAs
- **[bulk/límites]**: toda sentencia construida con parámetros por fila debe acotarse por el límite del motor. SQL Server: 2100 por petición. MySQL/MariaDB con sentencia preparada (conector `mariadb`): 65.535. Probar con el conector `mariadb`: PyMySQL no reproduce estos fallos.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- Siguientes del bloque: P-10, P-06 + observación de SQLAlchemy, P-07 (bloques), P-08.
