# TRACEABILITY

## Session metadata
- id: 2026-10-01z-fix-audit-v027
- fecha: 2026-10-01
- rama: develop (base `c79f8de`)
- flujo: `/audit-code` alcance C (`6eb9392..HEAD`: v0.27.0 + 4 commits sin push) → APROBADO CON CONDICIONES → «Si» →
  correcciones M-1 (opción a), B-1, B-2

## AUDIT_CODE (resumen)
- **M-1 (MEDIA, confirmado)**: la conciliación de `ParallelLoadResult` era falsa con una partición fallida que había
  escrito rechazos (sonda: `total_rows=0`, `rows_rejected=1`); `docs/api/bulk_parallel.md` además seguía sin
  `rows_rejected`.
- **B-1 (BAJA)**: tabla de `dump` en `error` con «Filas Rechazadas» > 0 sin nada copiado: sin documentar.
- **B-2 (BAJA, hipótesis)**: `VARCHAR2` > 4000 (EXTENDED) no estaba en la regla del ORA-03106 (banco en `STANDARD`, no
  reproducible aquí).
- B-3 (hipótesis, no corregido): `test_update_auto_increment_mariadb.py` con una URL de MySQL usaría el conector de
  MariaDB contra MySQL. I-1 (`install` no atómico, sin impacto: SQLAlchemy corta en el primer `True`; 8 hilos → 1
  listener) e I-2 (`mariadb_connector` en `ENGINES` por defecto del banco): informativos.

## AI output summary
- M-1 (a): condición «sin `partition_errors`» en el docstring de `ParallelLoadResult` y en `docs/api/bulk_parallel.md`
  (fórmula con `rows_rejected`); `PartitionResult.rows_rejected` aclara que incluye rechazos de intentos deshechos; test.
- B-1: `TableDumpResult` y `docs/api/dump.md`; test.
- B-2: `_lob_like()` en `crud.py` (`_LOB_TYPES` o `String` con longitud > 4000); test con `String(4000)`/`String(5000)`;
  mutación detectada; `docs/api/bulk_crud.md`.
- CHANGELOG `[Unreleased]` → *Fixed*.

## Validación
`ruff`/`mypy` limpios (391); `pytest` 5981 passed, 426 skipped; `tests/integration` 572 passed; `zensical build --strict`
sin avisos.

## Directrices para Futuras IAs
- **[bulk/paralelo]**: cualquier contador de efectos fuera de la BD (rechazos, auditoría estricta) puede incluir intentos
  deshechos; las conciliaciones con `total_rows` solo valen sin `partition_errors`.
- **[bulk/oracle]**: la regla del ORA-03106 depende del tipo declarado; si se amplía (p. ej. a `RAW` largo), ampliar
  `_lob_like` y su test parametrizado.

## Veredicto final
Veredicto: CLOSED
