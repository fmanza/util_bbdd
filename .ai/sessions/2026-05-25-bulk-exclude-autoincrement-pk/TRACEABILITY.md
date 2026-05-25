# TRACEABILITY

## Session metadata
- id: 2026-05-25-bulk-exclude-autoincrement-pk
- fecha: 2026-05-25
- rama: develop
- skill: new_feature
- fase: IMPLEMENT → AUDIT_CODE → VERSION

## Prompt issued

```
Revisar e implementar en src/util_bbdd/bulk una opción explícita para excluir la columna
primary key autoincremental/identity durante bulk_insert_from_df.

Añadir exclude_autoincrement_pk: bool = False a bulk_insert_from_df.
Extender get_insert_columns con exclude_autoincrement_pk=False.
Cuando True, excluir la columna PK autoincremental/identity del INSERT (no modificar el
DataFrame original). Aplica a generar_sql=True y generar_sql=False. No afecta a UPDATE ni DELETE.
Detección: col.autoincrement is True o getattr(col, "identity", None) is not None.
PKs planas sin autoincrement=True ni Identity() NO deben excluirse.
En PK compuesta, solo excluir la columna específicamente autoincremental.
```

## Context supplied
- `src/util_bbdd/bulk/_support/validation.py` — `get_insert_columns`
- `src/util_bbdd/bulk/crud.py` — `bulk_insert_from_df`, `__run_bulk_pipeline`, `__prepare_insert_operation`

## AI output summary

### Análisis

`get_insert_columns` no tenía mecanismo para excluir columnas autoincrement/identity
del INSERT. Esto obligaba al llamante a manipular el DataFrame antes de invocar
`bulk_insert_from_df`, con riesgo de modificar el objeto original.

La detección correcta usa dos condiciones combinadas (OR):
- `col.autoincrement is True` — cubre columnas con `autoincrement=True` explícito
- `getattr(col, "identity", None) is not None` — cubre columnas con `Identity()`

Esto excluye deliberadamente `autoincrement='auto'` (plain integer PK sin declaración
explícita), evitando falsos positivos en columnas que el usuario sí quiere insertar.

### Diseño adoptado

| Decisión | Alternativa | Razón |
|---|---|---|
| `col.autoincrement is True or identity is not None` | `table._autoincrement_column` | `_autoincrement_column` captura `autoincrement='auto'`, lo que causaría falsos positivos en PKs planas |
| Filtro en `get_insert_columns` como kwarg | Lógica en `__prepare_insert_operation` | Centraliza en el helper de validación; `crud.py` solo pasa el flag |
| Keyword-only (`*`) en `get_insert_columns` | Posicional | Evita errores silenciosos al llamar con `True` en posición incorrecta |
| No modificar `df` original | Modificar y restaurar | El DataFrame puede estar en uso en el llamante; mutación implícita es peligrosa |

### IMPLEMENT

**`_support/validation.py`**
- `get_insert_columns(df_columns, table, *, exclude_autoincrement_pk=False) -> list[str]`:
  cuando `True`, calcula `ai_pk_names` iterando `table.primary_key.columns` con la
  condición `col.autoincrement is True or getattr(col, "identity", None) is not None`
  y filtra esas columnas de la lista resultante.

**`crud.py`**
- `bulk_insert_from_df`: nuevo param `exclude_autoincrement_pk: bool = False`.
- `__run_bulk_pipeline`: propaga `exclude_autoincrement_pk` a `__prepare_insert_operation`.
- `__prepare_insert_operation`: recibe `exclude_autoincrement_pk` y lo pasa a
  `get_insert_columns`. El resto del flujo (PostgreSQL OVERRIDING, MSSQL wrapping,
  default) trabaja sobre el `insert_cols` ya filtrado sin cambios adicionales.

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| Validación bulk | `src/util_bbdd/bulk/_support/validation.py` | modificado (+12 líneas) |
| CRUD bulk | `src/util_bbdd/bulk/crud.py` | modificado (+14 líneas) |
| Tests exclude PK | `tests/unit/test_bulk_exclude_autoincrement_pk.py` | creado (9 tests) |

## Tests añadidos

| Test | Qué verifica |
|---|---|
| `test_get_insert_columns_default_includes_all` | Con False (defecto) no se excluye ninguna columna |
| `test_get_insert_columns_excludes_identity_col` | `Identity()` → columna excluida |
| `test_get_insert_columns_excludes_autoincrement_true_col` | `autoincrement=True` → columna excluida |
| `test_get_insert_columns_does_not_exclude_plain_pk` | PK plana sin Identity ni autoincrement=True → NO excluida |
| `test_composite_pk_only_autoincrement_col_excluded` | PK compuesta: solo la columna con Identity se excluye |
| `test_bulk_insert_exclude_does_not_modify_original_df` | El DataFrame original no se modifica |
| `test_bulk_insert_generate_sql_excludes_identity_col` | Los registros pasados al generador SQL no incluyen la columna identity |
| `test_bulk_insert_execute_excludes_identity_col` | En ejecución directa (generar_sql=False) los registros no incluyen la columna |
| `test_bulk_insert_false_includes_identity_col` | Con False (defecto) la columna identity se incluye normalmente |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests totales | 3019 | 3028 |
| Tests nuevos sesión | — | +9 |
| Regresiones | — | 0 |
| ruff | ✅ | ✅ |
| mypy | ✅ | ✅ |

## Veredicto final

**CLOSED** — `bulk_insert_from_df` acepta `exclude_autoincrement_pk=True` para omitir la
columna PK autoincremental/identity sin modificar el DataFrame original. Aplica a ambos
modos (ejecución y generación SQL). PKs planas sin Identity/autoincrement=True no se
ven afectadas. 9 tests nuevos, 0 regresiones.
