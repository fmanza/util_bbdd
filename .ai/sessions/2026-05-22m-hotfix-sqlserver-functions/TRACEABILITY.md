# TRACEABILITY — 2026-05-22m-hotfix-sqlserver-functions

## Resumen

**Fase**: HOTFIX
**Rama**: develop
**Fecha**: 2026-05-22
**Skill**: hotfix
**Estado**: CLOSED ✅

---

## Solicitud

El usuario reportó que las rutinas FUNCTION (PROCEDURE/FUNCTION) seguían sin aparecer
en los reportes de migración al usar `src/util_bbdd/migrate` con SQL Server como fuente.

---

## Root Cause Analysis

### Causa raíz confirmada

`build_sqlserver_routines_query()` en
`src/util_bbdd/metadata/sqlserver/_adapter_helpers.py`
usaba `FROM sys.procedures sp` como tabla base.

`sys.procedures` en SQL Server es una *catalog view* que **solo contiene stored
procedures** (type `'P'`). Las funciones existen en `sys.objects` con tipos:

| Type | Descripción |
|------|-------------|
| `FN` | Scalar function |
| `IF` | Inline table-valued function |
| `TF` | Multi-statement table-valued function |

Esos tipos **nunca aparecen** en `sys.procedures`, por lo que el inventario de
rutinas omitía silenciosamente todas las funciones.

El `CASE sp.type WHEN 'FN' THEN 'FUNCTION'` era código muerto: la expresión
nunca evaluaba a verdadero porque `sys.procedures` no tiene filas de tipo `FN/IF/TF`.

### Por qué los tests no detectaron el bug antes

El test `test_multiple_routines` en `test_routines_sqlserver_extractor.py` inyectaba
filas de tipo FUNCTION directamente mediante `execute_custom_many.side_effect`,
**sin pasar por la SQL query real**. El mock ocultaba el defecto SQL.

---

## Fix aplicado

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `src/util_bbdd/metadata/sqlserver/_adapter_helpers.py` | `FROM sys.procedures` → `FROM sys.objects o WHERE o.type IN ('P','FN','IF','TF')` |
| `src/util_bbdd/migrate/extractors/sqlserver.py` | Docstring actualizado (elimina nota "v1 limitation") |
| `tests/unit/migrate/test_routines_sqlserver_extractor.py` | 3 tests nuevos: FN escalar, IF (TVF inline), tipo UNKNOWN |
| `tests/unit/migrate/test_sqlserver_extractor.py` | Mock `_make_routines_manager` actualizado: `SYS.PROCEDURES` → `SYS.OBJECTS`; orden `SYS.SQL_MODULES` primero |

### SQL antes/después

**Antes** (solo procedures):
```sql
SELECT sp.name, CASE sp.type WHEN 'P' THEN 'PROCEDURE' WHEN 'FN' THEN 'FUNCTION' ELSE 'UNKNOWN' END, ...
FROM sys.procedures sp
INNER JOIN sys.schemas s ON sp.schema_id = s.schema_id
WHERE sp.is_ms_shipped = 0
AND s.name = %(schema_name)s
ORDER BY sp.name
```

**Después** (procedures + funciones):
```sql
SELECT o.name, CASE o.type WHEN 'P' THEN 'PROCEDURE' WHEN 'FN' THEN 'FUNCTION' WHEN 'IF' THEN 'FUNCTION' WHEN 'TF' THEN 'FUNCTION' ELSE 'UNKNOWN' END, ...
FROM sys.objects o
INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
WHERE o.is_ms_shipped = 0
AND o.type IN ('P', 'FN', 'IF', 'TF')
AND s.name = %(schema_name)s
ORDER BY o.name
```

---

## Validación

- 3311 tests pasando, 0 fallos (vs. 3308 antes del fix + 3 tests nuevos)
- `test_scalar_function_extracted_as_function_type`: FN → FUNCTION ✅
- `test_inline_tvf_extracted_as_function_type`: IF → FUNCTION ✅
- `test_unknown_type_row_included_with_unknown_type`: UNKNOWN pass-through ✅
- No hay regresión en stored procedures (sys.objects incluye type 'P') ✅
- Otros motores no afectados (Oracle, MariaDB, PostgreSQL usan catálogos correctos) ✅

---

## Commit message sugerido

```
fix(migrate): SQL Server incluye FUNCTION escalares e inline-TVF en extracción

build_sqlserver_routines_query() usaba sys.procedures que solo contiene
stored procedures (type 'P'). Cambiado a sys.objects con type IN ('P','FN','IF','TF')
para incluir también funciones escalares (FN) e inline/multi-statement TVF (IF/TF).

El CASE WHEN 'FN' anterior era código muerto — sys.procedures nunca tiene ese tipo.

Tests: 3 nuevos en test_routines_sqlserver_extractor.py; mock _make_routines_manager
en test_sqlserver_extractor.py actualizado a sys.objects + orden de chequeo correcto.

Closes: reporte "FUNCTION no aparece en reportes migrate SQL Server"
```

---

## Directrices para Futuras IAs

- **SQL Server `sys.procedures`** es solo stored procedures. Para inventariar
  PROCEDURE + FUNCTION siempre usar **`sys.objects`** con `type IN ('P','FN','IF','TF')`.
- Al hacer mock de `_make_routines_manager` para SQL Server, verificar que el
  `side_effect` chequea `SYS.SQL_MODULES` **antes** que `SYS.OBJECTS` — la query
  de body hace JOIN a `sys.objects` también y el orden importa.
- El test `test_multiple_routines` ya cubre FUNCTION a nivel de extractor, pero
  NO prueba el SQL generado. Añadir siempre un test de contenido SQL cuando el
  bug sea un query incorrecto.
