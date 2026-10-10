# Revisión de la documentación — nivel 2 (D2)

## Método

El de `../2026-10-10-api-1-0-final/02_DOC_REVIEW.md` y `../2026-10-10-plan-pendientes-post-1-0/02_DOC_REVIEW.md`,
concretado en `PLAN_AUDIT_PLAN.md` §4. Comprobador: `tools/doc_check.py` (sigue las inclusiones `--8<--` de los
ejemplos) con lista de excepciones `tools/doc_check_allow.txt`. Logs: `build/logs/docsn2_*`.

## C1 — consolidación de `api/managers_sync_technical.md` (D1)

| Hallazgo | Dónde | Corrección |
|---|---|---|
| API pública inventada: `introspect()` → `DatabaseSchema`, `execute(query)`, `__init__(db_type, credenciales, pool_config?)`, `pool_config={"min_size", "max_size"}`, `host`/`port`… como parámetros del constructor | `api/managers_sync_technical.md` | Página borrada y fuera del `nav`; su única parte útil (componentes internos) pasa, verificada, a §3 de `api/managers_sync.md` |
| `db_type` sin `mysql` | `api/managers_sync.md` | Lista de `get_supported_db_types()` (7 motores) |
| «`conn_params` debe incluir `database`» | `api/managers_sync.md` | Obligatorios por motor según `DatabaseTypeValidator.get_required_params` (Oracle: `user`, `password`; HSQLDB: `user`, `jdbc_url`, `jdbc_jar`) |
| Tabla de errores incompleta: sin `InvalidDatabaseType` ni `DatabaseConfigurationError`; «`ConnectionError` si no se puede conectar» | `api/managers_sync.md` | Probado: `db_type="foo"` → `InvalidDatabaseType`; falta de parámetros → `ValidationError`; PostgreSQL inalcanzable con pool → `DatabaseConfigurationError` (tras el timeout del pool, 30 s); `ConnectionError` solo en conexión única |
| Faltaban `execute_query_one`, `init`, `get_connection`/`release_connection`, `clear_cache`, `queries_file`; `ValueError` de `get_storage_inventory` sin `tablespace` en Oracle/PostgreSQL | `api/managers_sync.md` | Añadidos con su firma (`inspect.signature`) |

## Fuera de alcance (registrado)

- `SyncDatabaseManager.__init__` documenta `ConnectionError` si falla la conexión inicial, pero con pool (lo habitual)
  el fallo llega como `DatabaseConfigurationError` («pool initialization incomplete after 30 sec»). Documentado tal
  cual; unificar la excepción sería un cambio de contrato (decisión del usuario).
- El docstring de la clase y de `__init__` omite MySQL en la lista de motores y nombra `DatabaseValidationError` /
  `DatabaseDriverError`, que no existen (son `ValidationError` / `DriverError`). Es `src/`: no se toca en esta sesión.
