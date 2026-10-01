# TRACEABILITY

## Session metadata
- id: 2026-10-01r-spike-oracle-batcherrors
- fecha: 2026-10-01
- rama: develop (base `90b58e3`)
- flujo: Fase 2 (P-C, spike S-5) del plan `../2026-10-01p-plan-bulk-pending-2/PLAN_AUDIT_PLAN.md`; solo medición

## Prompt issued
«Si» (seguir con la Fase 2).

## AI output summary
- `s5_batcherrors.py` (equivalencia por tipo, errores de fila, banco 1M) y `s5_ora03106.py` (matriz del fallo del
  driver); informe `S-5_batcherrors.md`; logs `s5_types.log`, `s5_ora03106.log`, `s5_bench.log`.
- Resultado: datos idénticos; aísla también ORA-12899/01400/01438; 10 malas 1,06× (bisección 1,22×); ORA-03106 en UPDATE
  con CLOB de 9000 y una fila mala. Veredicto GO_CONDICIONAL (INSERT/DELETE; UPDATE sin columnas LOB).

## Validación
Sin cambios en `src/` ni `tests/`.

## Directrices para Futuras IAs
- **[bulk/oracle]**: SQLAlchemy envía el executemany de Oracle con `cursor.executemany` (`use_insertmanyvalues=False`);
  el evento `do_executemany` permite añadir `batcherrors=True` sin perder los procesadores de bind ni `setinputsizes`.
- **[bulk/oracle]**: oracledb 4.0.1 thin da ORA-03106 en UPDATE con un bind CLOB grande (9000) y una fila con error si
  se usa `batcherrors`; con 4001 o en INSERT no.

## Veredicto final
Veredicto: CLOSED (spike)
