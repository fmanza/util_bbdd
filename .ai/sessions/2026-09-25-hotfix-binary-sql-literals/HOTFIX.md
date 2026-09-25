# HOTFIX — Literales binarios en el SQL generado (C-1 + P-30)

<!-- arquetipo: informativo-libre -->

- **Fecha**: 2026-09-25 · **Rama**: develop · **Origen**: [auditoría de serialización SQL](../../audit/audit_report_bulk_sql_serialization_20260925.md) (C-1, P-30)
- **Severidad**: P1. Corrupción silenciosa en Oracle; ficheros que no cargan en SQLite, PostgreSQL y SQL Server.

## PLAN

- **Objetivo**: que el SQL de `generar_sql=True` guarde los bytes exactos de las columnas binarias en todos los dialectos.
- **Ruta**: `src/util_bbdd/bulk/_support/sql_helpers.py`, en los dos caminos de generación: la plantilla
  (`_LiteralTemplate`) y el camino por fila (`per_row` de INSERT, UPDATE y DELETE).
- **Supuestos verificados**: los contenedores del banco (`docker-compose.bench.yml`) sirven como referencia de cada
  motor. El SQL se ejecutó dentro de cada contenedor con su cliente nativo y sus variables de entorno, sin usar la
  contraseña fuera de él.
- **Dato faltante**: `UTIL_BBDD_TEST_<MOTOR>_URL` no está definida en esta sesión. El test de integración nuevo solo
  se ejecutó en SQLite; en los servidores, la verificación es la del arnés `docker exec`.

## Causa raíz (reproducida en servidores reales)

Nueve valores (`b"abc"`, `b"a'b"`, `b"a\\b"`, `b"\\x41"`, `b"%(x)s %s ?"`, `"ñ€".encode()`, `b"\x00\xff"`,
`bytes(range(256))`, `None`) insertados con el SQL generado y leídos de vuelta en hexadecimal:

| Motor | Antes | Después | Síntoma antes |
|---|---:|---:|---|
| SQLite 3 | 1/9 | 9/9 | UTF-8 → TEXT; `0x00FF` → entero 255; hex largo → error |
| PostgreSQL 17 | 7/9 | 9/9 | `0x…` → «bytea but expression is of type integer» |
| MySQL 8.4 | 9/9 | 9/9 | — |
| MariaDB 11.4 | 9/9 | 9/9 | — |
| SQL Server 2022 | 3/9 | 9/9 | `'abc'` → Msg 257 (sin conversión implícita varchar → varbinary) |
| Oracle 23ai | 1/9 | 9/9 | `'abc'` → **`0x0ABC` sin error**; resto ORA-01465 |

1. **Camino de plantilla**: el `literal_processor` de `LargeBinary` en SQLAlchemy 2.0.50 renderiza los bytes como
   cadena (`'abc'`), no como literal binario. Con bytes no UTF-8 lanza una excepción y la fila cae al camino por fila.
2. **Camino por fila**: `compile_stmt_with_binary_support` termina en `format_sql_param_value`, que escribe `0xHEX`
   en todos los dialectos.

## AUDIT_PLAN

| Riesgo | Tipo | Evaluación |
|---|---|---|
| Cambia el SQL generado en MySQL/MariaDB y PostgreSQL, que ya guardaban bien los UTF-8 | Funcional | Aceptado: forma distinta, mismos datos (9/9 antes y después) |
| Valores no `bytes` en columnas binarias (p.ej. `str` sin restaurar) | Funcional | Siguen el camino anterior de su tipo |
| Dialectos fuera de la tabla | Funcional | Sin cambios |
| Oracle: literal > 2000 bytes (ORA-01704) | Técnico | Preexistente (antes `0x…` fallaba siempre); documentado, no se aborda |
| Inyección SQL | Seguridad | El literal solo contiene dígitos hexadecimales en mayúscula; ya no se entrecomilla contenido binario |
| Cambio de API | Compatibilidad | Ninguno: helpers internos (`_BINARY_LITERAL_FORMATS`, `_binary_or_value`, `_binary_processor`) |

## IMPLEMENT

- `_BINARY_LITERAL_FORMATS`: formato por `dialect.name`.
- `_binary_or_value(column_type, value, dialect)`: en el camino por fila, `bytes` de una columna `_Binary` →
  `literal_column(<literal>)`. Se aplica en SET/VALUES y en el WHERE de UPDATE y DELETE.
- `_LiteralTemplate._binary_processor`: en la plantilla, los huecos de columnas `_Binary` (VALUES/SET y WHERE)
  escriben los `bytes` en hexadecimal; cualquier otro valor se renderiza como antes.
- Tests:
  - `test_binary_values_use_the_dialect_hex_literal` (8 drivers): literal esperado y ninguna compilación por fila.
    Falla 8/8 con el código anterior.
  - `test_binary_primary_key_in_where_uses_hex_literal`: WHERE por plantilla y por el camino por fila.
  - `test_generated_sql_binary_column_roundtrip` (integración): ejecuta el SQL generado y compara los bytes. Falla
    con el código anterior en SQLite.
  - Las referencias `_ref_*` de `test_generate_sql_template.py` aplican la misma conversión que el camino por fila
    (la equivalencia plantilla == camino por fila se mantiene).

## AUDIT_CODE

- **Regresiones**: ruff, mypy y `pytest` en verde (4913 passed antes del último ajuste de tipos; tras él, 633 passed
  en `bulk`, helpers e integración). Los tests de binarios de ejecución (`generar_sql=False`, P-21) no cambian.
- **Casos límite**: `b""` (Oracle lo guarda como NULL por diseño del motor), `bytearray` y `memoryview`, PK binaria
  con `None` (camino por fila), `%` y comillas dentro de los bytes, 256 bytes con todos los valores.
- **Rendimiento (efecto del arreglo, no objetivo)**: filas con bytes no UTF-8, de 119–136 a 1,0–1,5 µs/fila.

## VERSION

```
fix(bulk): literales binarios por dialecto en el SQL generado (C-1, P-30)
```

- **Rollback**: `git revert <commit>`. No hay datos persistidos que migrar. Los ficheros `.sql` generados antes del
  arreglo con binarios deben regenerarse para SQLite, PostgreSQL, SQL Server y Oracle.
