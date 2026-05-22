# TRACEABILITY

## Session metadata
- id: 2026-05-22g-hotfix-sqlserver-routines
- fecha: 2026-05-22
- rama: develop
- skill: hotfix
- fase: RCA + FIX + AUDIT_CODE

## Prompt issued
`AttributeError: 'SyncDatabaseManager' object has no attribute 'execute'` al ejecutar
`src\util_bbdd\migrate` sobre SQL Server con `source_engine="sqlserver"`.
Traceback en `migrate/extractors/sqlserver.py → _plan_from_sqlserver →
extract_routines → fetch_routines_sync → connection.execute(sql, params)`.

## Context supplied
- `src/util_bbdd/migrate/extractors/sqlserver.py` — extractor afectado
- `src/util_bbdd/metadata/sqlserver/routines.py` — funciones `fetch_routines_sync` / `fetch_routine_body_sync`
- `src/util_bbdd/metadata/sqlserver/_adapter_helpers.py` — SQL builders
- `src/util_bbdd/managers/sync_mgr.py` — API pública `execute_custom_many`
- `tests/unit/migrate/test_sqlserver_extractor.py` — suite existente de referencia

## AI output summary
- **RCA**: `extract_routines()` llamaba a `fetch_routines_sync(self._manager, schema)` y
  `fetch_routine_body_sync(self._manager, schema, routine_name)` de `metadata/sqlserver/routines.py`.
  Esas funciones invocan `connection.execute(sql, params)` — API DB-API 2.0 raw — pero
  `self._manager` es `SyncDatabaseManager`, que no expone `.execute()` sino `execute_custom_many()`.
  Todos los demás métodos del extractor usan `self._query()` (wrapper de `execute_custom_many`);
  `extract_routines()` saltó esa abstracción, introduciendo la regresión con la sesión
  `2026-05-22e-migrate-routines`.
- **FIX**: Eliminado import `fetch_routine_body_sync, fetch_routines_sync` de `routines.py`.
  Añadido import `build_sqlserver_routine_body_query, build_sqlserver_routines_query` de
  `_adapter_helpers`. `extract_routines()` reescrito para usar `self._query()` con los SQL
  builders, parseando filas inline (consistente con el resto del extractor).
- **AUDIT_CODE**: 25 tests pasan en `test_sqlserver_extractor.py`; 0 regresiones.
  `fetch_routines_sync` y `fetch_routine_body_sync` en `metadata/` no modificados.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix `extract_routines()` + import `_adapter_helpers` | `src/util_bbdd/migrate/extractors/sqlserver.py` | completado |
| `TestExtractRoutines` (4 casos + regresión `.execute`) | `tests/unit/migrate/test_sqlserver_extractor.py` | completado |

## Directrices para Futuras IAs

- **[migrate/extractors]**: Todo acceso a BD en los extractores de `migrate/` DEBE ir a través de
  `self._query(sql, params)` (wrapper de `execute_custom_many`). Nunca pasar `self._manager`
  a funciones de `metadata/` que esperen una conexión raw DB-API 2.0 (`connection.execute`).
- **[metadata/sqlserver/routines.py]**: Las funciones `fetch_routines_sync`, `fetch_routine_body_sync`
  y `fetch_routine_parameters_sync` esperan un objeto con `.execute(sql, params)` (raw connection),
  no un `SyncDatabaseManager`. No usarlas desde los extractores de `migrate/`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Reinstalar el paquete en el entorno afectado: `pip install -e c:\Desarrollo\python\libs\util_bbdd`
