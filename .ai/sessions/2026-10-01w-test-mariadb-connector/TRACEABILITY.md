# TRACEABILITY

## Session metadata
- id: 2026-10-01w-test-mariadb-connector
- fecha: 2026-10-01
- rama: develop (base `2ac4ee4`)
- flujo: Fase A del plan `../2026-10-01v-plan-pendientes-mariadb-connector/PLAN_AUDIT_PLAN.md` (D-1..D-5 recomendadas)

## Prompt issued
«PLAN y AUDIT-PLAN de lo pendiente. Necesito que se incluya en las pruebas el driver original de MariaDB» → «Si».

## AI output summary
- `tests/integration/test_bulk_engines.py`: motor `mariadb_connector` en `_engine_params` (URL de MariaDB con
  `mariadb+mariadbconnector`; se salta sin el paquete `mariadb`), `_url_env`/`_engine_url`, `MYSQL_FAMILY` con el
  conector. Eliminado `_mysql_driver_engines` (añadía el conector a mano en 2 tests; ahora es un motor parametrizado).
- `tests/integration/test_bulk_audit_20261001.py`: el test del lock wait timeout usa el motor `mariadb_connector`; el
  UPDATE demasiado largo de `isolate` lo incluye. Resultado: 50 ejecuciones de bulk con el conector (352 en total).
- `tests/integration/test_mariadb_engine_e2e.py` (nuevo, 7): managers `db_type="mariadb"` — sync con el conector
  (directa y `mariadb.ConnectionPool`; comprueba que la conexión es del módulo `mariadb`), async con aiomysql, catálogo,
  metadatos, inventario, `%` literales. El DEFAULT se fija como lo devuelve MariaDB (`'x'`, D-2).
- `tests/integration/test_update_auto_increment_mariadb.py`: parametrizado por driver (PyMySQL y conector); id con
  `SELECT LAST_INSERT_ID()` (con `mariadbconnector` SQLAlchemy no rellena `lastrowid` en `text()`; `probe_lastrowid.py`);
  contador de `orders` fijado a 101 (con el conector el executemany va en bloque e InnoDB reservaba hasta 128).
- Docs: `docs/guides/benchmarks.md` (banco de pruebas) y `.ai/runtime.md`.

## Validación
`ruff` limpio (los 5 errores de mypy de `test_bulk_engines.py` son anteriores y el fichero no está en el mypy del
proyecto); `pytest` 5978 passed, 426 skipped; `tests/integration` 572 passed (antes 513); `zensical build --strict` sin
avisos. Sin cambios en `src/`: ningún fallo de la librería con el conector.

## Directrices para Futuras IAs
- **[tests/mariadb]**: la librería usa MariaDB Connector/Python para `db_type="mariadb"` (y aiomysql en async); el banco
  usa PyMySQL. Los tests de MariaDB deben cubrir los dos (motor `mariadb_connector`).
- **[tests/mariadb]**: con `mariadbconnector`, `CursorResult.lastrowid` es `None` en `text()`; usar `LAST_INSERT_ID()`.
- **[tests/mariadb]**: el executemany del conector reserva AUTO_INCREMENT por bloques (huecos); no suponer contadores
  consecutivos tras un executemany.
- **[metadata/mariadb]**: `get_columns` devuelve el DEFAULT de MariaDB entre comillas (`'x'`); `migrate` lo normaliza
  con `column_default_hex`. Normalizarlo en los managers sería un cambio de salida pública (pendiente de decisión).

## Veredicto final
Veredicto: CLOSED
