# TRACEABILITY

## Session metadata
- id: 2026-10-01o-fix-isolate-low-findings
- fecha: 2026-10-01
- rama: develop (base `64e7585`)
- flujo: PLAN + AUDIT_PLAN (`PLAN_AUDIT_PLAN.md`, GO_CONDICIONAL) → «Si» (D-1 no, D-2 a, D-3 a) → IMPLEMENT → VERSION

## Prompt issued
«Los tres hallazgos, PLAN Y AUDIT +PLAN» (B-1, B-3 y B-4 del `/audit-code` de `e2ce535..HEAD`) → «Si».

## AI output summary
- Sondas previas (`probes/`): B-1 confirmado con pyodbc y pymssql; **B-3 reclasificado a MEDIA**: con
  `sqlite3` `autocommit=True` las filas no se confirmaban y la BD quedaba bloqueada; quitar el `BEGIN` no bastaba (el
  `ROLLBACK TO` deja abierto el SAVEPOINT externo). El modo `AUTOCOMMIT` de SQLAlchemy funcionaba.
- `bulk/_support/rejects.py`:
  - B-1: `_rollback_after_data_error`: si el rollback al SAVEPOINT falla, se relanza el error de datos con una nota
    (XACT_ABORT ON) y el error del rollback como `__cause__`.
  - B-3: `_savepoint` decide por `driver.autocommit`: heredado → `BEGIN` como antes; `True` → `ValueError` antes de
    enviar nada.
  - B-4: `RejectsWriter` con `_audit.repository._get_file_lock`; cabecera por `handle.tell() == 0`; primera escritura
    de la instancia aparta un fichero con otra cabecera (`AuditCsvRepository._ruta_apartado`, reutilizado sin cambios).
- Tests: 6 unitarios (rollback fallido, sqlite3 `autocommit=True`, `AUTOCOMMIT` de SQLAlchemy limpio y con rechazo,
  cabecera ajena, 4 hilos sobre la misma ruta) + integración SQL Server `XACT_ABORT ON` (pyodbc y pymssql). Mutación: sin
  el lock compartido, el test de hilos falla 3/3.
- Docs: límites en `docs/api/bulk_crud.md`; CHANGELOG (entrada *Added* de `isolate`, aún sin publicar).

## Validación
`ruff`/`mypy` limpios (390); `pytest` 5953 passed; integración `test_bulk_audit_20261001.py` 91 passed (5 servidores)
+ `isolate and mssql` con pymssql 5 passed; `zensical build --strict` sin avisos.

## Directrices para Futuras IAs
- **[bulk/sqlite]**: con `sqlite3` en Python ≥ 3.12 el modo de transacción lo da `Connection.autocommit`
  (`LEGACY_TRANSACTION_CONTROL`, `True`, `False`), no solo `isolation_level`; con `autocommit=True` no hay forma segura
  de usar SAVEPOINT desde SQLAlchemy.
- **[bulk/rejects]**: un rollback a SAVEPOINT puede fallar (XACT_ABORT ON, conexión rota); el error útil para el usuario
  es el de datos original, con el del rollback como causa.
- **[bulk/csv]**: los CSV que escribe `bulk` (auditoría y rechazos) comparten `_audit.repository._get_file_lock`; solo
  protege entre hilos de un proceso.

## Veredicto final
Veredicto: CLOSED
