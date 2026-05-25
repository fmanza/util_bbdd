# TRACEABILITY

## Session metadata
- id: 2026-05-25-bulk-sqlserver-identity-insert
- fecha: 2026-05-25
- rama: develop
- skill: new_feature
- fase: IMPLEMENT → AUDIT_CODE → VERSION

## Prompt issued

```
Revisar e implementar soporte explícito en src/util_bbdd/bulk para generar ficheros SQL
ejecutables en SQL Server cuando el DataFrame inserta valores manuales en columnas IDENTITY.

En generar_sql=True y dialecto mssql, envolver los INSERT con:
  SET IDENTITY_INSERT <tabla> ON;
  ...INSERT...
  SET IDENTITY_INSERT <tabla> OFF;
```

## Context supplied
- `src/util_bbdd/bulk/crud.py` — `__prepare_insert_operation`, flujo `generar_sql`
- `src/util_bbdd/bulk/_support/sql_helpers.py` — `generate_insert_sql`, helpers existentes
- `tests/unit/test_bulk_override_identity.py` — patrón de tests del módulo bulk

## AI output summary

### Análisis

El dialecto MSSQL de SQLAlchemy gestiona `SET IDENTITY_INSERT ON/OFF` automáticamente
en ejecución real (`generar_sql=False`). Pero en el modo `generar_sql=True`, el SQL se
compila como literal y la cláusula no se añade → el fichero SQL falla en SQL Server si
contiene valores explícitos para una columna IDENTITY.

La detección usa `getattr(col, "identity", None) is not None` (más precisa que
`table._autoincrement_column`, que retorna True para cualquier PK entera sin Identity).

### Diseño adoptado

| Decisión | Alternativa | Razón |
|---|---|---|
| `getattr(col, "identity", None) is not None` | `table._autoincrement_column` | Evita falsos positivos en PKs enteras sin Identity() explícita |
| Wrapping solo en `generate_sql_lines` | Wrapping en ejecución | Ejecución real ya delega en SQLAlchemy; cambio solo afecta el path de generación |
| `dialect.identifier_preparer.format_table(table)` | Nombre de tabla hardcodeado | Maneja schema + quoting correctamente para cualquier configuración |
| ON y OFF una sola vez fuera del bucle | Por registro | Correcto semánticamente; IDENTITY_INSERT es a nivel de sesión, no de statement |

### IMPLEMENT

**`_support/sql_helpers.py`**
- `should_wrap_identity_insert(table, insert_cols, dialect) -> bool`:
  retorna True solo si `dialect.name == "mssql"` y alguna columna de `insert_cols`
  tiene `getattr(col, "identity", None) is not None`.
- `wrap_identity_insert_sql(sql_lines, table, dialect) -> list[str]`:
  devuelve `[SET ... ON, *sql_lines, SET ... OFF]`. Table formateada con
  `dialect.identifier_preparer.format_table(table)`.

**`crud.py`**
- Importa `should_wrap_identity_insert`, `wrap_identity_insert_sql`.
- En `__prepare_insert_operation`, tras el bloque PostgreSQL y antes del default:
  si `should_wrap_identity_insert`, devuelve `_PreparedBulkOperation` cuya
  `generate_sql_lines` envuelve el resultado de `generate_insert_sql`.
  La `execute` (generar_sql=False) permanece igual; SQLAlchemy gestiona solo.

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| SQL helpers | `src/util_bbdd/bulk/_support/sql_helpers.py` | modificado (+25 líneas) |
| CRUD bulk | `src/util_bbdd/bulk/crud.py` | modificado (+14 líneas) |
| Tests MSSQL identity | `tests/unit/test_bulk_sqlserver_identity.py` | creado (12 tests) |

## Tests añadidos

| Test | Qué verifica |
|---|---|
| `test_should_wrap_returns_true_for_mssql_with_identity_col` | Detección correcta con Identity() en MSSQL |
| `test_should_wrap_returns_false_when_identity_col_absent_from_records` | Identity en tabla pero no en records → False |
| `test_should_wrap_returns_false_for_mssql_without_identity_col` | PK entera sin Identity() → False (sin falso positivo) |
| `test_should_wrap_returns_false_for_non_mssql_dialect` | SQLite, PG, Oracle, MySQL → False |
| `test_wrap_adds_on_at_start_and_off_at_end` | Estructura ON/OFF correcta |
| `test_wrap_preserves_insert_lines_in_middle` | Las líneas INSERT se conservan en posición |
| `test_wrap_on_and_off_appear_exactly_once` | ON y OFF aparecen exactamente una vez |
| `test_wrap_uses_preparer_format_table` | Schema incluido si identifier_preparer lo devuelve |
| `test_generate_sql_mssql_identity_wraps_with_on_off` | Flujo completo: ON + 2 INSERTs + OFF = 4 líneas |
| `test_generate_sql_mssql_no_identity_col_no_wrap` | Sin Identity() → sin wrapping |
| `test_generate_sql_other_dialect_no_wrap` | Otro dialecto → sin wrapping |
| `test_execute_path_unchanged_does_not_call_wrap` | generar_sql=False no altera el stmt de ejecución |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests totales | 3007 | 3019 |
| Tests nuevos sesión | — | +12 |
| Regresiones | — | 0 |
| ruff | ✅ | ✅ |
| mypy | ✅ | ✅ |

## Veredicto final

**CLOSED** — generación SQL en MSSQL envuelve correctamente los INSERT con
`SET IDENTITY_INSERT ON/OFF` cuando se detecta columna IDENTITY en los registros.
Ejecución directa sin cambios. Otros motores sin efecto. 12 tests nuevos, 0 regresiones.
