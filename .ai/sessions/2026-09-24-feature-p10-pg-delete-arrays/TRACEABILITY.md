# TRACEABILITY

## Session metadata
- id: 2026-09-24-feature-p10-pg-delete-arrays
- fecha: 2026-09-24
- rama: develop
- skill: new_feature (mejora de rendimiento sin cambios de API pública)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Hago el commit y sigo con P-10 …?". Antes, commits `446c2b7` y `6c03368` de P-13. Tras la verificación de mkdocs el usuario escribió "continua".)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-10: "`DELETE FROM t WHERE pk = ANY(:ids)` para PK simple")
- `src/util_bbdd/bulk/_execution/batch.py` (`GenericDeleteStrategy`, `SqlBasedDeleteStrategy`, `DeleteStrategyResolver`)

## AI output summary
- **Medición previa**: 100K filas, PK simple, mediana de 3 (`scratchpad/p10_bench.py`).

  | Opción | psycopg 3 | psycopg2 |
  |---|---|---|
  | `executemany` (antes, una sentencia por fila) | 2,78 s | 26,74 s |
  | `IN (...)` | 1,13 s | 1,35 s |
  | `= ANY(array)` | 1,04 s | 1,06 s |

- **PK compuesta** (`scratchpad/p10_composite.py`):
  - `(a, b) IN ((..), ..)` resultó **más lento** que el `executemany`: 35–47 s con psycopg 3 frente a 2,7 s;
  - se descartó y se midió `DELETE ... USING unnest(...)`: 1,19 s con psycopg 3 y 1,24 s con psycopg2.
- **Implementación**: `PostgreSQLAnyDeleteStrategy`.
  - PK simple: `delete(t).where(col == any_(bindparam("pk_ids", type_=ARRAY(col.type))))`.
  - PK compuesta: `DELETE FROM t AS _bulk_del_t USING unnest(CAST(:pk_0 AS tipo[]), ...) AS _bulk_del_k(cols) WHERE ...`. El tipo se compila de la columna reflejada y los identificadores van con `identifier_preparer`.
  - `DeleteStrategyResolver` la usa para `postgresql` y admite `postgresql_strategy=` para sustituirla. `sql_based_dialects` sigue teniendo prioridad.
  - Valores con `Series.tolist()`: tipos nativos de Python.
- **Resultado con la librería**, 100K filas, mediana de 3:

  | PK | psycopg 3 | psycopg2 |
  |---|---|---|
  | Simple | 2,79 → 0,99 s (2,8×) | 27,35 → 1,01 s (27×) |
  | Compuesta | 2,72 → 1,18 s (2,3×) | 27,90 → 1,17 s (24×) |

- **Tests**:
  - `tests/unit/bulk/test_delete_postgresql.py` (8):
    - SQL de PK simple con esquema y de compuesta con identificadores que exigen comillas y tipos INTEGER/VARCHAR/TIMESTAMP;
    - valores nativos;
    - enrutado del resolver para 5 dialectos y estrategia personalizada.
  - Integración: `test_delete_with_text_and_datetime_primary_keys` (simple/compuesta, texto con `'` y `%` y fechas; 6 motores; PostgreSQL con los dos drivers). Los tests previos de DELETE simple y compuesto ejercitan ya la nueva estrategia en PostgreSQL.
- **Docs**: `docs/guides/benchmarks.md` añade a la tabla de problemas conocidos los síntomas de P-13 y P-27 (pendiente de los hotfix anteriores).
- **Validación**:
  - `ruff check src tests` y `mypy src tests/unit/test_protocol_conformance.py` limpios;
  - suite 4609 passed / 159 skipped;
  - integración 6 motores 156 passed / 24 skipped;
  - `mkdocs build --strict`: los mismos 13 avisos previos.

## AUDIT_CODE
- Regresiones potenciales:
  - tipos de PK sin forma de array en PostgreSQL (dominios o tipos no reflejados): el CAST usa el tipo compilado de la columna; no probado con dominios;
  - los valores pasan por el procesador de `ARRAY(tipo)`, igual que antes pasaban por el del tipo de la columna.
- Edge cases:
  - tabla o columnas con nombres reservados o mayúsculas: se citan (test unitario);
  - esquema explícito: `format_table` con esquema;
  - una tabla llamada `_bulk_del_t`: el alias la oculta, pero la condición usa el alias. No hay colisión porque la tabla solo aparece en `FROM`.
- Seguridad: sin interpolación de valores; solo identificadores citados por el dialecto y tipos compilados de la tabla reflejada.
- Compatibilidad: sin cambios de firma pública; `DeleteStrategyResolver` gana un parámetro opcional.

## Directrices para Futuras IAs
- **[bulk/PostgreSQL]**: no usar `(a, b) IN ((..), ..)` con miles de filas en PostgreSQL: medido 17× más lento que el `executemany`. Para varias columnas, arrays con `unnest`.
- **[medición]**: medir cada alternativa antes de elegirla, incluso cuando otro motor ya la use con éxito (el `IN` de filas va bien en MySQL y fatal en PostgreSQL).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- Siguientes del bloque: P-06 + observación de SQLAlchemy, P-07 (bloques), P-08.
