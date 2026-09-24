# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-p18-mssql-fast-executemany
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase: RCA + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
Hazlo
```
(Respuesta a la propuesta de commit de la Fase 0 + `/hotfix` de P-01 + P-18.)

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- **Commits previos** de la Fase 0: `290c483` (feat) y `e22e3bb` (docs(ai)).
- **RCA** (confirmada en el código de SQLAlchemy):
  - `_register_fast_executemany` registraba un listener `before_cursor_execute` que ponía `cursor.fast_executemany = True` sin que el dialecto lo supiera.
  - SQLAlchemy solo omite `cursor.setinputsizes()` en executemany cuando `dialect.fast_executemany` es True (`connectors/pyodbc.py:210-214`). Así que llamaba a `setinputsizes()` y luego el listener activaba fast_executemany; pyodbc no admite esa combinación y con DATETIME falla con `HY104` (**P-18**).
  - El dialecto conservaba `use_insertmanyvalues_wo_returning=True`, así que el INSERT iba por insertmanyvalues (`cursor.execute`) y nunca por fast_executemany (**P-01**).
- **AUDIT_PLAN**: GO.
  - Se modifica el dialecto de un engine compartido, con el mismo alcance que el listener y la misma configuración que `create_engine(fast_executemany=True)`.
  - El INSERT pasa a usar fast_executemany de verdad (riesgo conocido de memoria con `NVARCHAR(MAX)`; la salida sigue siendo `enable_fast_executemany=False`).
- **IMPLEMENT**:
  - `src/util_bbdd/bulk/_execution/batch.py`: `_register_fast_executemany` fija `dialect.fast_executemany = True` y `dialect.use_insertmanyvalues_wo_returning = False` (lo mismo que `MSDialect_pyodbc.__init__`). Solo actúa si el dialecto tiene `fast_executemany` (mssql+pyodbc). Eliminados el listener `_fast_executemany_listener` y el import de `event`.
  - `src/util_bbdd/bulk/crud.py`: docstring de `enable_fast_executemany` actualizado (comportamiento real y cifra medida).
  - `tests/unit/bulk/test_fast_executemany.py` (nuevo, 5 tests, DBAPI simulado, sin servidor). Reproducía el fallo antes del fix (3 fallos: dialecto sin `fast_executemany`, listener registrado); tras el fix, 5 passed.
  - `tests/integration/test_bulk_engines.py`: retirado el `xfail` de P-18; el test queda como regresión.
  - `CHANGELOG.md` (`[Unreleased]` → Fixed) y `docs/guides/benchmarks.md` (tabla, aviso y solución de problemas).
- **Validación**:
  - `ruff check src tests` limpio; `mypy src tests/unit/test_protocol_conformance.py tests/unit/bulk/test_fast_executemany.py` limpio.
  - `pytest`: 4462 passed / 19 skipped.
  - Integración 6 motores con pymssql: 17 passed, 1 xfailed (P-05). SQL Server con pyodbc + ODBC 18: 6 passed, 2 xfailed (P-05); el UPDATE con DATETIME pasa.
  - Banco `mssql+pyodbc`, 100K × 3: `baseline` ya iguala a la variante P-01. INSERT 2,03 s (antes 26,0 s, 12,8×); UPDATE 2,98 s (antes fallaba).
  - Build de docs: `benchmarks.md` sin avisos.

## AUDIT_CODE
- Regresiones potenciales:
  - Cualquier código del usuario que comparta el engine mssql+pyodbc usa fast_executemany y deja de recibir `setinputsizes()` en sus executemany. Es el comportamiento documentado de `create_engine(fast_executemany=True)`, y el listener ya imponía fast_executemany a todo el engine.
  - Sentencias INSERT compiladas y cacheadas antes de crear el `BulkCrud` conservan insertmanyvalues: siguen siendo correctas, solo más lentas.
- Edge cases:
  - pymssql y el resto de dialectos no se tocan (test).
  - `enable_fast_executemany=False` no toca el dialecto (test).
  - Registro repetido: idempotente (test).
  - Engine simulado (MagicMock): se omite (comportamiento previo).
- Compatibilidad: sin cambio de API pública. `_fast_executemany_listener` era privado y no se usaba fuera de `batch.py`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix | `src/util_bbdd/bulk/_execution/batch.py` | completado |
| Docstring | `src/util_bbdd/bulk/crud.py` | actualizado |
| Test unitario | `tests/unit/bulk/test_fast_executemany.py` | nuevo |
| Regresión integración | `tests/integration/test_bulk_engines.py` | `xfail` P-18 retirado |
| Changelog / guía | `CHANGELOG.md`, `docs/guides/benchmarks.md` | actualizados |

## Directrices para Futuras IAs
- **[bulk/SQL Server]**: no actives opciones del driver con listeners de cursor si SQLAlchemy tiene un flag de dialecto equivalente. El dialecto ajusta su comportamiento a ese flag: `setinputsizes`, insertmanyvalues.
- **[bulk/bench]**: la variante `p01-mssql-engine-fast-executemany` de `scripts/bench_bulk.py` ya equivale a `baseline` (~1,0×). Se conserva como control de regresión.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (no realizado; pendiente de petición del usuario).
