# AUDIT_PLAN — Serialización SQL de bulk (P0 + P1)

<!-- arquetipo: informativo-libre -->

**Veredicto: APROBADO CON CONDICIONES** (C1–C4 al final).

## 1. Supuestos verificados

| # | Supuesto del PLAN | Verificación | Resultado |
|---|---|---|---|
| S1 | Compiladores que no redefinen `render_literal_value` | MRO de `statement_compiler` en los 8 drivers de `test_generate_sql_template.py` | ✅ `SQLCompiler` en sqlite, mssql+pyodbc, mssql+pymssql, oracle+oracledb. Redefinido en `PGCompiler` (psycopg y psycopg2) y `MySQLCompiler` (pymysql, mariadbconnector) |
| S2 | `type_.dialect_impl(d).literal_processor(d)` (público) equivale a `_cached_literal_processor(d)` (privado) | Comparación del código de la función en 11 tipos (String, Integer, DateTime, Numeric, Boolean, Date, Time, Text, Unicode, Float, BigInteger) × 8 drivers | ✅ Misma función en todos |
| S3 | P-31 + P-32 dan salida byte-idéntica | Prototipo de la auditoría: dataset de bench 100K + casos límite + PK `NULL` en WHERE, 5 dialectos | ✅ (ver informe, fase 5) |
| S4 | `_LiteralTemplate.render` / `_literal` no tienen usos fuera de `sql_helpers.py` | `grep` en `src/`, `tests/` y `scripts/` | ✅ Solo internos: se pueden retirar |
| S5 | La vía rápida de P-33 cubre la dtype `str` de pandas 3 | `isinstance(dtype, pd.StringDtype)` | ✅ `str` (na_value=nan) y `string[python]` (na_value=`<NA>`); `category` no es `StringDtype` y queda fuera, como indica el plan |
| S6 | `np.str_` fuera de la vía rápida conserva el resultado | `np.str_(" a ").strip()` → `str` en ambos caminos | ✅ |
| S7 | Hay tests de equivalencia que cubren P1 | `test_generate_sql_template.py` (8 drivers) y `test_dataframe_to_sql_records.py` (24 dtypes, igualdad de tipo) | ✅ |
| S8 | `dataframe_to_sql_records` tiene más consumidores | `crud.py:499` (`bulk_insert_from_chunks`) y `crud.py:681` (`__record_blocks`) | ✅ P-33 beneficia también a `generar_sql=False` y a `bulk_insert_from_chunks` (y a dump, que usa `BulkCrud`) |

## 2. Viabilidad y riesgo por paso

| Paso | Impacto medido | Esfuerzo | Riesgo | Mitigación |
|---|---:|---:|---|---|
| 0 — benchmark | — | 1,5 h | Nulo (solo `scripts/`) | — |
| 1 — P-33 | −75 % por celda de texto (≈ −10 % INSERT) | 1,5 h | Bajo: igualdad de tipo exigida por el test existente | 5 casos nuevos en `DTYPE_MATRIX` |
| 2 — P-31 | −15–21 % render | 3 h | Bajo–medio: toca el camino caliente | Tests de equivalencia existentes + comprobación de "sin compilación por fila" |
| 3 — P-32 | −18 pp adicionales en sqlite/oracle/mssql | 1 h | Bajo: activación por identidad de método; PG/MySQL no cambian | Test de activación por dialecto |

**Orden**: 0 → 1 → 2 → 3. El 1 es independiente del resto. El 3 depende del 2 (usa `render_block`). Cada paso se valida
y se mide por separado, para poder atribuir la mejora y revertir paso a paso.

## 3. Compatibilidad

- **API pública**: sin cambios (`generate_*_sql`, `dataframe_to_sql_records` y `normalize_sql_literal` mantienen
  firma y resultado). `_LiteralTemplate` es privada.
- **Salida SQL**: byte-idéntica (condición C1).
- **Dependencias**: ninguna nueva. La comprobación de S1 importa `SQLCompiler` de `sqlalchemy.sql.compiler`, un módulo
  público en 2.0.
- **Multi-BBDD**: PostgreSQL y MySQL/MariaDB siguen por `render_literal_value` del dialecto (escape de `\` según
  `_backslash_escapes` / `sql_mode`).
- **Diagrama de capas**: sin imports nuevos entre paquetes; no se regenera.

## 4. Riesgos y observaciones

| # | Riesgo | Severidad | Tratamiento |
|---|---|---|---|
| R1 | Una versión futura de SQLAlchemy añade lógica a `SQLCompiler.render_literal_value` (hoy: `None` → `NULL` y envoltorio de `CompileError`) que el atajo de P-32 se saltaría | Baja | Los tests de equivalencia contra la compilación por fila lo detectarían. Añadir comentario con la versión verificada (2.0.50) |
| R2 | Orden de los errores: con render por columnas, un error de la fila *i* en la columna *k* se detecta antes que el de una fila anterior en la columna *k+1* | Nula | Las filas marcadas se resuelven con `per_row` **en orden de fila** al ensamblar: el primer error que se lanza es el de la primera fila no renderizable, igual que hoy |
| R3 | `pyarrow` no está instalado en el venv | Info | El caso `string_pyarrow` se salta con `importorskip`; CI lo cubre si lo tiene |
| R4 | Memoria: columnas de literales por bloque (5.000 × n cadenas) | Nula | Mismo orden de magnitud que las líneas ya generadas por bloque |
| R5 | La proyección de −40 % es aritmética sobre mediciones por etapa | Info | El paso 4 la mide de extremo a extremo con 1M filas; el objetivo se acepta con la medición real |

## 5. Pruebas requeridas

| Área | Test | Estado |
|---|---|---|
| P-33 | `test_dataframe_to_sql_records.py`: `object_str_only`, `object_str_pd_na`, `string_pyarrow`, `object_np_str`, `object_str_and_int` | Nuevos |
| P-31 | `test_generate_sql_template.py`: todos los existentes sin cambios | Existentes |
| P-31 | Bloque con filas buenas y malas intercaladas (clave ausente, PK `None`) → orden y contenido iguales a `_ref_*` | Nuevo |
| P-32 | `test_direct_processor_only_for_base_compiler` | Nuevo |
| Integración | `tests/unit/bulk/test_block_pipeline.py`, `test_binary_columns.py`, `test_generate_sql_json.py`, `test_generate_sql_percent.py` | Existentes |
| Rendimiento | `scripts/bench_sqlgen.py` antes/después de cada paso; `--e2e` con 1M filas | Nuevo script |

## 6. Condiciones de aprobación

- **C1**: la suite completa y los tests de equivalencia en verde **sin modificar ninguna expectativa existente**. Si hay
  que cambiar un `_ref_*` o un valor esperado, se para: eso es un cambio de salida y queda fuera de P1.
- **C2**: baseline medido con `scripts/bench_sqlgen.py` **antes** del paso 1 y guardado en `baseline/`.
- **C3**: cada paso se mide por separado; un paso con mejora < 5 % en su métrica se revierte o se justifica.
- **C4**: P-30 y C-1 no entran en este cambio (salida distinta; flujo `/hotfix`).
