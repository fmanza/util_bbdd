# TRACEABILITY

## Session metadata
- id: 2026-05-25-dump-module
- fecha: 2026-05-25
- rama: develop
- skill: new-feature
- fase: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE (inline) → linting fixes

## Prompt issued
```
Crear módulo src/util_bbdd/dump para volcado de datos de esquema/database origen →
destino entre motores iguales o distintos.

Restricciones:
  - Usar src/util_bbdd/bulk para carga (DataFrames Pandas → bulk insert)
  - Reutilizar src/util_bbdd/comparar para comparación de columnas
  - Orden de carga topológico respetando FK (Kahn)
  - Desactivar constraints antes de la carga y reactivarlas después
  - Si una constraint no puede activarse, reportarlo sin detener el proceso
  - Un Excel con 3 hojas: Auditoría de tablas, Tablas faltantes, Columnas inexistentes
  - Motores: mariadb, oracle, sqlserver, postgresql
  - Carga best-effort (continuar ante errores de tabla)
```

## Context supplied
- `src/util_bbdd/bulk/` — BulkCRUD con `bulk_insert_from_df`
- `src/util_bbdd/comparar/` — SchemaComparator, SchemaDiff, TableDiff, ColumnDiff

## AI output summary

### Módulo dump — 4 archivos nuevos

**`_constraints.py`**
- `ConstraintResult` dataclass: `table_name, constraint_name, dialect, status, error_msg`
- `ConstraintManager(engine, schema)` context manager:
  - MariaDB: `event.listen(engine, "connect", _fk_off)` + `engine.dispose()` — cross-connection safe
  - SQL Server: `ALTER TABLE t NOCHECK CONSTRAINT ALL` (catalog-level)
  - PostgreSQL: `ALTER TABLE t DISABLE TRIGGER ALL` (catalog-level)
  - Oracle: `DISABLE/ENABLE VALIDATE CONSTRAINT` por constraint; filtra `SYS_C%`
  - `__exit__` garantiza `enable_all()` aunque la carga falle

**`orchestrator.py`**
- `DumpConfig` dataclass con `truncate_target=True` (default)
- `DumpOrchestrator.run()` — 6 fases: inspect → sort FK → disable constraints → cleanup → load → enable + report
- `_build_fk_graph` + `_topological_sort` (Kahn): ciclos detectados y añadidos al final con `in_cycle=True`
- Cleanup: SQL Server usa DELETE (TRUNCATE rechazado con FKs catalogadas aunque NOCHECK'd); otros usan TRUNCATE TABLE
- Columnas: intersección case-insensitive origen ↔ destino (Oracle uppercase, PostgreSQL lowercase)
- Import circular resuelto: `DumpReporter` se importa localmente dentro de `run()`

**`reporters.py`**
- `DumpReporter.generate()` → un `.xlsx` con 3 hojas
- Hoja 1 — Auditoría Tablas: volumetría origen vs. destino, estado, posición de carga, ciclos FK, columnas omitidas
- Hoja 2 — Tablas Faltantes: tablas de origen sin correspondencia en destino
- Hoja 3 — Columnas Inexistentes: `ColumnDiff(attribute="existence", source_value="exists")` de `SchemaDiff`
- Sección de constraints con incidencias al pie de Hoja 1

**`__init__.py`**
- Exports: `ConstraintManager, ConstraintResult, DumpConfig, DumpOrchestrator, DumpReporter, DumpResult, TableDumpResult`

### Archivos modificados

- `src/util_bbdd/__init__.py` — re-exports de `DumpConfig, DumpOrchestrator, DumpResult, TableDumpResult`
- `src/util_bbdd/_core/exceptions.py` — añadidas `DumpError, DumpConstraintError, DumpReportError`

### Tests — 50 tests unitarios

- `tests/unit/dump/test_constraints.py` — 17 tests: ConstraintResult, dialectos no soportados, SQL Server, MariaDB, Oracle (filtro SYS_C%), quoting
- `tests/unit/dump/test_orchestrator.py` — 18 tests: DumpConfig, sort topológico (chain, ciclo, auto-ref, mixto), quoting, columnas comunes, run() integración
- `tests/unit/dump/test_reporters.py` — 15 tests: estructura Excel 3 hojas, hoja auditoría, tablas faltantes, columnas inexistentes

## Fixes post-implementación (linting/Pylance)

| Problema | Solución |
|---|---|
| S3776 `_topological_sort` (complejidad 16) | Extraído `_build_fk_graph` helper |
| S3776 `_sheet_audit` (complejidad 21) | Extraídos `_write_audit_rows` + `_write_constraint_section` |
| Pylance `value: object` en `_cell` | Cambiado a `str \| int \| float \| bool \| None` |
| Pylance `wb.remove(wb.active)` con None posible | Guard `if wb.active is not None` |
| Pylance `Cell.column` es `int \| None` | `col or 1` fallback en `_autowidth` |
| Pylance `_mariadb_listener = list[object]` | Cambiado a `MagicMock()` en test |
| Pylance `openpyxl.worksheet.worksheet.Worksheet` | Import directo `from openpyxl.worksheet.worksheet import Worksheet` |
| S5443 `/tmp` en tests | Eliminado `output_dir=Path("/tmp")` (mocked; usa default `Path()`) |
| MagicMock `spec=Engine` bloquea `.dialect` | Eliminado `spec=Engine` en `_make_engine` helper |

## Artefactos modificados

| Artefacto | Ruta | Cambio |
|---|---|---|
| Módulo dump | `src/util_bbdd/dump/` | Nuevo — 4 archivos |
| Tests dump | `tests/unit/dump/` | Nuevo — 3 archivos, 50 tests |
| Package init | `src/util_bbdd/__init__.py` | Re-exports dump añadidos |
| Exceptions | `src/util_bbdd/_core/exceptions.py` | DumpError, DumpConstraintError, DumpReportError |

## Métricas

| Métrica | Valor |
|---|---|
| Tests nuevos | 50 |
| Tests totales | pasan (sin regresiones) |
| ruff | ✅ |
| mypy | ✅ |
| Complejidad cognitiva | ≤ 15 en todos los módulos |

## Decisiones de diseño destacadas

- **MariaDB cross-connection**: `SET FOREIGN_KEY_CHECKS = 0` es session-level; `event.listen` + `dispose()` garantiza que toda conexión nueva del pool nazca con FK checks desactivados
- **SQL Server cleanup**: TRUNCATE rechazado incluso con NOCHECK si existe FK catalogada → DELETE
- **Circular import**: `reporters.py` importa `TableDumpResult` de `orchestrator.py`; `orchestrator.py` importa `DumpReporter` localmente dentro de `run()` para romper el ciclo
- **Columnas case-insensitive**: Oracle devuelve uppercase, PostgreSQL lowercase → comparación `.lower()` preservando el case original para la SQL de lectura

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: Ninguno. 50 tests verdes, ruff + mypy limpios, complejidad cognitiva dentro de límites.
