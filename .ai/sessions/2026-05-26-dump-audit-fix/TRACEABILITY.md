# TRACEABILITY

## Session metadata
- id: 2026-05-26-dump-audit-fix
- fecha: 2026-05-26
- rama: develop
- skill: audit_code → implement
- fase: AUDIT_CODE → IMPLEMENT → VALIDATE

## Prompt issued

```
IMPLEMENT todos los hallazgos (no solo los prioritarios) y ejecutar por prioridad
[emitir informe AUDIT_CODE completo sobre src/util_bbdd/dump/ post D1–D8]
```

Seguido de correcciones SonarQube (S8572, S3776 ×2, S4144) y Pylance.

## Context supplied
- `src/util_bbdd/dump/orchestrator.py`
- `src/util_bbdd/dump/_constraints.py`
- `src/util_bbdd/dump/reporters.py`
- `src/util_bbdd/bulk/crud.py`
- `tests/unit/dump/test_constraints.py`
- `tests/unit/dump/test_orchestrator.py`

## AI output summary

### Veredicto auditoría: APROBADO CON CONDICIONES

| Hallazgo | Severidad | Descripción | Archivo |
|---|---|---|---|
| C1 | Crítico | `target_schema` no se propagaba a `bulk_insert_from_df` | `orchestrator.py` + `bulk/crud.py` |
| A1 | Alto | Headers de constraints en Excel col 2-6 pero datos en col 1-5 (desalineados) | `reporters.py` |
| A2 | Alto | Todos los ciclos FK independientes colapsados en una sola lista | `orchestrator.py` |
| A3 | Alto | `__exit__` sin try/except: excepciones de `enable_all()` enmascaraban la original | `_constraints.py` |
| M1 | Medio | `_safe_count` llamado dos veces en path "skipped" (doble roundtrip BD) | `orchestrator.py` |
| M2 | Medio | `_enable_mariadb` llamaba `engine.dispose()` aunque no hubiera `disable` previo | `_constraints.py` |
| M3 | Medio | `_disable_oracle` usaba una sola transacción para todos los constraints (rollback total si falla uno) | `_constraints.py` |
| L1 | Bajo | Sin tests para `_enable_postgresql`/`_disable_postgresql` | `test_constraints.py` |
| L2 | Bajo | Sin tests para `_cleanup` (TRUNCATE/DELETE) | `test_orchestrator.py` |
| L3 | N/A | `__all__` ya presente en `dump/__init__.py` (falso positivo) | — |
| L4 | Bajo | `DumpReporter.__init__` posicionado después de `@staticmethod` (PEP 8) | `reporters.py` |

### Cambios aplicados

**`src/util_bbdd/dump/orchestrator.py`** (C1, A2, M1, S3776)
- C1: `dest_table = f"{cfg.target_schema}.{table}" if cfg.target_schema else table`
- A2: `_topological_sort` delega en `_find_cycle_components` (BFS componentes conexas)
- M1: variable `target_count = self._safe_count(...)` reutilizada en `before`/`after`
- S3776 ×2: extraídos `_find_cycle_components`, `_build_cycle_adj` y `_bfs_component`

**`src/util_bbdd/bulk/crud.py`** (C1)
- `reflect_table`: soporta `"schema.table"` con `.split(".", 1)` → `schema=schema_part` a `Table()`

**`src/util_bbdd/dump/_constraints.py`** (A3, M2, M3, S8572)
- A3: `__exit__` envuelve `enable_all()` en `try/except Exception` con `_log.exception()`
- M2: `_enable_mariadb` retorna `[]` inmediatamente si `_mariadb_listener is None`
- M3: `_exec_disable_oracle` gestiona su propia transacción `engine.begin()` por constraint
- Import huérfano `from sqlalchemy.engine import Connection` eliminado
- S8572: `_log.error("… %s", exc)` → `_log.exception("…")` (incluye traceback automáticamente)

**`src/util_bbdd/dump/reporters.py`** (A1, L4)
- A1: `_write_constraint_section` usa layout 2 filas: título en `offset`, cabeceras en `offset+1` (cols 1-5), datos desde `offset+2`
- L4: `__init__` reubicado antes de los `@staticmethod` helpers

**`tests/unit/dump/test_constraints.py`** (L1, S4144)
- L1: nueva clase `TestConstraintManagerPostgreSQL` con 7 tests
- S4144: `test_enable_without_prior_disable_returns_empty` diferenciado con `insp.get_foreign_keys.assert_not_called()`

**`tests/unit/dump/test_orchestrator.py`** (L2, T4, Pylance)
- L2: nueva clase `TestCleanup` (4 tests: TRUNCATE non-mssql, DELETE mssql, skip_set, `_cleanup` invocado por `run()`)
- T4: nueva clase `TestTargetSchemaPropagation` — verifica que `bulk_insert_from_df` recibe `"staging.orders"` cuando `target_schema="staging"`
- A2-test: `test_multiple_disconnected_cycles_reported_separately` añadido a `TestTopologicalSort`
- Pylance: cast `engine: MagicMock = orch._cfg.target_engine  # type: ignore[assignment]` en `_executed_sql`

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| Orchestrator | `src/util_bbdd/dump/orchestrator.py` | modificado |
| BulkCrud | `src/util_bbdd/bulk/crud.py` | modificado |
| Constraints | `src/util_bbdd/dump/_constraints.py` | modificado |
| Reporter | `src/util_bbdd/dump/reporters.py` | modificado |
| Test constraints | `tests/unit/dump/test_constraints.py` | modificado (+7 tests PG, +diferenciación S4144) |
| Test orchestrator | `tests/unit/dump/test_orchestrator.py` | modificado (+cleanup +T4 +A2 +Pylance cast) |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests dump (unit) | 50 | 63 |
| Regresiones | — | 0 |
| ruff | ✅ | ✅ |
| mypy dump/ + bulk/crud | ✅ | ✅ |
| SonarQube issues | 4 activos | 0 |

## Directrices para Futuras IAs

1. **[dump/orchestrator.py] target_schema en INSERT**: `_process_table` construye `dest_table = f"{cfg.target_schema}.{table}" if cfg.target_schema else table`. Esta variable se pasa a `crud.bulk_insert_from_df`. No pasar el nombre de tabla sin schema si `target_schema` está configurado.

2. **[bulk/crud.py] reflect_table schema.table**: `reflect_table` acepta `"schema.table"` con punto. Lo parsea y pasa `schema=` a SQLAlchemy `Table()`. Cualquier cambio en la firma de `bulk_insert_from_df` debe preservar este contrato.

3. **[dump/_constraints.py] __exit__ logging**: usa `_log.exception()` (no `_log.error("… %s", exc)`) para incluir traceback automáticamente. El `except Exception` lleva `# noqa: BLE001`.

4. **[dump/_constraints.py] M3 Oracle**: cada constraint de Oracle usa su propia transacción `engine.begin()` dentro de `_exec_disable_oracle`. Un fallo en un constraint no revierte los demás. No volver a la transacción global.

5. **[dump/orchestrator.py] ciclos FK**: `_topological_sort` retorna ciclos como lista de listas (una por componente conexa). `_find_cycle_components` → `_build_cycle_adj` + `_bfs_component`. No colapsar todos los ciclos en una sola lista.

6. **[dump/reporters.py] layout Excel constraints**: título en `offset`, cabeceras en `offset+1` (cols 1-5), datos desde `offset+2`. No cambiar este layout sin actualizar también los tests de `test_reporters.py`.

## Veredicto final

**CLOSED** — 6 archivos modificados, 13 tests nuevos, 63/63 pasan, ruff + mypy limpios, 0 issues SonarQube activos.

---

## Segunda iteración: tech_debt dump→bulk (D1–D4)

### Hallazgos implementados

| ID | Severidad | Descripción | Resolución |
|---|---|---|---|
| D1 | Media | `orchestrator.py` acoplado a `BulkCrud` sin abstracción | `dump/_protocols.py`: Protocol `BulkInserter` creado |
| D2 | Baja | `chunk_size` sin documentar su doble semántica | `_models.py` `DumpConfig.chunk_size` docstring extendido |
| D3 | Media | `bulk_crud = BulkCrud` alias no tipado — mypy no valida contrato | `orchestrator._process_table` tipado `crud: BulkInserter` |
| D4 | Baja | `DumpConfig` sin `bulk_audit_path` — inserts nunca auditados | Campo `bulk_audit_path: Path\|None=None` añadido y propagado |
| D5 | Info | `generar_sql=False` hardcodeado | Sin acción (correcto por diseño) |

### Artefactos segunda iteración

| Artefacto | Ruta | Acción |
|---|---|---|
| Protocols | `src/util_bbdd/dump/_protocols.py` | creado |
| Models | `src/util_bbdd/dump/_models.py` | modificado (D2 + D4) |
| Orchestrator | `src/util_bbdd/dump/orchestrator.py` | modificado (D1 + D3 + D4) |
| Public API | `src/util_bbdd/dump/__init__.py` | modificado (re-export `BulkInserter`) |

### Validación segunda iteración

- 63/63 tests pasan (sin regresiones)
- ruff ✅ — mypy ✅

### Directrices para Futuras IAs (D1–D4)

7. **[dump/_protocols.py] BulkInserter Protocol**: contrato mínimo de dump sobre un insertor. Cualquier objeto con `bulk_insert_from_df(df, tabla_destino, generar_sql, ...)` satisface el protocol. Usar `BulkInserter` como tipo de `crud` en `_process_table`, no `BulkCrud` directamente.

8. **[dump/_models.py] bulk_audit_path**: campo opcional en `DumpConfig`. Cuando se pasa, el constructor de `BulkCrud` lo recibe como `audit_csv_path`. Si es `None`, el comportamiento de `BulkCrud` es el default (sin auditoría CSV).

9. **[dump/_models.py] chunk_size doble semántica**: el mismo `chunk_size` se aplica a `pd.read_sql(chunksize=)` (lectura origen) y a `BulkCrud(chunk_size=)` (escritura destino). No dividir en dos campos sin revisión del impacto en tests de integración.

## Veredicto final actualizado

**CLOSED** — 8 archivos totales afectados, 63/63 tests verdes, ruff + mypy limpios, D1–D5 auditados.
