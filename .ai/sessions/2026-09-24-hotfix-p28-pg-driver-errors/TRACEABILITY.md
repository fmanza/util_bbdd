# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-p28-pg-driver-errors
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase: RCA + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Hago el commit de P-27 y sigo con el hotfix de P-28?". Antes, commits `9b7a18c` y `6f8acee`.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` (P-28)
- `src/util_bbdd/bulk/_execution/batch.py` (`PostgresCopyStrategy`, `PostgreSQLExecuteValuesStrategy`)
- `src/util_bbdd/bulk/_execution/parallel_loader.py` (`load`, `_load_partition`), `src/util_bbdd/dump/orchestrator.py` (captura de `SQLAlchemyError`)

## AI output summary
- **RCA**: el INSERT de PostgreSQL escribe por el cursor del driver. SQLAlchemy, que es quien envuelve los errores del driver en `DBAPIError`, no interviene y la excepción llega sin envolver. Consumidores afectados:
  - `ParallelBulkLoader._load_partition` solo captura `SQLAlchemyError`/`SQLAOperationalError`; la excepción escapa y `future.result()` la relanza en `load()`;
  - `dump` solo captura `SQLAlchemyError`;
  - el log de `BulkCrud.__run_bulk_pipeline` tampoco la ve.
- **Reproducción** (`scratchpad/p28_repro.py`), `ParallelBulkLoader` con una partición que repite una PK existente:
  - psycopg 3 y psycopg2: `load()` se aborta con `UniqueViolation`;
  - PyMySQL: `total_rows=3` y 1 error;
  - `BulkCrud`: `UniqueViolation` con `SQLAlchemyError=False` en PostgreSQL.
- **Fix**: `_wrap_driver_error(connection, statement, exc)`:
  - `DBAPIError.instance(statement, None, exc, dialect.loaded_dbapi.Error, ...)`, la misma función que usa SQLAlchemy, que elige la clase por la jerarquía del error del driver (`IntegrityError`, `OperationalError`…);
  - sin parámetros (pueden ser miles de filas);
  - si `dialect.is_disconnect(...)`, invalida la conexión y marca `connection_invalidated`.

  Las dos estrategias capturan `dialect.loaded_dbapi.Error` y relanzan con `from exc`; el resto de excepciones no se toca.
- **Resultado**: PostgreSQL se comporta como MySQL (`total_rows=3`, 1 error; `IntegrityError`).
- **Tests**:
  - `tests/unit/bulk/test_raw_cursor_errors.py` (4; fallan 3 sin el fix):
    - COPY con `UniqueViolation` → `IntegrityError` (`orig`, sentencia, sin parámetros);
    - desconexión → `OperationalError` con la conexión invalidada;
    - una excepción ajena al driver no se envuelve;
    - `execute_values` con `UniqueViolation` → `IntegrityError`.
  - Integración, 6 motores; en PostgreSQL con psycopg 3 y psycopg2 (fallan los 3 casos de PostgreSQL sin el fix):
    - `test_insert_duplicate_key_raises_sqlalchemy_integrity_error`;
    - `test_parallel_loader_reports_partition_error`;
    - `test_commit_every_n_chunks_keeps_committed_chunks_on_failure` vuelve a exigir `SQLAlchemyError`.
- **Validación**:
  - `ruff check src tests` y `mypy src tests/unit/test_protocol_conformance.py` limpios. `DBAPIError.instance` está tipado como `StatementError`; así queda anotado el helper;
  - suite 4593 passed / 138 skipped;
  - integración 6 motores 136 passed / 20 skipped.

## AUDIT_CODE
- Regresiones potenciales: quien capturase `psycopg.errors.*` directamente en el INSERT de PostgreSQL debe capturar ahora `sqlalchemy.exc.*`. El error original sigue en `.orig` y en `__cause__`. Es el contrato documentado (`SQLAlchemyError`).
- Edge cases:
  - error al adaptar un valor en COPY (`psycopg.ProgrammingError`/`DataError`): se envuelve;
  - `KeyError` u otros errores de Python: sin cambios;
  - desconexión a mitad de COPY: conexión invalidada, como en el resto de rutas de SQLAlchemy.
- Seguridad: los parámetros no se incluyen en la excepción ni en el log.
- Compatibilidad: solo PostgreSQL; sin cambios de API.

## Directrices para Futuras IAs
- **[bulk/errores]**: toda llamada al cursor del driver debe ir dentro de `try/except dialect.loaded_dbapi.Error` con `_wrap_driver_error`, junto con `_begin_if_needed` (P-27).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- Siguientes del bloque: P-13, P-10, P-06 + observación de SQLAlchemy, P-07 (bloques), P-08.
