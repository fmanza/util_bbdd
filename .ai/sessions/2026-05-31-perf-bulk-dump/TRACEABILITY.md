# TRACEABILITY

## Session metadata

- id: 2026-05-31-perf-bulk-dump
- fecha: 2026-05-31
- rama: develop
- skill: new_feature (flujo completo × 3 fases)
- fase: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION (×3) + docs

## Prompt issued

```
Revisar src\util_bbdd\dump y src\util_bbdd\bulk en busca de optimizaciones de rendimiento,
sobre todo cuando trabajan conjuntamente los dos paquetes, queremos los mejores tiempos de
respuesta al insertar registros, no olvidar que se trabaja con cuatro motores de base de
datos (MariaDB, SQL Server, Oracle y PostgreSQL).
```

Sesión dividida en tres ciclos completos de PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
más cierre documental.

---

## Context supplied

- Código fuente: `src/util_bbdd/bulk/` (crud.py, _execution/batch.py, normalize.py, _support/)
- Código fuente: `src/util_bbdd/dump/` (orchestrator.py, _constraints.py, _models.py)
- Historial git reciente (rama develop)
- Suite de tests existente (3556 tests antes de la sesión)

---

## AI output summary

### FASE 1 — Hot-path INSERT / eliminación de overhead interno

#### PLAN + AUDIT_PLAN

Cinco hallazgos verificados directamente en el código:

| ID | Archivo | Descripción | Severidad |
|---|---|---|---|
| F1 | `batch.py:134`, `crud.py:466` | Triple conversión `{str(key): v}` por registro en pipeline INSERT | Crítico |
| F2 | `crud.py:516` | `df.replace({np.nan: None}, inplace=True)` — scan O(n×m) redundante antes de `normalize_records_for_sql` | Crítico |
| F3 | `batch.py:40` | `iterrows()` en `SqlBasedDeleteStrategy` para construir lista de PKs (10–100× más lento que `itertuples`) | Alto |
| F4 | `_constraints.py:302-311` | `_exec_disable_oracle_batch` abría una conexión por tabla en Oracle | Medio |
| F5 | `orchestrator.py:250-254` | Nuevo `BulkCrud` por tabla volcada (N instanciaciones, `_table_cache` descartado N veces) | Medio |

Veredicto AUDIT_PLAN: **GO_CONDICIONAL** — condiciones C1-C3 aplicadas en IMPLEMENT.

#### IMPLEMENT

| Hallazgo | Cambio |
|---|---|
| F1 | Eliminadas comprehensions redundantes en `__ejecutar_batch_stmt` y `_execute_on_connection` |
| F2 | Eliminado `df.replace({np.nan: None})` de `__actualizar_df`; eliminado `import numpy as np` |
| F3 | `iterrows()` → `itertuples(index=False, name=None)` |
| F4 | Único `with self._engine.connect() as conn:` para todas las tablas Oracle; `conn.commit()` explícito |
| F5 | `BulkCrud` creado una vez en `run()` y pasado a `_process_table(crud)` |

#### Tests corregidos

- `test_actualizar_df_replaces_nan_with_none` → `test_actualizar_df_normalizes_columns_nan_unchanged` (contrato nuevo: NaN queda en DF, conversión ocurre en `normalize_sql_literal`)
- 6 decoradores `@patch("...bulk_crud")` → `@patch("...BulkCrud")` en `test_orchestrator.py`

#### Métricas fase 1

| Métrica | Antes | Después |
|---|---|---|
| Tests | 3556 | 3556 |
| Nuevos/modificados | — | 2 tests actualizados |

---

### FASE 2 — Optimizaciones específicas por motor

#### PLAN + AUDIT_PLAN

Tres features para los cuatro motores:

| ID | Motor(es) | Descripción | Ganancia estimada |
|---|---|---|---|
| FA | SQL Server / pyodbc | `cursor.fast_executemany = True` vía event listener `before_cursor_execute` | 5–15× en `executemany` |
| FB | PostgreSQL / psycopg2 | `psycopg2.extras.execute_values` — 1 round-trip por chunk en lugar de N | 3–5× en INSERT masivo |
| FC | SQL Server (`_cleanup`) | TRUNCATE híbrido: `TRUNCATE TABLE` para tablas sin FK entrantes; `DELETE FROM` solo para referenciadas | O(1) vs O(n) en cleanup |

Veredicto AUDIT_PLAN: **GO_CONDICIONAL** — condiciones C1–C4 por feature aplicadas.

#### IMPLEMENT

**FA — `fast_executemany`** (`batch.py`):
- `_fast_executemany_listener` (module-level)
- `_register_fast_executemany(engine)` — guard `isinstance(engine, Engine)` evita `InvalidRequestError` con MagicMock; guard por `event.contains` (ver FASE 3 DB)
- `BatchStatementExecutor.__init__`: parámetro `enable_fast_executemany: bool = True`
- `BulkCrud.__init__`: parámetro `enable_fast_executemany: bool = True` propagado

**FB — `execute_values`** (`batch.py`):
- `InsertExecutionStrategyProtocol` (Protocol)
- `DefaultInsertStrategy` (comportamiento anterior)
- `PostgreSQLExecuteValuesStrategy` — fallback para `TextClause` (override_identity) y `ImportError`
- `InsertStrategyResolver` — inyectable en `BatchStatementExecutor.__init__`
- `BulkCrud.__init__`: parámetro `insert_resolver: InsertStrategyResolver | None = None`

**FC — TRUNCATE híbrido** (`orchestrator.py`):
- `_get_dst_fk_referenced_tables(schema) → frozenset[str]` — análisis FK destino una vez por volcado
- `_cleanup` refactorizado: lógica `use_delete` pasa de bool fijo a set; extracción en `_cleanup_table` y `_cleanup_table_delete_fallback` (reduce complejidad cognitiva a < 15)
- Retry DELETE si TRUNCATE falla (FK de esquema externo no detectada)

#### Tests corregidos/añadidos

- `test_delete_used_for_mssql` → `test_truncate_used_for_mssql_no_fk_references` (nueva semántica: sin FK = TRUNCATE)
- `test_delete_used_for_mssql_referenced_table` (nuevo: FK configurada → DELETE)
- Guard `isinstance(engine, Engine)` en `_register_fast_executemany` — evita `InvalidRequestError` con 3 tests de `test_bulk_sqlserver_identity.py`

#### Métricas fase 2

| Métrica | Antes | Después |
|---|---|---|
| Tests | 3556 | 3557 |
| Nuevos/modificados | — | 2 tests nuevos, 1 renombrado |

---

### FASE 3 — Deuda técnica menor

#### PLAN + AUDIT_PLAN

| ID | Descripción | Veredicto |
|---|---|---|
| DA | `raw_cursor` en `PostgreSQLExecuteValuesStrategy` no se cerraba explícitamente | GO |
| DB | `_FAST_EXEC_ENGINES: set[int]` — riesgo de falso-positivo con `id()` tras GC de engine | GO |

#### IMPLEMENT

- DA: `raw_cursor = conn.cursor()` → `with conn.cursor() as raw_cursor:`
- DB: Eliminada variable `_FAST_EXEC_ENGINES`; `_register_fast_executemany` usa `event.contains(engine, "before_cursor_execute", _fast_executemany_listener)` para deduplicar

#### Métricas fase 3

| Métrica | Antes | Después |
|---|---|---|
| Tests | 3557 | 3557 |
| Nuevos | — | 0 (cambios internos sin contrato nuevo) |

---

### DOCS — Actualización documental

Tres archivos actualizados (sin nuevos archivos):

| Archivo | Cambio |
|---|---|
| `docs/functional/dump-data-export.md` | Fase 4 — tabla SQL Server: refleja estrategia híbrida TRUNCATE/DELETE |
| `docs/api/bulk-crud.md` | Contrato de entrada: 2 filas nuevas (`enable_fast_executemany`, `insert_resolver`); casos especiales: notas sobre FA y FB |
| `docs/api/dump.md` | Fila `truncate_target`: nota SQL Server hybrid; nueva subsección "Optimizaciones automáticas de inserción" |

`mkdocs build` sin errores nuevos (warnings preexistentes en `github_usage_complete_example.md`).

---

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| Ejecutor batch + estrategias INSERT | `bulk/_execution/batch.py` | modificado (+InsertExecutionStrategyProtocol, DefaultInsertStrategy, PostgreSQLExecuteValuesStrategy, InsertStrategyResolver, FA helpers) |
| BulkCrud | `bulk/crud.py` | modificado (+enable_fast_executemany, +insert_resolver, -numpy import, -df.replace, -triple str(key)) |
| ConstraintManager | `dump/_constraints.py` | modificado (Oracle 1 conexión, -_exec_disable_oracle_batch) |
| DumpOrchestrator | `dump/orchestrator.py` | modificado (+_get_dst_fk_referenced_tables, +_cleanup_table, +_cleanup_table_delete_fallback, BulkCrud compartido) |
| Tests orchestrator | `tests/unit/dump/test_orchestrator.py` | modificado (6 patches BulkCrud, 2 tests cleanup renombrados/añadidos) |
| Tests bulk helpers | `tests/unit/test_bulk_crud_helpers.py` | modificado (1 test NaN→nuevo contrato) |
| Doc funcional dump | `docs/functional/dump-data-export.md` | modificado |
| Doc API bulk-crud | `docs/api/bulk-crud.md` | modificado |
| Doc API dump | `docs/api/dump.md` | modificado |

---

## Métricas globales de sesión

| Métrica | Antes | Después |
|---|---|---|
| Tests totales | 3556 | 3557 |
| Tests nuevos | — | +1 |
| Tests modificados | — | +5 |
| ruff | ✅ | ✅ |
| mypy (archivos modificados) | ✅ | ✅ |
| mkdocs build | ✅ | ✅ (sin errores nuevos) |

## Directrices para Futuras IAs

- `BatchStatementExecutor` ahora es stateful con respecto a `_insert_strategy` (seleccionada en `__init__`). Si se añade un nuevo motor con estrategia INSERT específica, añadir a `InsertStrategyResolver.resolve()` y crear clase `XxxInsertStrategy` siguiendo el patrón de `PostgreSQLExecuteValuesStrategy`.
- `_FAST_EXEC_ENGINES` fue eliminado intencionalmente — la deduplicación es vía `event.contains`. No reintroducir.
- `BulkCrud` es compartido entre tablas en `DumpOrchestrator.run()`. Si se necesita aislamiento por tabla, crear una nueva instancia dentro de `_process_table` — pero revisar el coste N instanciaciones.
- La ruta `override_identity=True` (PostgreSQL GENERATED ALWAYS AS IDENTITY) usa `TextClause` en lugar de `Insert` — `PostgreSQLExecuteValuesStrategy` detecta esto con `hasattr(stmt, "table")` y hace fallback. Cualquier nueva ruta que use `text()` directamente seguirá este mismo fallback.
- Optimizaciones pendientes para fase siguiente (no implementadas): `COPY FROM STDIN` PostgreSQL (5–10×, requiere serialización CSV), MariaDB multi-row executemany mode.

## Veredicto final

**CLOSED** — 3557/3557 tests verdes. Documentación actualizada. Sin deuda nueva introducida.
