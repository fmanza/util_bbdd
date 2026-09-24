# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-p27-pg-commit-every-n-chunks
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase: RCA + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si. He instalado psycopg2
```
(Respuesta a "¿Hago el commit de P-25 y P-26 y sigo con el hotfix de P-27 antes que el resto?". Antes, commits `eab996a` y `b680708`.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` (P-27)
- `src/util_bbdd/bulk/_execution/batch.py` (`PostgresCopyStrategy`, `PostgreSQLExecuteValuesStrategy`, `BatchStatementExecutor`), `src/util_bbdd/bulk/crud.py` (`bulk_session`)
- psycopg 3.3.3 y psycopg2 2.9.13 (instalado por el usuario para esta sesión)

## AI output summary
- **RCA**: las dos estrategias de INSERT de PostgreSQL escriben por `connection.connection.cursor()`.
  - SQLAlchemy no ve esa ejecución y no inicia su transacción.
  - En modo `commit_every_n_chunks`, `BatchStatementExecutor.execute` y `bulk_session` usan `engine.connect()` (commit-as-you-go): `connection.commit()` no hace nada y la conexión vuelve al pool con rollback.
  - Con `engine.begin()` (modo atómico) la transacción ya está abierta, por eso no fallaba.
- **Reproducción**: `scratchpad/p27_repro.py`, 5 + 5 filas con `chunk_size=2`.
  - psycopg y psycopg2: 0 de 10 filas guardadas con `commit_every_n_chunks` = 1 o 2, con o sin `bulk_session`, y `rows_committed` = 10.
  - En modo atómico, 10 de 10.
- **Fix**: `_begin_if_needed(connection)` (`if not connection.in_transaction(): connection.begin()`) antes de usar el cursor, en las dos estrategias. Tras el fix: 10 de 10 en todos los modos y con los dos drivers.
  - Son los únicos usos del cursor del driver en `src/`.
- **Tests**:
  - `tests/unit/bulk/test_raw_cursor_transaction.py` (6):
    - las dos estrategias llaman a `begin` antes de pedir el cursor, y no lo hacen si ya hay transacción;
    - en SQLite, `commit()` en commit-as-you-go confirma lo escrito por el cursor del driver;
    - la transacción existente se conserva.
  - Integración (5 casos × 6 motores; en PostgreSQL con psycopg 3 y psycopg2):
    - `test_commit_every_n_chunks_persists_inserts` (`commit_every_n_chunks` 1/2 × con/sin sesión);
    - `test_commit_every_n_chunks_keeps_committed_chunks_on_failure`: los lotes confirmados quedan y `rows_committed` los cuenta.
  - Con el código anterior fallan los 5 casos de PostgreSQL; el resto de motores pasa.
- **Hallazgo nuevo P-28 (MEDIA)**:
  - los errores del INSERT de PostgreSQL llegan como excepción del driver (`psycopg.errors.UniqueViolation`), no como `SQLAlchemyError`;
  - `ParallelBulkLoader` y `dump` solo capturan `SQLAlchemyError`, así que, por deducción, un error de datos abortaría la carga en lugar de registrarse;
  - registrado en `02_BASELINE_MOTORES_REALES.md`; el test acepta de momento ambos tipos.
- **Validación**:
  - `ruff check src tests` y `mypy src tests/unit/test_protocol_conformance.py` limpios;
  - suite 4587 passed / 128 skipped;
  - integración 6 motores 124 passed / 20 skipped.

## AUDIT_CODE
- Regresiones potenciales:
  - en modo atómico `in_transaction()` es verdadero y no cambia nada;
  - en commit-as-you-go, tras cada commit periódico, el siguiente lote abre otra transacción.
- Edge cases:
  - `records` vacío: return antes de abrir la transacción;
  - el fallback a `connection.execute` (UPDATE, `OVERRIDING SYSTEM VALUE`, psycopg2 no instalado) ya iniciaba la transacción.
- Compatibilidad: sin cambios de API; solo PostgreSQL.

## Directrices para Futuras IAs
- **[bulk/transacciones]**: cualquier escritura por el cursor del driver debe llamar antes a `_begin_if_needed`. Todo test de una estrategia de este tipo debe incluir `commit_every_n_chunks`.
- **[bulk/errores]**: el cursor del driver también se salta el envoltorio de excepciones de SQLAlchemy (P-28).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- P-28 (MEDIA).
- Siguientes del bloque: P-13, P-10, P-06 + observación de SQLAlchemy, P-07 (bloques), P-08.
