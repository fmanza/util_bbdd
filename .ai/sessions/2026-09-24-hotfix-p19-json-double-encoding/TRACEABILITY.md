# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-p19-json-double-encoding
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase: RCA + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Hago el commit y paso al `/hotfix` de P-19?". Antes se hicieron los commits `9bc03de` y `a649f50` del refactor P-02.)

## Context supplied
- Ver `00_CONTEXT_SNAPSHOT.md`.

## AI output summary
- **Supuesto de alcance verificado** en servidores reales (INSERT y UPDATE de `{"k": …}` y `None`):

| Motor | Tipo reflejado | INSERT | UPDATE |
|---|---|---|---|
| SQLite | `JSON` | corrompía | corrompía |
| MySQL 8.4 | `JSON` | correcto | corrompía |
| PostgreSQL 17 | `JSON`/`JSONB` | correcto (COPY) | corrompía |
| Oracle 23 | `NullType` | correcto | correcto |
| MariaDB 11.4 | `LONGTEXT` | correcto | correcto |

- **RCA**:
  - `normalize_sql_literal` convierte dict/list a texto JSON.
  - Las sentencias construidas desde la tabla reflejada (`update(tabla).values({col: bindparam(col)})` e `insert(tabla)` en `DefaultInsertStrategy`) aplicaban el procesador del tipo `JSON`. Serializaba el texto por segunda vez y, con `none_as_null=False`, convertía `None` en el literal JSON `null`.
  - Las vías sin tipo (COPY, `exec_driver_sql`, `text()`) no se veían afectadas.
- **Prototipo validado antes de implementar**: `TypeDecorator` sin `bind_processor` y con `load_dialect_impl` = tipo de la columna. Conserva `::JSONB` en PostgreSQL. INSERT y UPDATE correctos en PostgreSQL JSONB/JSON, MySQL y SQLite. Con `executemany`, las columnas no incluidas en `.values()` siguen viajando.
- **AUDIT_PLAN**: GO. Las tablas sin columnas JSON no cambian (sin `.values()` extra). La generación de SQL (`generar_sql=True`) queda fuera: sigue usando el tipo de la columna.
- **IMPLEMENT**:
  - `src/util_bbdd/bulk/_support/sql_helpers.py`: `PreSerializedJSON` (TypeDecorator) y `json_passthrough_binds(table, columns)`.
  - `src/util_bbdd/bulk/crud.py`: `__insert_stmt` (usado por `bulk_insert_from_df` y `bulk_insert_from_chunks`) y el UPDATE enlazan las columnas JSON con `json_passthrough_binds`.
  - `tests/unit/bulk/test_json_columns.py` (nuevo, 5 tests, SQLite + compilación PostgreSQL). Los 5 fallaban antes del fix (doble serialización; helper inexistente) y pasan después.
  - `tests/integration/test_bulk_engines.py`: `test_json_column_roundtrip` (INSERT + UPDATE con dict, lista, `None` y Unicode). Sin el fix (vía `git stash`) falla en SQLite, PostgreSQL y MySQL; con el fix pasa en los 4 motores con JSON.
  - `CHANGELOG.md` (Fixed).
- **Validación**:
  - `ruff check src tests` limpio; `mypy src tests/unit/test_protocol_conformance.py tests/unit/bulk/test_json_columns.py` limpio.
  - Tests unitarios: 4058 passed. Suite completa: 4481 passed / 24 skipped.
  - Integración, 6 motores: 22 passed, 2 skipped (SQL Server y Oracle en el test JSON, por diseño).
- **Nuevo hallazgo P-20 (MEDIA, previo)**: `generar_sql=True` falla con `CompileError` ("No literal value renderer ... with datatype JSON") en tablas con columnas JSON, tanto en INSERT como en UPDATE. Verificado sobre el código sin el fix: no lo introduce este hotfix. Falla con error visible, sin corromper datos.

## AUDIT_CODE
- Regresiones potenciales:
  - Tablas sin columnas JSON: sin cambios (mismo `insert(tabla)`, mismos `bindparam`).
  - Tablas con JSON: el valor llega al driver tal cual lo produce `normalize_sql_literal`, igual que en las vías COPY/MySQL, que ya funcionaban.
- Edge cases:
  - Un valor JSON que no sea dict/list (p.ej. un número o un texto ya JSON) se envía sin procesar, como en las vías sin tipo.
  - `None` → NULL SQL.
  - Unicode (`ensure_ascii=False`) conservado.
- Compatibilidad: sin cambio de API pública. Los datos ya guardados con el fallo no se corrigen solos.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix | `src/util_bbdd/bulk/_support/sql_helpers.py`, `src/util_bbdd/bulk/crud.py` | completado |
| Test unitario | `tests/unit/bulk/test_json_columns.py` | nuevo |
| Regresión integración | `tests/integration/test_bulk_engines.py::test_json_column_roundtrip` | nuevo |
| Changelog | `CHANGELOG.md` | actualizado |
| Hallazgo P-20 | `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` | registrado |

## Directrices para Futuras IAs
- **[bulk/JSON]**: si añades una ruta que ejecute con la tabla reflejada, enlaza las columnas JSON con `json_passthrough_binds` (`_support/sql_helpers.py`). Si no, el valor ya serializado por `normalize_sql_literal` se vuelve a serializar.
- **[bulk/JSON]**: `generar_sql=True` con columnas JSON sigue fallando (P-20). Su corrección debe renderizar el texto ya serializado como literal de cadena.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (no realizado; pendiente de petición del usuario).
- P-20.
