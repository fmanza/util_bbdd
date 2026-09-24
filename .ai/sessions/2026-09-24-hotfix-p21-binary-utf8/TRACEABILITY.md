# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-p21-binary-utf8
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase: RCA + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
Si prefieres que en ese caso vuelva solo al UPDATE fila a fila en lugar de fallar, se puede añadir. Hazlo he informa en el LOG, luego /hotfix de P-21
```
(La primera parte, el fallback de `update_via_staging` por privilegio, se registró en `2026-09-24-new-feature-p04-mysql-staging-update/TRACEABILITY.md`.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` (P-21)
- `src/util_bbdd/bulk/normalize.py` (`_decode_bytes_to_string`), `src/util_bbdd/bulk/crud.py`, `src/util_bbdd/bulk/_support/sql_helpers.py`

## AI output summary
- **Supuesto de alcance verificado**, más amplio que el registrado. Columna binaria con `b"q"`, `b"\xff\x00"`, `b""`, `None`, `b"a\x08"`:

| Motor | INSERT | UPDATE |
|---|---|---|
| SQLite | TypeError | — |
| PostgreSQL | correcto (COPY) | TypeError |
| MySQL/MariaDB (por defecto, con staging) | correcto | correcto |
| MySQL/MariaDB sin staging | correcto | TypeError |
| SQL Server (pymssql y pyodbc) | TypeError | — |
| Oracle | `b"a\x08"` guardado como NULL (pérdida silenciosa) | correcto |

- **RCA**: `normalize_sql_literal` decodifica a `str` todo `bytes` UTF-8 válido, sin conocer el tipo de la columna destino. Los parámetros tipados binarios (`LargeBinary`, `BYTEA`, `VARBINARY`, `BLOB`) rechazan `str`, y Oracle lo enlaza de forma distinta.
- **Fix**:
  - `restore_binary_values(records, table)` en `_support/sql_helpers.py`: en las columnas de tipo `sqltypes._Binary`, recodifica en UTF-8 los `str`. Es una ida y vuelta exacta, porque ese `str` procede de decodificar UTF-8.
  - Se llama tras cada `normalize_records_for_sql` de `crud.py`: `bulk_insert_from_df`, `bulk_insert_from_chunks` y `bulk_update_from_df`.
  - Las columnas de texto siguen recibiendo `str`.
- **Tests**:
  - `tests/unit/bulk/test_binary_columns.py` (4, SQLite): fallaban los 4 antes del fix.
  - `tests/integration/test_bulk_engines.py::test_binary_column_roundtrip`, con y sin staging en MySQL/MariaDB. Con el fix anulado en memoria falla en SQLite, PostgreSQL, MySQL y MariaDB sin staging y SQL Server.
- **Validación**:
  - Sonda original repetida con el fix: INSERT y UPDATE correctos en los 6 motores y los dos drivers de SQL Server (Oracle: `b""` → NULL por diseño).
  - `ruff check`, `mypy src` limpios. Suite: 4500 passed / 58 skipped.
  - Integración: 42 passed / 18 skipped (6 motores); SQL Server con pyodbc 10 passed; `mariadbconnector` 10 passed.

## AUDIT_CODE
- Regresiones potenciales:
  - En columnas binarias, un `str` que el usuario pasara a propósito se envía ahora como bytes UTF-8. Antes fallaba en los parámetros tipados; en las vías sin tipo el resultado es el mismo salvo en el COPY de PostgreSQL, donde un `str` se interpretaba como texto de entrada `bytea`.
- Edge cases:
  - `None` se mantiene.
  - Bytes no UTF-8 no se tocan: `normalize` ya los dejaba como `bytes`.
  - Registros vacíos: no hace nada.
- Compatibilidad: sin cambio de API pública.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix | `src/util_bbdd/bulk/_support/sql_helpers.py`, `src/util_bbdd/bulk/crud.py` | completado |
| Tests | `tests/unit/bulk/test_binary_columns.py`, `tests/integration/test_bulk_engines.py::test_binary_column_roundtrip` | nuevos |
| Changelog | `CHANGELOG.md` | actualizado |

## Directrices para Futuras IAs
- **[bulk/normalización]**: `normalize_sql_literal` no conoce el tipo de la columna destino. Todo lo que dependa del tipo (JSON: P-19; binarios: P-21) se corrige en `crud.py` con la tabla reflejada, después de normalizar.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
