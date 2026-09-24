# TRACEABILITY

## Session metadata
- id: 2026-09-24-hotfix-p22-mysql-template-cache
- fecha: 2026-09-24
- rama: develop
- skill: hotfix (abierto durante la verificación de P-04, `/new-feature`)
- fase: RCA + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Sigo con P-04?". El fallo apareció al verificar P-04 contra MariaDB + `mariadbconnector`; el trabajo de P-04 se apartó con `git stash` para corregir P-22 en un commit propio.)

## Context supplied
- `src/util_bbdd/bulk/_execution/batch.py` (`MySQLMultiRowInsertStrategy`), `tests/unit/bulk/test_insert_strategies_cache.py`
- `src/util_bbdd/dump/orchestrator.py` (uso de `BulkCrud`)
- Sesión `2026-06-01f-bulk-perf-optimization-option-c` (introdujo la caché de plantillas)

## AI output summary
- **Síntoma**: en la verificación de P-04 con `mariadbconnector` y varios lotes, la carga en la tabla temporal fallaba con "Table 'tmp_bulkupd_…' doesn't exist". Por separado, crear, cargar y borrar temporales funcionaba.
- **RCA**: `MySQLMultiRowInsertStrategy._build_sql_template` cacheaba por `(num_rows, cols)`, sin la tabla. El segundo INSERT con las mismas columnas y el mismo número de filas reutilizaba la plantilla con el nombre de la primera tabla.
- **Impacto confirmado** (MariaDB 11.4 + `mariadbconnector`): con una misma `BulkCrud`, INSERT en `zz_util_bbdd_a` y luego en `zz_util_bbdd_b` → las 4 filas en `a`, `b` vacía, sin error.
  - `dump` en modo secuencial comparte una `BulkCrud` para todas las tablas (`orchestrator.py:165`): una migración a MySQL/MariaDB con tablas de mismas columnas mezclaba filas en cada sub-lote completo de 1000.
  - Desde P-02 (`9bc03de`) la estrategia solo es la de defecto con drivers distintos de PyMySQL; antes, la de todos.
- **Fix**: la clave pasa a ser `(num_rows, quoted_table, cols)`; docstring actualizado.
- **Tests**:
  - `tests/unit/bulk/test_insert_strategies_cache.py`: 2 claves esperadas actualizadas al nuevo formato y 2 tests nuevos (plantillas distintas por tabla; filas en su tabla con SQLite real). Ambos fallaban antes del fix.
  - `tests/integration/test_bulk_engines.py`: `test_same_bulkcrud_inserts_into_two_tables_with_same_columns`. Sin el fix falla con `mariadbconnector`; con el fix pasa en los 6 motores y con `mariadbconnector`.
- **Validación**:
  - `ruff check src tests` y `mypy src` limpios.
  - Suite: 4484 passed / 29 skipped.
  - Integración: 28 passed, 2 skipped (6 motores); MariaDB con `mariadbconnector`: 5 passed.
- **P-21 registrado** (visto al verificar P-04): `bulk_update_from_df` falla con BLOB si el valor es UTF-8 válido (`TypeError: string argument without an encoding`), en MySQL/MariaDB + PyMySQL.
- `CHANGELOG.md` (Fixed) con aviso para revisar datos cargados con la misma `BulkCrud` en varias tablas.

## AUDIT_CODE
- Regresiones potenciales: ninguna funcional. La caché crece como mucho por tabla distinta (antes, por tamaño y columnas).
- Edge cases: la misma tabla con distintos tamaños o columnas sigue cacheando por separado, como antes.
- Compatibilidad: `_sql_template_cache` es privado; solo los tests dependían del formato de la clave.

## Directrices para Futuras IAs
- **[bulk/cachés]**: toda caché de SQL generado debe incluir en la clave todo lo que aparece en el texto (tabla, columnas, número de filas). Una instancia de estrategia vive lo mismo que su `BulkCrud`, que puede usarse con muchas tablas.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- Reanudar P-04 (`git stash pop` de "P-04 staging update (en curso)").
- P-21.
