# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-audit-bulk-4-8
- fecha: 2026-09-24
- rama: develop
- skill: hotfix (hallazgos 4–8 de `2026-09-24-audit-code-bulk`, y 9, aparecido durante el 5)
- fase: RCA + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
Hallazgos 4–8 de la auditoría, todos de severidad baja
```

## Context supplied
- `.ai/sessions/2026-09-24-audit-code-bulk/TRACEABILITY.md` (tabla de hallazgos)
- `src/util_bbdd/bulk/_execution/{parallel_loader,batch}.py`, `_support/{pk_sync,sql_helpers}.py`, `crud.py`

## AI output summary

| # | Hallazgo | Corrección | Test / evidencia (con el código anterior → ahora) |
|---|---|---|---|
| 4 | `_hoist_constraints_for_workers` citaba el nombre recibido sin normalizar | `_resolve_table()` (reflexión con `BulkCrud`) + `format_table` del dialecto; se eliminan `_quote_mssql_table` y `_quote_pg_table` | Integración `…_with_differently_cased_name` (4 motores sin MySQL/MariaDB): PostgreSQL falla → pasa. Unitario: la comprobación y el DDL usan la tabla reflejada |
| 5 | `pk_sync`: PostgreSQL `pg_get_serial_sequence` sin comillas; Oracle `UPPER()` | PostgreSQL: `_qt(...)`. Oracle: `dialect.denormalize_name` | Integración `test_sync_pk_sequences_in_mixed_case_schema` (PostgreSQL): `schema "zzutilbbdd_…" does not exist` → pasa |
| 9 (nuevo) | Oracle: `ALTER SEQUENCE ISEQ$$_n RESTART` → `ORA-32793` siempre (también con nombres normales) | `ALTER TABLE … MODIFY (col GENERATED {ALWAYS \| BY DEFAULT [ON NULL]} AS IDENTITY (START WITH n))`, con tipo leído de `*_tab_identity_cols` + `*_tab_columns.default_on_null` | Integración `test_sync_pk_sequences_with_name_that_needs_quoting` (6 motores): Oracle falla → pasa. Verificado en Oracle 23: se conservan tipo, `ON NULL` e `INCREMENT BY 5` (ids siguientes 101, 106). 3 unitarios adaptados + 2 nuevos |
| 6 | Tabla sin sanear en el nombre del fichero de `generar_sql` | `_safe_filename_part()` (también caracteres de control) para base de datos y tabla | 6 casos en `test_generate_sql_filename.py`: fallaban 4 → pasan |
| 7 | DELETE ignoraba `commit_every_n_chunks` | `DeleteBatchExecutor(commit_every_n_chunks=…)`: commit cada N lotes, fuera (`connect()` + commit final) y dentro de la sesión | `test_delete_commit_cadence.py` (4, trigger de SQLite que hace fallar el tercer lote): fallaban 2 → pasan |
| 8 | MySQL/MariaDB `DISABLE/ENABLE KEYS`: commit implícito (rompía la atomicidad) | Solo si `information_schema.TABLES.ENGINE` es MyISAM/Aria; si no, INFO y se omite. Restauración solo si se deshabilitó | Integración `…_keeps_session_atomic_on_innodb` (MySQL, MariaDB): quedaban filas → 0. Unitarios adaptados (MyISAM/Aria sí, InnoDB no) |

- **Validación**:
  - `ruff check src tests` y `mypy` limpios. `ruff` marca `scripts/bench_dump.py`, ajeno a esta sesión;
  - suite sin URLs 4783 passed / 160 skipped;
  - con las URLs del banco 4943 passed, 0 skipped, 0 warnings.

## AUDIT_CODE
- Regresiones potenciales:
  - 4: el loader refleja la tabla una vez más antes de los workers (~1–60 ms);
  - 7: con `commit_every_n_chunks`, un DELETE que falla deja borrados los lotes confirmados, igual que INSERT y UPDATE (antes era atómico sin querer);
  - 8: `disable_indexes=True` ya no hace nada en InnoDB, algo que el servidor ya ignoraba.
- Compatibilidad: 9 exige Oracle 12c+ (igual que antes); `default_on_null` existe desde 12c.
- Tests existentes que fijaban el comportamiento anterior y se han adaptado:
  - `test_pk_sync.py`: 3 tests de Oracle con `ALTER SEQUENCE`;
  - `test_maintenance_scope.py`: 2 tests de MySQL que exigían `DISABLE KEYS` siempre.

## Directrices para Futuras IAs
- **[Oracle]**: las secuencias de columnas identity (`ISEQ$$_n`) no se alteran. Se usa `ALTER TABLE … MODIFY … AS IDENTITY (START WITH n)` repitiendo el tipo de generación.
- **[nombres]**: en el catálogo de Oracle, usar `dialect.denormalize_name`, no `UPPER()`. En PostgreSQL, cualquier función que analice un identificador (`pg_get_serial_sequence`, `regclass`) recibe el nombre citado.
- **[MySQL]**: todo `ALTER TABLE` hace commit implícito. Dentro de una sesión atómica, no ejecutarlo si no tiene efecto.
- **[tests]**: los tests con mocks que fijan SQL concreto pueden consolidar un fallo, como el de `ALTER SEQUENCE` en Oracle. Contrastar con el motor real.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commits (pendientes de petición del usuario).
