# TRACEABILITY

## Session metadata
- id: 2026-05-26-bulk-audit-fix
- fecha: 2026-05-26
- rama: develop
- skill: audit_code → implement
- fase: PLAN → AUDIT_PLAN → AUDIT_CODE → IMPLEMENT

## Prompt issued

```
/audit-code

Revisar el módulo src\util_bbdd\bulk
```

Seguido de `IMPLEMENT` para aplicar las condiciones del veredicto.

## Context supplied
- `src/util_bbdd/bulk/crud.py`
- `src/util_bbdd/bulk/normalize.py`
- `src/util_bbdd/bulk/audit.py`
- `src/util_bbdd/bulk/_support/persistence.py`
- `src/util_bbdd/bulk/_support/sql_helpers.py`
- `src/util_bbdd/bulk/_support/validation.py`
- `src/util_bbdd/bulk/_execution/batch.py`
- `src/util_bbdd/bulk/_audit/repository.py`
- `src/util_bbdd/bulk/_audit/service.py`
- `src/util_bbdd/bulk/_audit/exporters.py`
- Suite de tests del módulo (5 ficheros, 56 tests)

## AI output summary

### Veredicto auditoría: APROBADO CON CONDICIONES

56 tests pasaban antes de la auditoría. mypy limpio. Los hallazgos principales:

| Hallazgo | Severidad | Ubicación |
|---|---|---|
| Bloque `finally` + `__actualizar_df` modifican DataFrame del llamador (viola contrato) | Alta | `crud.py:355, 515` |
| Tiempo medido en auditoría incluye I/O de fichero cuando `generar_sql=True`, no ejecución BD | Media | `crud.py:331-339` |
| Falta guard para INSERT sin columnas coincidentes (error SQLAlchemy críptico) | Media | `validation.py:57-68` |
| `tiempo_seg` no tolera filas malformadas en lectura CSV | Media | `repository.py:119` |
| Anotaciones de tipo incompletas: `stmt` sin anotar, `-> list:` sin especializar | Baja | `crud.py:457, 591` |
| Validación letra muerta en `SqlBasedDeleteStrategy` (condición siempre `False`) | Baja | `batch.py:43` |

### Análisis del bug principal

El flujo en `__run_bulk_pipeline` modificaba el DataFrame original en dos puntos:

1. `__actualizar_df(df)` → `normalize_dataframe_columns` cambia `df.columns` in-place +
   `df.replace({np.nan: None}, inplace=True)` muta los valores.
2. Bloque `finally: df.columns = df.columns.str.upper()` → convertía siempre a
   mayúsculas al salir, sin respetar el dialecto ni el estado original.

El docstring de `bulk_insert_from_df` decía explícitamente "El DataFrame original no se
modifica", pero el código lo violaba en todos los casos. El test existente
`test_bulk_insert_exclude_does_not_modify_original_df` pasaba accidentalmente porque
usaba `mock_sqlserver_engine` (MSSQL → uppercase), y el DataFrame de entrada ya tenía
columnas en uppercase, por lo que el `finally` no producía cambio observable.

Adicionalmente, el test `test_execute_path_unchanged_does_not_call_wrap` tenía un bug
latente: usaba `identity_table` (lowercase columns) con MSSQL dialect (uppercase), lo
que generaba `insert_cols=[]` silenciosamente. El nuevo guard lo expuso y el test fue
corregido.

### IMPLEMENT

**`crud.py`**
- `__run_bulk_pipeline`: `working_df = df.copy()` al inicio; operaciones internas usan
  `working_df`. Eliminado bloque `finally`.
- Timing: `elapsed = 0.0` cuando `generar_sql=True` (sin ejecución en BD); `perf_counter`
  solo en rama `execute()`. Auditoría registra 0.0 s para operaciones de solo generación.
- `__ejecutar_batch_stmt`: parámetro `stmt: Any` (antes sin anotar).
- `__generar_sql_insert`: return type `-> list[str]` (antes `-> list`).

**`_support/validation.py`**
- `get_insert_columns`: guard al final — si `columns` queda vacío (por no-coincidencia
  o exclusión total), lanza `ValueError` descriptivo en lugar de propagar vacío a
  SQLAlchemy.

**`_audit/repository.py`**
- `leer_auditoria`: `pd.to_numeric(..., errors="coerce")` para `tiempo_seg` con
  `regex=False` en `str.replace`. Tolera filas con valor vacío o malformado sin lanzar
  excepción.

**`_execution/batch.py`**
- `SqlBasedDeleteStrategy.execute`: eliminada validación letra muerta
  (`all(isinstance(v, tuple) for v in values)` nunca podía ser `False` ya que `values`
  se construía como `[tuple(...) for ...]`).

**`tests/unit/test_bulk_sqlserver_identity.py`**
- `test_execute_path_unchanged_does_not_call_wrap`: corregido para usar tabla
  `mssql_table` con columnas uppercase (`ID`, `NAME`) y DataFrame con columnas uppercase,
  acordes al dialecto MSSQL. El test anterior pasaba accidentalmente con `insert_cols=[]`.

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| CRUD bulk | `src/util_bbdd/bulk/crud.py` | modificado (df.copy, finally, timing, tipos) |
| Validación bulk | `src/util_bbdd/bulk/_support/validation.py` | modificado (+6 líneas guard) |
| Repository auditoría | `src/util_bbdd/bulk/_audit/repository.py` | modificado (pd.to_numeric) |
| Executor batch | `src/util_bbdd/bulk/_execution/batch.py` | modificado (dead code eliminado) |
| Test MSSQL identity | `tests/unit/test_bulk_sqlserver_identity.py` | corregido (bug latente expuesto) |

## Decisiones de diseño

| Decisión | Alternativa | Razón |
|---|---|---|
| `elapsed=0.0` cuando `generar_sql=True` | Medir tiempo de generación SQL | La auditoría debe reflejar latencia de BD; el campo `sql` ya indica si fue generación |
| `df.copy()` en `__run_bulk_pipeline` | Copiar en cada sub-método | Punto único de copia; sub-métodos no necesitan saber si son originales o copias |
| Guard en `get_insert_columns` al final (post-exclusión) | Guard antes de exclusión | Cubre tanto el caso "no coincide nada" como "todo es autoincrement" en una sola comprobación |
| `pd.to_numeric(errors="coerce")` | `try/except` alrededor del cast | Idiomático pandas; mantiene NaN para filas malformadas en lugar de abortar la lectura |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests totales (módulo bulk) | 56 | 56 |
| Tests nuevos sesión | — | 0 (corrección de test existente) |
| Regresiones | — | 0 |
| ruff | ✅ | ✅ |
| mypy | ✅ (15 ficheros) | ✅ (15 ficheros) |

## Directrices para Futuras IAs

1. **Contrato inmutabilidad DataFrame**: `__run_bulk_pipeline` usa `working_df = df.copy()`
   desde la primera línea. Ningún sub-método ni bloque `finally` debe modificar `df`
   directamente. Cualquier operación in-place debe aplicarse sobre `working_df`.

2. **Timing en auditoría**: `elapsed` se mide únicamente en la rama `execute()` con
   `perf_counter`. Cuando `generar_sql=True` la BD no se toca; `elapsed=0.0` es el valor
   correcto. No restaurar el timing envolvente al bloque completo.

3. **Guard de columnas vacías**: `get_insert_columns` lanza `ValueError` si la lista de
   columnas válidas está vacía al final (post-exclusión). No devolver lista vacía: SQLAlchemy
   emitiría un error críptico que no identifica la causa raíz.

4. **Casing MSSQL en tests**: los tests que usan `mock_sqlserver_engine` deben construir
   tablas reflejadas y DataFrames con columnas en UPPERCASE. El dialecto MSSQL normaliza
   a uppercase vía `normalize_dataframe_columns`. Usar columnas lowercase con dialecto MSSQL
   produce `insert_cols=[]` y el test pasa por razones equivocadas.

## Veredicto final

**CLOSED** — 5 archivos modificados, 0 tests rotos, 56/56 pasan, mypy limpio.
Contrato de inmutabilidad del DataFrame restaurado. Métricas de auditoría consistentes.
Guard descriptivo para INSERT sin columnas coincidentes. Validación letra muerta eliminada.
