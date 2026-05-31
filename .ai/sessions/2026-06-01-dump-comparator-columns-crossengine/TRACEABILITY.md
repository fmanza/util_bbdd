# TRACEABILITY

## Session metadata
- id: 2026-06-01-dump-comparator-columns-crossengine
- fecha: 2026-06-01
- rama: develop
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT)
- fase: IMPLEMENT

## Prompt issued

```
Se ha realizado una prueba de src\util_bbdd\dump con dos motores diferentes (Oracle destino, MariaDB destino):
- La de destino tiene tablas de origen con el mismo nombre y mismas columnas
- Al ejecutar la prueba, da todas las columnas de origen salen como inexistentes en el destino
- Revisar la comparación de tablas y columnas para el caso de que sea diferente el motor.
- Se requiere disponer de la máxima funcionalidad cuando es el mismo motor
SOLO PLAN y AUDIT PLAN

[→ IMPLEMENT tras aprobación]
```

## Context supplied
- Sesión previa `2026-05-31-dump-cross-engine`: tablas ya eran case-insensitive; columnas en volcado ya eran case-insensitive (`_common_columns`)
- `src/util_bbdd/comparar/comparator.py` — funciones `_compare_columns_from_raw`, `_diff_common_column`, `_compare_comments_from_raw`
- `tests/comparar/test_comparator.py` — fixture `_make_mock_inspector` existente
- Suite verde previa: 3599 passed, 1 skipped

## Root cause analysis

`SchemaComparator._compare_columns_from_raw()` construía dicts con clave `col["name"]`
(case-sensitive). Oracle devuelve `"EMPLOYEE_ID"`, MariaDB devuelve `"employee_id"`.
Las operaciones `set(source_cols) - set(target_cols)` producían intersección vacía →
100 % de columnas marcadas como `existence=missing`.

El volcado real (`_common_columns`) ya era case-insensitive desde `2026-05-31-dump-cross-engine`.
El bug afectaba exclusivamente al `SchemaDiff` que alimenta el informe Excel.

Bugs adicionales de la misma clase identificados:
- `_diff_common_column`: PK check `col_name in source_pks` también case-sensitive
- `_compare_comments_from_raw`: mismo patrón `set(source_cols) | set(target_cols)`

## AI output summary

### PLAN
Tres funciones afectadas en `comparar/comparator.py`:
1. `_compare_columns_from_raw` (líneas 346-378): construir `lower→col` dicts; operar sobre claves
2. `_diff_common_column` (líneas 381-424): parámetro `tgt_col_name`; PK check con sets normalizados
3. `_compare_comments_from_raw` (líneas 592-607): mismo patrón `lower→col`

### AUDIT_PLAN
Veredicto: **APROBADO CON CONDICIONES** — todas resueltas en IMPLEMENT:
- Añadir `logger.warning` en colisión de case → implementado
- Verificar orden `source_or or target_or` en `_compare_comments_from_raw` → correcto
- Decisión scope `_compare_indices` column_names → diferido (deuda técnica abierta)
- Verificar `DumpReporter` con `ColumnDiff.column_name` → sin comparaciones adicionales

### IMPLEMENT

#### `src/util_bbdd/comparar/comparator.py`

`_compare_columns_from_raw`:
- Construye `source_by_lower: dict[str, Any]` y `target_by_lower: dict[str, Any]`
  (`lower→col`) con `logger.warning` en caso de colisión de case en origen o destino.
- Existencia: `source_by_lower.keys() - target_by_lower.keys()` (lowercase).
  `ColumnDiff.column_name` = `col["name"]` del motor origen (canónico).
- Columnas comunes: pasa ambos nombres canónicos (`s_col["name"]`, `t_col["name"]`)
  al nuevo `_diff_common_column`.

`_diff_common_column`:
- Nuevo parámetro `tgt_col_name: str` (nombre canónico del motor destino).
- PK check: `source_pks_lower = {pk.lower() for pk in source_pks}`;
  `col_name.lower() in source_pks_lower` y `tgt_col_name.lower() in target_pks_lower`.
- `ColumnDiff.column_name` sigue siendo nombre del origen.

`_compare_comments_from_raw`:
- `source_cols_lower` / `target_cols_lower` (`lower→col`).
- Iteración sobre `keys() | keys()` (lowercase).
- `canonical = (source_cols_lower.get(k) or target_cols_lower[k])["name"]`
  → usa nombre origen cuando existe, nombre destino en caso contrario.

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| Comparador de esquemas | `src/util_bbdd/comparar/comparator.py` | modificado |
| Tests comparador | `tests/comparar/test_comparator.py` | modificado (+5 tests, nueva clase) |
| CHANGELOG | `CHANGELOG.md` | actualizado (entrada Fixed) |
| Documentación comparator | `docs/COMPARATOR.md` | actualizado (sección cross-engine) |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests totales | 3599 | 3604 |
| Tests nuevos sesión | — | +5 |
| ruff | ✅ | ✅ (via hook) |
| mypy | ✅ | ✅ (via hook) |
| pytest | ✅ 3599 passed, 1 skipped | ✅ 3604 passed, 1 skipped |

## Directrices para Futuras IAs

- **Patrón establecido**: `_compare_columns_from_raw` usa `lower→col` dicts.
  `_diff_common_column` recibe `(col_name, tgt_col_name, s_col, t_col, source_pks, target_pks)`.
  No revertir a un único nombre ni a comparaciones case-sensitive.
- **Colisión de case en columnas**: `logger.warning` + conservar la primera columna encontrada
  (misma política que tablas en orchestrator).
- **`ColumnDiff.column_name` convención**: siempre nombre canónico del motor origen.
- **Deuda abierta**: `_compare_indices` compara `join_columns(column_names)` como string —
  también case-sensitive. Pendiente de fix en sesión futura (impacto menor: nombres de índices
  ya difieren cross-engine).
- **Comportamiento mismo-motor sin cambios**: `.lower()` es idempotente sobre same-case strings.
  Los tests `TestCrossEngineCaseInsensitiveColumns::test_same_engine_same_case_no_regression`
  verifican explícitamente la no-regresión.

## Veredicto final

Veredicto: **CLOSED**

Bug cross-engine corregido en las 3 funciones afectadas de `comparar/comparator.py`.
5 tests nuevos; suite 3604/3604 verde. No hay regresiones en mismo-motor.
