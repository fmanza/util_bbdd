# COMMIT MESSAGE - READY FOR GITHUB

## Conventional Commits format

```
fix: remediar diagnósticos de SonarQube y Pylance en tests y contratos

- fix(tests): cambiar comparación directa de float por epsilon en test_normalize.py
  Resuelve SonarQube python:S1244. Comparación segura usando abs(result - expected) < 1e-10
  siguiendo el patrón de otros tests en la misma clase (test_np_float64_returns_float).

- fix(types): actualizar firma de normalize_oracle_type para aceptar None
  Resuelve Pylance reportArgumentType. Cambio en firma: oracle_type: str -> str | None.
  La función ya manejaba None internamente (retorna 'object' para None).

- fix(tests): agregar métodos faltantes a mocks de adapters
  Resuelve Pylance reportArgumentType en test_postgresql_adapter_parity_mariadb.py.
  Todos los mocks ahora implementan completamente sus correspondientes protocolos:

  * PostgreSQLSyncManagerProtocol: Agregados _cache_context_key, _get_query_context_label,
    _get_query_context_database, _get_cached_rows, _execute_metadata_many

  * PostgreSQLAsyncManagerProtocol: Idem anterior + execute_custom_one, con anotaciones
    de tipo en _get_cached_rows_async y await asyncio.sleep(0)

  * MariaDBSyncManagerProtocol: Agregados get_tables, get_columns, get_primary_keys,
    get_foreign_keys, get_indices, execute_query_many, execute_custom_one

- fix(code-quality): agregar await asyncio.sleep(0) en funciones async de mocks
  Resuelve SonarQube python:S7503 (funciones async sin operaciones asincrónicas).
  Aplicado a: _get_cached_rows_async, _execute_metadata_many, execute_custom_one
  en MockAsyncManager (PostgreSQL).

Cambios:
- tests/unit/test_normalize.py: 1 cambio (línea 120)
- src/util_bbdd/metadata/oracle/common.py: 1 cambio (firma de función)
- tests/unit/test_postgresql_adapter_parity_mariadb.py: Múltiples cambios en 3 test methods

Sesión de remediación: 2026-06-01e-sonarqube-pylance-fixes
Documentación: .ai/sessions/2026-06-01e-sonarqube-pylance-fixes/
```

## Alternative short version (si se prefiere más conciso)

```
fix: remediar diagnósticos de SonarQube/Pylance en tests y tipos

Resuelve:
- SonarQube S1244: Comparación segura de floats en test_normalize.py
- Pylance reportArgumentType: Actualizar firma de normalize_oracle_type(str | None)
- Pylance reportArgumentType: Agregar métodos faltantes a mocks de adapters
- SonarQube S7503: Agregar await asyncio.sleep(0) en funciones async

Archivos: test_normalize.py, oracle/common.py, test_postgresql_adapter_parity_mariadb.py
```

## Changes summary for PR description

```
## Descripción

Esta PR remedia diagnósticos reportados por SonarQube y Pylance en el análisis estático
de código. Los cambios son acotados y enfocados en conformidad con herramientas de
verificación de calidad.

### Cambios específicos

#### 1. test_normalize.py (S1244 - Comparación de floats)
- Cambio: Línea 120, actualizar test_native_float_passthrough()
- Antes: `assert normalize_sql_literal(1.5) == 1.5`
- Después: Comparación con epsilon para evitar problemas de punto flotante
- Razón: SonarQube python:S1244 - No realizar comparaciones directas de valores float

#### 2. oracle/common.py (Pylance - Tipos)
- Cambio: Firma de función normalize_oracle_type()
- Antes: `def normalize_oracle_type(oracle_type: str) -> str:`
- Después: `def normalize_oracle_type(oracle_type: str | None) -> str:`
- Razón: La función ya acepta None en la lógica (retorna 'object'). Firma ahora refleja esto.

#### 3. test_postgresql_adapter_parity_mariadb.py (Pylance + S7503)
- Cambios en tres test methods que crean mocks
- Agregados todos los métodos requeridos por los protocolos correspondientes
- Agregados await asyncio.sleep(0) en funciones async para satisfacer S7503
- Anotaciones de tipo completas en parámetros de mocks

### Verificación
- ✅ Todos los diagnósticos de S1244 resueltos
- ✅ Todos los diagnósticos de reportArgumentType resueltos
- ✅ Todos los diagnósticos de S7503 resueltos
- ✅ Sin cambios funcionales; solo remedios de tipo y completitud de protocolos
- ✅ Documentación en .ai/sessions/2026-06-01e-sonarqube-pylance-fixes/

### Impacto
- Riesgo: BAJO (cambios acotados, sin refactoring)
- Compatibilidad: Backward compatible (firma de tipo más amplia en normalize_oracle_type)
- Testing: Ningún cambio en lógica de tests, solo en aserción de float
```
