# TRACEABILITY

## Session metadata
- id: 2026-05-26-dump-comparar-audit-impl
- fecha: 2026-05-26
- rama: develop
- skill: audit_code + implement
- fase: AUDIT_CODE → IMPLEMENT

## Prompt issued
```
/audit-code

Revisa src\util_bbdd\dump y src\util_bbdd\comparar, tiene dependencias, revisar.
Quiero bugs, edge cases, compatibilidad y tests faltantes.
```
Seguido de: `IMPLEMENT`

## Context supplied
- `src/util_bbdd/dump/` — orchestrator.py, _constraints.py, _sql_utils.py, _models.py, _protocols.py, reporters.py, __init__.py
- `src/util_bbdd/comparar/` — comparator.py, _routine_fetchers.py, contracts.py, models.py, reporters/
- `tests/unit/dump/` — test_orchestrator.py, test_constraints.py
- `tests/comparar/test_comparator.py`
- Estado git: rama develop, 6 commits previos de audit+tech-debt sobre dump y comparar

## AI output summary
- Auditado dump/ y comparar/ como módulos interdependientes (dump → comparar; dump.reporters importa SchemaDiff)
- Identificado B1: `_process_table()` construía `dest_table` con concatenación cruda en lugar de `quote_table()` — rotura con schemas/tablas reservadas
- Identificado B2: `get_routines_mariadb()` usaba `str(row["Create Procedure"])` sin guard `or ""`; cuando usuario no tiene `SHOW CREATE` el valor es NULL → `"None"` literal → falsos positivos en comparación DDL
- Identificado B3: `comparator.py` usaba `str(value or "")` para defaults de columna; colapsa `0`, `False` y `None` a `""` — columna `DEFAULT 0` no genera `ColumnDiff` frente a `DEFAULT NULL`
- Identificado TC1 faltante: test que verifica `dest_table` usa quoting con schema reservado
- Identificado TC2 faltante: tests que verifican NULL DDL MariaDB produce `""` no `"None"`
- Identificado TC5 faltante: test que verifica error en chunk parcial deja `status="error"` y conserva `error_msg`
- Identificado TC6 faltante: tests de `__exit__` de `ConstraintManager` — propagación excepción original + `constraint_results` accesible
- Aplicado B1: `orchestrator.py:224` — `dest_table = quote_table(table, cfg.target_schema, cfg.target_engine)`
- Aplicado B2: `_routine_fetchers.py:101,118` — `str(row[...] or "")` con guard `or ""`
- Aplicado B3: `comparator.py:403–406` — `s_default_raw = s_col.get("default")` + `"" if s_default_raw is None else str(s_default_raw)` (x2)
- Añadidos TC1 + TC5 en `tests/unit/dump/test_orchestrator.py`
- Añadidos TC6 (×2) en `tests/unit/dump/test_constraints.py`
- Añadidos TC2 (×2) + B3 (×2) en `tests/comparar/test_comparator.py`

## Artefactos generados

| Artefacto                            | Ruta                                                         | Estado     |
|--------------------------------------|--------------------------------------------------------------|------------|
| Fix B1 quoting dest_table            | src/util_bbdd/dump/orchestrator.py:224                       | completado |
| Fix B2 MariaDB NULL DDL              | src/util_bbdd/comparar/_routine_fetchers.py:101,118          | completado |
| Fix B3 default=0/False comparación   | src/util_bbdd/comparar/comparator.py:403–406                 | completado |
| Tests TC1 + TC5 orchestrator         | tests/unit/dump/test_orchestrator.py                         | completado |
| Tests TC6 ×2 constraints __exit__    | tests/unit/dump/test_constraints.py                          | completado |
| Tests TC2 ×2 + B3 ×2 comparator     | tests/comparar/test_comparator.py                            | completado |

## Directrices para Futuras IAs

- **[dump/orchestrator.py]**: `quote_table()` está importado de `_sql_utils` y debe usarse siempre que se construya una referencia `schema.table`; concatenación cruda rompe dialectos con palabras reservadas.
- **[comparar/_routine_fetchers.py]**: Los campos `Create Procedure` / `Create Function` en MariaDB/MySQL son NULL cuando el usuario no tiene privilegio SHOW CREATE. Usar siempre `value or ""` antes de `str()`.
- **[comparar/comparator.py]**: Los defaults de columna pueden ser `0`, `False`, o `None` como valores Python legítimos. Nunca usar `or ""` para normalizarlos; usar `is None` como guard explícito.
- **[dump ↔ comparar]**: Hay dependencia real `dump → comparar` (`orchestrator.py` importa `SchemaComparator`, `reporters.py` importa `SchemaDiff`). Agentes de exploración automática reportaron erróneamente "no hay dependencias"; verificar con `grep` directo.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Ejecutar `pytest` completo para confirmar que los 6 nuevos tests pasan (no se ejecutó suite completa en sesión)
