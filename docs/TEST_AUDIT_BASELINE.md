# TEST AUDIT BASELINE (FASE 0)

Fecha: 2026-03-12  
Scope: inventario, clasificacion, duplicacion, flakiness y baseline de rendimiento de la suite `pytest`.

## 1) Comandos ejecutados

- `pytest -q --durations=20` (baseline completo)
- `pytest -q --collect-only -m unit`
- `pytest -q --collect-only -m integration`
- `rg --files tests`
- `rg -n "@pytest\.fixture" tests/conftest.py tests/integration/conftest.py`
- `rg -n "time\.sleep|asyncio\.sleep|random\.|uuid4\(|datetime\.(now|utcnow)|date\.today\(|pytest\.mark\.flaky|flaky" tests`
- `rg -n "def _install_fake_" tests`

Artefacto de salida cruda:

- `docs/METRICS_BASELINE_BEFORE.txt`

## 2) Inventario actual de tests

### Conteo por archivos `test_*.py`

- Total archivos de test: 45
- `tests/unit`: 33
- `tests/integration`: 2
- `tests/` raiz: 10

### Conteo de tests recolectados

- Total casos recolectados por pytest: 449

### Archivos detectados

```text
tests/test_async_mariadb.py
tests/test_async_manager_lifecycle.py
tests/test_async_factory_selection.py
tests/test_async_contracts.py
tests/integration/test_sync_e2e.py
tests/integration/test_async_e2e.py
tests/unit/test_execute_custom_query_contract.py
tests/unit/test_error_wrapping_raise_from.py
tests/unit/test_engine_capabilities.py
tests/unit/test_documentation_contract.py
tests/unit/test_database_queries_refactor_pr5.py
tests/unit/test_database_manager_normalized_methods.py
tests/unit/test_database_manager_get_ddl_fallback.py
tests/unit/test_database_exceptions_pr0.py
tests/unit/test_contract_return_types.py
tests/unit/test_bind_usage.py
tests/unit/test_async_sync_parity_results.py
tests/unit/test_async_executor_contract.py
tests/unit/test_async_database_manager_cache.py
tests/unit/test_async_database_manager.py
tests/test_util_bbdd_core.py
tests/test_async_sqlserver.py
tests/test_async_sqlite.py
tests/test_async_sqlalchemy_engine_factory.py
tests/test_async_postgresql.py
tests/test_async_oracle.py
tests/unit/test_timeout_behavior.py
tests/unit/test_sync_executor_contract.py
tests/unit/test_sync_close_strict.py
tests/unit/test_sync_async_contract.py
tests/unit/test_result_normalizer.py
tests/unit/test_query_resolver_simplified.py
tests/unit/test_query_registry.py
tests/unit/test_oracle_lob_executor_materialization.py
tests/unit/test_metadata_normalization.py
tests/unit/test_execute_query_contract.py
tests/unit/validators/test_oracle_validator.py
tests/unit/validators/test_mariadb_validator.py
tests/unit/validators/test_hsqldb_validator.py
tests/unit/test_validators_advanced_pr4.py
tests/unit/test_validations_by_motor.py
tests/unit/validators/test_sqlserver_validator.py
tests/unit/validators/test_sqlite_validator.py
tests/unit/validators/test_postgresql_validator.py
tests/unit/validators/test_validators_factory.py
```

## 3) Clasificacion unit vs integration (estado real)

Clasificacion por estructura:

- `tests/integration/*`: 2 archivos (bloque E2E/integration)
- `tests/unit/*`: 33 archivos (unit)
- `tests/test_*.py` en raiz: 10 archivos no separados por dominio

Validacion por markers (comportamiento actual):

- `pytest -q --collect-only -m unit` -> selecciona toda la suite (449 items)
- `pytest -q --collect-only -m integration` -> 0 seleccionados (449 deselected)

Conclusion:

- La clasificacion por marker no esta alineada con la estructura de carpetas.
- Existe sobreasignacion de `unit` en coleccion.

## 4) Duplicacion detectada

### 4.1 Duplicacion de fixtures

- `tests/conftest.py`: 364 lineas, 22 fixtures.
- `tests/integration/conftest.py`: 248 lineas, 9 fixtures.

Bloques muy similares en `tests/conftest.py`:

- `mock_mysql_engine`, `mock_engine`, `mock_postgresql_engine`, `mock_oracle_engine`, `mock_sqlite_engine`, `mock_mariadb_engine`, `mock_sqlserver_engine` (lineas 32-108).
- Patrons repetidos de inicializacion `MagicMock` + `dialect/url/connect`.

### 4.2 Duplicacion de helpers por motor async

Se repite el mismo patron `install fake driver + 4 tests por motor` en 5 archivos:

- `tests/test_async_mariadb.py`
- `tests/test_async_postgresql.py`
- `tests/test_async_oracle.py`
- `tests/test_async_sqlite.py`
- `tests/test_async_sqlserver.py`

Evidencia: 10 helpers `def _install_fake_*` detectados.

### 4.3 Duplicacion de escenarios timeout/error

Escenarios de timeout similares repartidos entre:

- `tests/unit/test_timeout_behavior.py`
- `tests/unit/test_sync_executor_contract.py`
- `tests/unit/test_async_executor_contract.py`

## 5) Flakiness: hallazgos y riesgo

No hay tests marcados con `@pytest.mark.flaky`.

Se detectan 10 usos de `sleep`:

- `tests/integration/conftest.py:104` (`time.sleep(0.1)`)
- `tests/integration/conftest.py:226` (`time.sleep(0.1)`)
- `tests/unit/test_timeout_behavior.py:42` (`time.sleep(0.05)`)
- `tests/unit/test_timeout_behavior.py:63` (`time.sleep(0.05)`)
- `tests/unit/test_timeout_behavior.py:85` (`await asyncio.sleep(0.05)`)
- `tests/unit/test_timeout_behavior.py:112` (`await asyncio.sleep(0.05)`)
- `tests/unit/test_sync_executor_contract.py:271` (`time.sleep(0.05)`)
- `tests/unit/test_sync_executor_contract.py:296` (`time.sleep(0.05)`)
- `tests/unit/test_async_executor_contract.py:210` (`await asyncio.sleep(5)`)
- `tests/test_async_sqlalchemy_engine_factory.py:23` (`await asyncio.sleep(0)`)

Riesgo de flakiness:

- Medio en tests de timeout por margenes cortos (`0.05s`) y scheduler del SO.
- Medio en teardown de integration por dependencia de `sleep(0.1)`.
- Bajo en el resto (la mayoria son deterministas con mocks).

## 6) Baseline de ejecucion (FASE 0)

Ejecucion base (`pytest -q --durations=20`):

- Recolectados: 449
- Resultado: 420 passed, 20 failed, 9 errors
- Duracion total: 10.14s

### Top 10 tests mas lentos

1. `1.03s` call `tests/test_async_sqlite.py::test_async_sqlite_pool_close_timeout_does_not_block`
2. `0.19s` teardown `tests/integration/test_async_e2e.py::...::test_e2e_async_get_columns`
3. `0.19s` teardown `tests/integration/test_sync_e2e.py::...::test_e2e_connection_reuse`
4. `0.18s` teardown `tests/integration/test_sync_e2e.py::...::test_e2e_get_columns_info`
5. `0.18s` teardown `tests/integration/test_sync_e2e.py::...::test_e2e_simple_select_query`
6. `0.18s` teardown `tests/integration/test_sync_e2e.py::...::test_e2e_query_not_found`
7. `0.18s` teardown `tests/integration/test_async_e2e.py::...::test_e2e_async_query_not_found`
8. `0.18s` teardown `tests/integration/test_async_e2e.py::...::test_e2e_async_simple_select`
9. `0.18s` teardown `tests/integration/test_async_e2e.py::...::test_e2e_async_insert`
10. `0.18s` teardown `tests/integration/test_sync_e2e.py::...::test_e2e_transaction_consistency`

### Principales grupos de fallo observados en baseline

- `ModuleNotFoundError` en integration async E2E:
  - falta modulo `util_bbdd.query_registry` (9 errores)
- Errores de binds/params en integration sync E2E:
  - `Incorrect number of bindings supplied`
- Timeouts y firmas de mocks no alineadas en tests de executors:
  - `missing 1 required positional argument: 'params'/_params`

## 7) Estado de aceptacion FASE 0

- [x] Enumerar archivos de tests actuales
- [x] Clasificar unit vs integration (incluyendo gaps de clasificacion)
- [x] Identificar duplicacion (fixtures/helpers/mocks)
- [x] Detectar focos de flakiness
- [x] Capturar baseline de tiempos con `--durations=20`
- [x] Dejar evidencia en documento y artefacto crudo

## 8) Backlog inmediato para FASE 1

1. Corregir estrategia de markers (`unit/integration`) para que no mezcle toda la suite.
2. Mover tests raiz `tests/test_*.py` a carpetas de dominio (`unit` o `integration`) segun comportamiento.
3. Preparar extraccion de fixtures repetidas de `tests/conftest.py` hacia `tests/fixtures/*`.
4. Sustituir `sleep` de teardown/timeout por sincronizacion determinista (monkeypatch/fakes).
