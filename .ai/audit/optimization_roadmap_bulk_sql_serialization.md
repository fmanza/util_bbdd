# Roadmap de optimización — serialización de ficheros SQL (bulk)

<!-- arquetipo: informativo-libre -->

- **Origen**: [`audit_report_bulk_sql_serialization_20260925.md`](./audit_report_bulk_sql_serialization_20260925.md)
- **Baseline (SQLite, 1M filas)**: INSERT 11,60 s · UPDATE 11,89 s · DELETE 2,16 s
- **Estado (2026-09-25)**: P0 y P1 implementados (`.ai/sessions/2026-09-25-performance-audit-bulk-sql/validation_report_20260925.md`): INSERT 6,09 s, UPDATE 6,64 s con 1M filas en SQLite. P-30 + C-1 resueltos por hotfix (`.ai/sessions/2026-09-25-hotfix-binary-sql-literals/HOTFIX.md`). Pendiente: P-34, P-35.
- **Objetivo**: INSERT/UPDATE ≤ 7,5 s en SQLite/Oracle/SQL Server y ≤ 8,5 s en PostgreSQL/MySQL, con salida byte-idéntica
  (salvo P-30, que cambia la salida a propósito)

## P0 — Medición reproducible (prerrequisito, ~2 h)

1. Añadir `--generar-sql` a `scripts/bench_bulk.py` (o `scripts/bench_sqlgen.py`), con desglose
   normalización/render/escritura por dialecto sin servidor. Partir de `bench_sqlgen.py` de la auditoría.
2. Test de caracterización `tests/unit/bulk/test_sql_generation_golden.py`: salida de
   `generate_insert_sql`/`generate_update_sql`/`generate_delete_sql` para los 5 dialectos sobre el corpus de casos
   límite (`'`, `%`, `%(x)s`, `\`, emoji, `\n`, Decimal, tz, `-0.0`, `inf`, bytes UTF-8 y no UTF-8, JSON, NULL, PK NULL).
   Es la red de seguridad de P1.

## P1 — Sin cambio de salida (~1 día)

| Orden | Hallazgo | Cambio | Mejora esperada | Criterio de aceptación |
|---|---|---|---|---|
| 1 | P-33 | Vía rápida de columnas de texto en `_normalize_column` | −10 % (con SQL y sin SQL) | `dataframe_to_sql_records` idéntico a `normalize_records_for_sql(df.to_dict("records"))` (test existente + Hypothesis con `None`/`pd.NA`/`NaN`/vacíos/espacios) |
| 2 | P-31 | `_LiteralTemplate.render_block` por columnas; `_render_lines` lo usa | −15–21 % | Golden de P0 sin cambios; fallback por fila conservado |
| 3 | P-32 | Procesador precalculado si el compilador no redefine `render_literal_value` | −18 pp en sqlite/oracle/mssql | Golden sin cambios; PG/MySQL siguen por `render_literal_value` |

Flujo recomendado: `/refactor` (sin cambio funcional) → `/audit-code` → benchmark antes/después con P0.

## P2 — Con cambio de salida o mayor esfuerzo

| Hallazgo | Cambio | Nota |
|---|---|---|
| P-30 + C-1 | Literal binario por dialecto dentro de la plantilla (`X'..'` SQLite, `'\x..'::bytea` PG, `HEXTORAW` Oracle, `0x..` MSSQL/MySQL) | Una sola intervención: corrige C-1 y retira el fallback ×12. **Cambia la salida**: CHANGELOG + COMPATIBILITY. Flujo `/hotfix` (C-1) o `/new-feature`. |
| P-34 | Camino SQL por columnas sin `dict` por fila | −8 %; solo si tras P1 sigue haciendo falta |
| P-35 | Cachear la plantilla entre bloques | Medir primero; estimado < 1 % |

## No hacer

- Escritura asíncrona o en hilo del fichero (P-36): la E/S es ≈ 3 %; se perdería la atomicidad `.tmp` → `replace` y la
  propagación síncrona de errores.
- Memoización de literales por valor: ≤ 5 % y no es segura (`Decimal`, `-0.0`, `datetime` con zona).

## Métricas de éxito (medir con P0 tras cada paso)

| Métrica | Baseline | Tras P1 (objetivo) |
|---|---:|---:|
| INSERT 1M SQLite (s) | 11,60 | ≤ 7,5 |
| UPDATE 1M SQLite (s) | 11,89 | ≤ 7,8 |
| Render INSERT µs/fila (sqlite / pg / mysql / oracle / mssql) | 8,3 / 8,9 / 9,1 / 7,5 / 7,4 | ≤ 5,5 / 7,5 / 7,5 / 5,0 / 5,0 |
| Normalización texto µs/celda | 0,52–0,57 | ≤ 0,15 |
| Diferencias en golden multi-dialecto | — | 0 |
| Fila con BLOB no UTF-8 µs/fila (tras P2) | 119–136 | ≤ 10 |
