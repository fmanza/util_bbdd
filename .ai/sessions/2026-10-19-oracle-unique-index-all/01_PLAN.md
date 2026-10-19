# PLAN — Oracle: índices únicos sin constraint en `disable_indexes="all"`

## Inputs (completados con el código real)

| Input | Valor |
|---|---|
| Objetivo | `"all"` en Oracle hace DROP + recreación (DDL de `DBMS_METADATA.GET_DDL`) de los índices únicos sin constraint; si no hay DDL, `"skipped"` + warning |
| Módulos | `metadata/oracle/indexes.py`, `metadata/facts.py`, `bulk/_support/secondary_indexes.py`, `bulk/_models.py`, `_core/exceptions.py`, `bulk/_audit/events.py`, `dump/_audit_events.py`, `dump/reporters.py` |
| API pública | `IndexActionResult.action` admite `"skipped"`; `IndexRebuildError.recovery_ddl` (nuevo atributo, aditivo). Sin parámetros nuevos |
| Contrato de entrada | El de hoy: `disable_indexes="all"` / `manage_indexes="all"` con sus salvaguardas (`disable_constraints=True` o `truncate_target=True`) |
| Contrato de salida | Cada índice único sin constraint aparece en `index_results`: `"recreated"`, `"failed"` (con DDL) o `"skipped"` (con motivo) |
| Reglas de negocio | No inventar DDL: solo el de `GET_DDL`; el DDL se loguea antes del DROP |
| Restricciones | ADR-003, ADR-004 (11g), sin dependencias nuevas |
| Motores | Solo Oracle (el resto sin cambios de comportamiento) |
| Migraciones | No |

## Comprobación en el banco (Oracle 23.26 Free, usuario `bench`)

| Prueba | Resultado |
|---|---|
| `ALTER INDEX <único> UNUSABLE` + INSERT | `ORA-01502`: confirma que la vía de los no únicos no sirve |
| Tipos en `ALL_INDEXES` | `NORMAL`, `NORMAL/REV`, `FUNCTION-BASED NORMAL` |
| `GET_DDL('INDEX', …, USER)` | Devuelve `str` (no LOB) ejecutable tal cual: `CREATE UNIQUE INDEX "BENCH"."X" ON … TABLESPACE "USERS"`, con `REVERSE` y expresiones |
| DROP + `text(ddl)` | Recrea los 4 tipos, incluida una expresión con `'HH24:MI'` |
| Recrear con duplicados | `ORA-01452`: el índice queda borrado |
| `GET_DDL` de un índice de otro esquema sin `SELECT_CATALOG_ROLE` | `ORA-31603` (y `DROP` daría `ORA-01418`) → caso `"skipped"` |
| Índices basados en función | `ALL_IND_COLUMNS` da columnas ocultas `SYS_NC000nn$` que cambian al recrear: el diagnóstico de duplicados tiene que usar `ALL_IND_EXPRESSIONS` |
| Diagnóstico con claves todo-NULL | `GROUP BY` cuenta las filas todo-NULL como duplicadas (falso positivo): Oracle no indexa esas claves |

## Diseño

1. **`metadata/oracle/indexes.py`** (ADR-003):
   - `fetch_unique_indexes_without_constraint_sql()`: índices de la tabla con `uniqueness='UNIQUE'`, `index_type IN
     ('NORMAL','NORMAL/REV','FUNCTION-BASED NORMAL','FUNCTION-BASED NORMAL/REV')`, `temporary='N'`, `status IN
     ('VALID','N/A')` y sin constraint que lo use (mismo `NOT EXISTS` que los secundarios); columnas en orden con
     `column_expression` (`ALL_IND_EXPRESSIONS`, `LEFT JOIN`). Sin `FETCH FIRST` ni sintaxis posterior a 11g.
   - `fetch_index_ddl_sql()`: `SELECT DBMS_METADATA.GET_DDL('INDEX', :name, NVL(UPPER(:owner), USER)) FROM DUAL` (sin
     transformaciones de sesión: no ensucia conexiones del pool).
2. **`metadata/facts.py`**: `UniqueIndexFact` gana `key_sql: tuple[str, ...] = ()` (SQL de cada elemento de la clave:
   columna citada o expresión) y `ddl_error: str | None = None`. `_oracle_unique_indexes` añade un hecho
   `kind="unique_index"` por índice, con `ddl` si `GET_DDL` responde y empieza por `CREATE UNIQUE INDEX`; si no,
   `ddl=None` y `ddl_error` (primera línea del error, p. ej. `ORA-31603`).
3. **`bulk/_support/secondary_indexes.py`**:
   - `IndexStep.skip_reason: str | None = None`.
   - `_plan_unique_oracle`: para `unique_index` con DDL, `DROP INDEX <owner>.<índice>` → DDL (con `:` escapados para
     `text()`), `"recreated"`, `recovery_ddl=ddl`, prioridad `_UNIQUE_INDEX`, `unique_columns=key_sql`; sin DDL, un
     paso con `skip_reason`.
   - `IndexDdlRunner.disable`: un paso con `skip_reason` no ejecuta nada, avisa (warning) y se devuelve para que la
     restauración lo informe; `restore`: lo emite como `IndexActionResult(action="skipped", error_msg=motivo)`.
   - Si falla la recreación de un paso con `recovery_ddl`, se guarda en `runner.recovery_ddl` y `rebuild_error` lo
     añade al mensaje y a `IndexRebuildError.recovery_ddl` (vale también para PostgreSQL e InnoDB, que ya borran).
   - `duplicates_sql` en Oracle: excluye las claves todo-NULL (`WHERE NOT (k1 IS NULL AND …)`).
4. **`IndexActionResult.action`**: `+ "skipped"`; auditoría (`bulk` y `dump`) lo mapea a `"warning"`; el Excel de
   `dump` le da color ámbar.
5. **Los tres consumidores** (`maintenance.py`, `parallel_loader.py`, `dump/_indexes.py`) no cambian: los pasos
   `skipped` viajan en la lista de desactivados y salen en `restore()`.

## Rutas afectadas

- `src/util_bbdd/metadata/oracle/indexes.py`, `src/util_bbdd/metadata/facts.py`
- `src/util_bbdd/bulk/_support/secondary_indexes.py`, `src/util_bbdd/bulk/_models.py`
- `src/util_bbdd/_core/exceptions.py`, `src/util_bbdd/bulk/_audit/events.py`, `src/util_bbdd/dump/_audit_events.py`,
  `src/util_bbdd/dump/reporters.py`
- Docstring de `src/util_bbdd/bulk/crud.py` (`maintenance_scope`)
- Tests: `tests/unit/bulk/test_secondary_indexes_all.py`, `tests/unit/metadata/` (facts), `tests/integration/test_dump_engines.py`
  (`ux_big` pasa a tocarse también en Oracle), `tests/integration/test_bulk_engines.py` (nuevo caso Oracle)
- Docs: `CHANGELOG.md`, `docs/guides/performance_audit_constraints_guide.md`, páginas de `docs/` que listan
  `IndexActionResult.action` o la limitación

## Riesgos

- R1: con duplicados, el índice queda **borrado** (hoy fallaría el INSERT). Mitigación: DDL en el log antes del DROP,
  en el `error_msg` y en `IndexRebuildError.recovery_ddl`. Es la semántica de `"all"` (datos ya validados).
- R2: caída del proceso entre DROP y CREATE → índice perdido; DDL en el log (igual que PostgreSQL hoy).
- R3: 11g no está en el banco: SQL sin sintaxis 12c+; `DBMS_METADATA` existe desde 9i.
- R4: `column_expression` es `LONG`: no se puede usar en `WHERE`/`ORDER BY`; solo se lee.
- R5: dos puntos en literales del DDL (`'X :Y'`) se tomarían como binds en `text()`; se escapan.
