# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-p20-generar-sql-json
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase: RCA + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Sigo con el `/hotfix` de P-20?")

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` (P-20)
- `src/util_bbdd/bulk/_support/sql_helpers.py` (`generate_insert_sql`, `generate_insert_sql_override_identity`, `generate_update_sql`, `compile_stmt_with_binary_support`)

## AI output summary
- **Alcance verificado**: `CompileError` al generar INSERT y UPDATE en SQLite, PostgreSQL `JSON` y `JSONB`, y MySQL. MariaDB funciona (`JSON` = `LONGTEXT`).
- **RCA**: la generación compila con `literal_binds=True`, que necesita el `literal_processor` del tipo, y `JSON` no tiene. `compile_stmt_with_binary_support` solo recupera el caso de binarios.
- **Fix**: `_json_as_string_literals(table, values)` enlaza los valores no nulos de columnas JSON como `literal(valor, String())`. El valor ya viene serializado por `normalize_sql_literal`, así que no se vuelve a serializar (coherente con P-19); `None` → `NULL`. Aplicado en `generate_insert_sql`, `generate_insert_sql_override_identity` y `generate_update_sql`.
- **Tests**:
  - `tests/unit/bulk/test_generate_sql_json.py` (2, SQLite): generan el SQL, lo ejecutan y comparan los documentos (comillas, barra invertida, Unicode, anidación, `None` → NULL SQL). Fallaban con `CompileError` antes del fix.
  - `tests/integration/test_bulk_engines.py::test_generated_sql_with_json_column`: sin el fix (anulado en memoria) falla en SQLite, PostgreSQL y MySQL; con el fix pasa en los 4 motores con JSON.
- **Verificación con servidores reales**: el SQL generado de INSERT y UPDATE, ejecutado sentencia a sentencia, guarda documentos idénticos en PostgreSQL `JSONB`/`JSON`, MySQL y MariaDB.
- **Nuevo hallazgo P-23 (ALTA, previo)**: el INSERT generado parecía fallar en los 4 servidores. La diferencia era un `%` duplicado (`"%s ?"` → `"%%s ?"`). Aislado con una columna VARCHAR: en PostgreSQL, MySQL y MariaDB el SQL generado duplica **todos** los `%` de los literales de texto (`'a%b'` → `'a%%b'` al ejecutar el fichero); SQLite no. Es ajeno a JSON y queda registrado para un hotfix propio.
- **Validación**:
  - `ruff check src tests` y `mypy src` limpios.
  - Suite: 4536 passed / 63 skipped.
  - Integración 6 motores: 46 passed / 20 skipped.

## AUDIT_CODE
- Regresiones potenciales: solo cambian las columnas de tipo JSON reflejado en la generación de SQL, que antes fallaban siempre. Las demás columnas no cambian.
- Edge cases:
  - `None` → `NULL`.
  - Documentos con comillas simples y dobles, barras invertidas y Unicode: correctos en los 4 motores.
  - `%` en el documento: afectado por P-23 (no por este fix).
- Comportamiento previo observado, ajeno: en SQLite el nombre del fichero generado incluye la ruta absoluta de la BD, que prevalece sobre `path_sql`, así que el fichero queda junto a la BD.
- Compatibilidad: sin cambio de API.

## Directrices para Futuras IAs
- **[bulk/generar_sql]**: para validar la generación de SQL hay que **ejecutar** el fichero contra el motor y comparar lo guardado; compilar sin error no basta (así apareció P-23).
- **[bulk/generar_sql]**: en SQLite el fichero puede no quedar en `path_sql`, porque el nombre incluye la ruta absoluta de la BD.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- P-23.
