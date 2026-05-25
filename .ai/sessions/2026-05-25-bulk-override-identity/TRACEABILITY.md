# TRACEABILITY

## Session metadata
- id: 2026-05-25-bulk-override-identity
- fecha: 2026-05-25
- rama: develop
- skill: new_feature
- fase: IMPLEMENT → AUDIT_CODE → VERSION

## Prompt issued

```
Revisar e implementar soporte explícito en src/util_bbdd/bulk para insertar valores manuales
en columnas PostgreSQL GENERATED ALWAYS AS IDENTITY.

Añadir override_identity: bool = False en bulk_insert_from_df.
```

## Context supplied
- `src/util_bbdd/bulk/crud.py` — clase `bulk_crud`, métodos `bulk_insert_from_df`, `__prepare_insert_operation`
- `src/util_bbdd/bulk/_support/validation.py` — `get_insert_columns`
- `src/util_bbdd/bulk/_support/sql_helpers.py` — `generate_insert_sql`, `compile_stmt_with_binary_support`
- `src/util_bbdd/bulk/_execution/batch.py` — `BatchStatementExecutor`
- `tests/unit/test_bulk_internal_helpers.py` — patrón de tests existentes

## AI output summary

### Análisis

PostgreSQL rechaza `INSERT INTO t (id) VALUES (1)` en una columna `GENERATED ALWAYS AS IDENTITY`
salvo que el INSERT lleve `OVERRIDING SYSTEM VALUE`. SQLAlchemy no añade esta cláusula
automáticamente, por lo que era necesario implementarla de forma explícita.

### Diseño adoptado

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| `text()` con `:param` para ejecución | `stmt.prefix_with(...)` | `prefix_with` inserta después de `INSERT`, no después de la lista de columnas → SQL inválido |
| Regex `re.sub` para inyección en SQL generado | Recompilación de la cláusula | La regex se aplica sobre el string compilado y es segura para `count=1` en un INSERT simple |
| Solo actúa en PostgreSQL | Todos los motores | La semántica GENERATED ALWAYS es exclusiva de PostgreSQL en este contexto |
| `ValueError` temprano si `override_identity=False` y se detectan columnas ALWAYS | Dejar fallar en BD | Fail-fast con mensaje claro es más útil que un error opaco de PostgreSQL |

### IMPLEMENT

**`_support/validation.py`**
- Nueva función `detect_always_identity_columns(columns, table)`:
  itera `table.columns`, filtra por `getattr(col.identity, "always", False)` y presencia en `columns`.

**`_support/sql_helpers.py`**
- Nuevo import: `text` de SQLAlchemy.
- `generate_insert_sql_override_identity(stmt, records, dialect)`:
  compila cada registro con `compile_stmt_with_binary_support` y aplica
  `re.sub(r"\)\s+VALUES\b", ") OVERRIDING SYSTEM VALUE VALUES", sql, count=1)`.
- `build_override_identity_text_stmt(table, columns, dialect)`:
  construye `text("INSERT INTO t (a, b) OVERRIDING SYSTEM VALUE VALUES (:a, :b)")` usando
  `dialect.identifier_preparer` para quoted identifiers.

**`crud.py`**
- `bulk_insert_from_df`: nuevo parámetro `override_identity: bool = False`.
- `__run_bulk_pipeline`: recibe `override_identity`; para `strategy_key="insert"` llama
  directamente a `__prepare_insert_operation(df, tabla, override_identity=override_identity)`.
- `__prepare_insert_operation`:
  - `is_postgres = engine.dialect.name == "postgresql"`
  - Llama a `detect_always_identity_columns` solo cuando `is_postgres`.
  - Si hay columnas `ALWAYS` y `not override_identity` → `ValueError` con mensaje claro.
  - Si `override_identity and always_identity_cols` → usa `text_stmt` + `generate_insert_sql_override_identity`.
  - Default: flujo original sin cambios.

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| Validación | `src/util_bbdd/bulk/_support/validation.py` | modificado (+12 líneas) |
| SQL helpers | `src/util_bbdd/bulk/_support/sql_helpers.py` | modificado (+27 líneas) |
| CRUD bulk | `src/util_bbdd/bulk/crud.py` | modificado (+45 líneas) |
| Tests override identity | `tests/unit/test_bulk_override_identity.py` | creado (12 tests) |

## Tests añadidos

| Test | Qué verifica |
|---|---|
| `test_detect_always_identity_columns_detects_always_true` | Identity(always=True) → detectada |
| `test_detect_always_identity_columns_ignores_by_default` | Identity(always=False) → no detectada |
| `test_detect_always_identity_columns_ignores_non_identity` | Columna regular → no detectada |
| `test_detect_always_identity_columns_ignores_columns_absent_from_df` | Columna ALWAYS ausente del DF → no detectada |
| `test_generate_insert_sql_override_identity_injects_clause` | SQL contiene `OVERRIDING SYSTEM VALUE` antes de `VALUES` |
| `test_generate_insert_sql_regular_has_no_override_clause` | SQL normal NO contiene `OVERRIDING SYSTEM VALUE` |
| `test_generate_insert_sql_override_identity_generates_one_line_per_record` | Una línea SQL por registro |
| `test_build_override_identity_text_stmt_contains_clause` | `text()` contiene cláusula y parámetros nombrados |
| `test_bulk_insert_raises_when_always_identity_and_no_override` | `ValueError` en PostgreSQL con ALWAYS sin flag |
| `test_bulk_insert_no_raise_when_always_identity_and_override_true` | Sin error con `override_identity=True` |
| `test_bulk_insert_no_raise_on_other_dialect_with_always_identity` | Otros motores no afectados |
| `test_bulk_insert_no_raise_when_by_default_identity_and_no_override` | `GENERATED BY DEFAULT` no bloqueado |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests totales | 2985 | 2997 |
| Tests nuevos sesión | — | +12 |
| Regresiones | — | 0 |
| ruff | ✅ | ✅ |
| mypy | ✅ | ✅ |

## Veredicto final

**CLOSED** — feature `override_identity` implementada con fail-fast defensivo, generación SQL
correcta con `OVERRIDING SYSTEM VALUE`, ejecución vía `text()` con parámetros nombrados.
Comportamiento por defecto y otros motores no afectados. 12 tests nuevos, 0 regresiones.
