# TRACEABILITY

## Session metadata
- id: 2026-09-25c-hotfix-dump-pk-sync-truncate
- fecha: 2026-09-25
- rama: develop (base `e0fb600`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-02 y PD-03 de `2026-09-25-performance-audit-dump`, reproducidos de nuevo en `2026-09-25b-performance-audit-dump-delta` (roadmap, pasos 0.2 y 0.3)

## Prompt issued
```
/hotfix PD-02 y PD-03 del módulo dump (roadmap pasos 0.2 y 0.3).
Criterios: identidad 3/3 en PG y Oracle y pk_sync_results no vacío; redump PG 3/3 success. Tests que lo cubran.
```

## RCA
- **PD-02**: `DumpOrchestrator._sync_pk_sequences` filtraba `effective_dst_order` (nombres sin esquema, `customers`) contra `crud._table_cache`, cuyas claves son el nombre lógico de la carga (`dump_dst.customers` con `target_schema`, `orchestrator.py:416`). Ninguna coincidía: devolvía `None` sin avisar y la Fase 5a no sincronizaba nada. En PostgreSQL y Oracle el siguiente INSERT sin PK chocaba (`duplicate key` / `ORA-00001`); MySQL, MariaDB, SQL Server y SQLite no se veían afectados porque ajustan la identidad al insertar valores explícitos.
- **PD-03**: `_cleanup` truncaba tabla a tabla. PostgreSQL rechaza `TRUNCATE` de una tabla referenciada por FK salvo que las tablas que la referencian vayan en la misma sentencia, aunque estén vacías y con `DISABLE TRIGGER ALL`. El error se degradaba a WARNING, el destino conservaba sus filas y la carga fallaba con `UniqueViolation`.

## FIX (mínimo)
- `orchestrator.py::_sync_pk_sequences`: construye el mismo nombre lógico que la carga (`f"{schema}.{t}"` si hay `target_schema`) antes de filtrar y sincronizar.
- `orchestrator.py::_cleanup` + `_truncate_together` (nuevo): en PostgreSQL con más de una tabla, un único `TRUNCATE TABLE t1, t2, …` sin `CASCADE`; si falla (p. ej. FK desde una tabla ajena al volcado), rollback, WARNING y limpieza tabla a tabla como antes. El resto de motores no cambia.
- `docs/api/dump.md` (fila `truncate_target`) y `CHANGELOG.md` (`[Unreleased]` → *Fixed*).

## Validación
- **Tests nuevos** (`tests/unit/dump/test_orchestrator.py`), los 5 fallan sin el arreglo (`git stash` del fuente) y pasan con él:
  - `TestCleanup::test_postgresql_truncates_all_tables_in_one_statement`, `…_falls_back_to_table_by_table_if_joint_truncate_fails`, `…_joint_truncate_uses_target_schema`;
  - `TestSyncPkSequencesLogicalName::test_target_schema_syncs_tables_cached_by_logical_name` y E2E `test_sqlite_dump_with_target_schema_runs_pk_sync` (volcado real a un esquema adjunto de SQLite; espía la llamada a `BulkCrud.sync_pk_sequences`, porque SQLite no tiene contadores y devuelve `[]`).
  - `test_truncate_used_for_non_mssql` pasa a Oracle: con PostgreSQL afirmaba dos TRUNCATE separados, que era el comportamiento erróneo.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src tests/unit/test_protocol_conformance.py` limpio; `pytest tests/unit`: **4494 passed**.
- **Banco real** (`scripts/bench_dump.py`, `large` 3,5M filas, `results/results.jsonl`):

| Motor | Variante | n | Total (mediana) | Tablas `success` | Verificación | Identidad | `pk_sync` |
|---|---|---|---|---|---|---|---|
| PostgreSQL | baseline | 3 | 18,4 s | 3/3 | 3/3 | **3/3** (antes 0/3) | 3 × `synced` (0,02–0,07 s) |
| PostgreSQL | redump | 3 | 18,3 s | 3/3 (antes 1/3) | 3/3 | 3/3 | 3 × `synced` · `cleanup` 0,05 s |
| Oracle | baseline | 3 | 58,9 s | 3/3 | 3/3 | **3/3** (antes 0/3) | 3 × `synced` (0,04–0,20 s) |

## Regresión
Una repetición por motor (`large`), frente a la mediana de la sesión delta:

| Motor | Total | Delta (mediana) | Tablas `success` | Verificación | Identidad | `pk_sync` |
|---|---|---|---|---|---|---|
| MySQL | 57,9 s | 57,0 s | 3/3 | OK | OK | 3 × `synced` (0,04 s; antes no se ejecutaba) |
| MariaDB | 54,9 s | 52,9 s | 3/3 | OK | OK | 3 × `synced` (0,06 s; antes no se ejecutaba) |
| SQL Server (pyodbc) | 69,6 s | 65,8 s | 3/3 | OK | OK | 3 × `synced` (0,03 s; antes no se ejecutaba) |
| SQLite | 21,2 s | 21,3 s | 3/3 | OK | OK | `[]` (sin contadores) |

Diferencias dentro del ruido de una repetición (±10 %); el coste añadido de la Fase 5a es ≤ 0,2 s en todos los motores.

## AUDIT_CODE
- **Comportamiento nuevo con `target_schema`**: la Fase 5a ahora se ejecuta también en MySQL/MariaDB (`ALTER TABLE … AUTO_INCREMENT`) y SQL Server (`DBCC CHECKIDENT`), donde antes no hacía nada. Los errores por tabla siguen capturados como `status="error"` y no interrumpen el volcado; requiere los permisos ya documentados en `BulkCrud.sync_pk_sequences`.
- **Sin `target_schema`**: nombres idénticos a los anteriores; sin cambio.
- **PostgreSQL, TRUNCATE conjunto**: mismos bloqueos (`ACCESS EXCLUSIVE`) que tabla a tabla, tomados a la vez. Sin `CASCADE`, nunca vacía tablas ajenas al volcado. Con una sola tabla se mantiene la ruta anterior. No reinicia las identidades (`RESTART IDENTITY` no se añade): la Fase 5a las ajusta.
- **Edge cases**: tablas en ciclos FK (van en la misma sentencia, que PostgreSQL resuelve); identificadores con palabras reservadas (citados con `quote_table`, como antes); fallo del TRUNCATE conjunto (rollback antes del reintento, cubierto por test).
- **Compatibilidad**: sin cambios de API pública. `DumpResult.pk_sync_results` pasa de `None` a lista con `target_schema` en motores con identidad.

## VERSION
- Commit: `fix(dump): PK sync con target_schema y limpieza de PostgreSQL con FK (PD-02, PD-03)`
- Changelog: dos entradas en `[Unreleased]` → *Fixed*.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump]**: el nombre lógico de una tabla destino es `f"{target_schema}.{tabla}"` (o `tabla`); es la clave de `BulkCrud._table_cache`. Cualquier búsqueda en esa caché debe usar el mismo formato.
- **[dump/pg]**: para vaciar tablas relacionadas por FK en PostgreSQL, TRUNCATE conjunto; `DISABLE TRIGGER ALL` no basta para truncar tabla a tabla.
- **[tests]**: SQLite no tiene contadores de PK que sincronizar (`sync_pk_sequences` devuelve `[]`): para probar la Fase 5a en SQLite hay que espiar la llamada, no el resultado.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Resto de la Fase 0 del roadmap (PD-01, PD-04, PD-05, PD-06 parcial, PD-07, PD-08, PD-09).
