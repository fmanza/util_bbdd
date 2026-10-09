# TRACEABILITY

## Session metadata
- id: 2026-10-09j-hotfix-pool-reset
- fecha: 2026-10-09
- rama: develop
- skill: diagnóstico de log → hotfix
- fase: diagnóstico (contra el servidor real, solo lectura) + PLAN + AUDIT_PLAN + IMPLEMENT (RCA + fix) + AUDIT_CODE + VERSION

## Prompt issued
```text
Lee C:\Desarrollo\Proyectos\pruebas_util\ficheros\salida\log\log_01.log y dime por qué no se puede generar la
documentación de una BBDD MariaDB; ayúdame a configurarlo sin tocar la configuración de la base de datos.

/hotfix
Bug: con use_pool=True, mariadb.ConnectionPool hace COM_RESET_CONNECTION al reutilizar una conexión; la sesión vuelve
al charset del servidor (latin1) y no se re-ejecuta init_command → SystemError/UnicodeDecodeError en fetchrows.
```

## Context supplied
- Log: `MetadataError: Error leyendo el catálogo de MariaDB (SystemError del driver mariadb, 3 intentos sin fallback):
  CONVERT strategy failed … Diagnosis: utf8mb4_clean` en `get_ddl` → `_snapshot(COLUMNS, PRIMARY_KEYS)`.
- `doc_bbdd_param.toml` (`[conexion.mariadb]`, `init_command = "SET SESSION character_set_server = utf8mb4, NAMES utf8mb4"`).
- Servidor `10.20.0.245`: MariaDB 10.3.10, `@@character_set_server = latin1`; driver `mariadb` 1.1.14.

## AI output summary
- **Descartado**: datos corruptos. `CAST(... AS BINARY)` de COLUMNS/TABLES/KEY_COLUMN_USAGE/STATISTICS/VIEWS/ROUTINES
  (13.900 filas): 0 campos con bytes no UTF-8. La consulta de COLUMNS completa funciona en crudo con los kwargs exactos
  de la librería, tras ROUTINES y tras `rollback()`.
- **Reproducción**: `DatabaseDocumentation` con `use_pool=True` falla a los 4 s (Word 1/13); con `use_pool=False` genera
  sin errores. `pool_size=1` también falla.
- **RCA**: `mariadb.ConnectionPool` (`pool_reset_connection=True` por defecto) reinicia la sesión al reutilizar la
  conexión y no repite `init_command`. Comprobado en crudo: 1.er uso charsets utf8mb4 → COLUMNS OK; 2.º uso
  `('latin1','latin1','latin1')` → `SystemError … fetchrows`; con `pool_reset_connection=False`, utf8mb4 en ambos.
  El diagnóstico de charset sale `utf8mb4_clean` porque se hace con una conexión recién abierta.
- **Fix**: `pool_connection_mariadb.PoolConnection` guarda el `init_command` aceptado por el pool en
  `_pending_init_command`, de modo que `get_connection()` lo ejecuta en cada entrega (la vía ya existía para drivers
  que lo rechazan). Descartado `pool_reset_connection=False`: arrastraría estado de sesión entre usos.
- **Test-first**: `tests/unit/connection/mariadb/test_mariadb_pool_reset_init_command.py` (3; fallaban antes del fix).
  `test_pool_no_pending_init_command_when_pool_accepts_it` fijaba el comportamiento erróneo: renombrado a
  `test_pool_reapplies_init_command_when_pool_accepts_it`.
- **Validación**: `ruff` OK; `mypy` sin errores (332 ficheros); `pytest` 5449 passed, 507 skipped
  (`build/logs/hotfix_pool_reset_results.txt`); generación real con pool contra el servidor sin `SystemError`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/connection/mariadb/pool_connection_mariadb.py` | modificado |
| Tests | `tests/unit/connection/mariadb/test_mariadb_pool_reset_init_command.py` | nuevo |
| Tests | `tests/unit/connection/mariadb/test_mariadb_driver_connection.py` | test adaptado al contrato nuevo |
| Docs | `docs/guides/connection_guide.md` | § 6 y «Problemas frecuentes» |
| VERSION | `CHANGELOG.md`, `pyproject.toml`, `README.md`, `docs/index.md`, `docs/roadmap.md`, `docs/architecture.md`, `.ai/CURRENT_STATE.md`, `.ai/sessions/SESSIONS_DIGEST.md` | 0.40.3 |

## Directrices para Futuras IAs
- **[MariaDB/pool]**: `mariadb.ConnectionPool` reinicia la sesión al reutilizar conexiones (`pool_reset_connection=True`) y no repite `init_command`; `PoolConnection.get_connection()` lo reaplica siempre (`_pending_init_command`). Un fallo que solo aparece con `use_pool=True` y desde la 2.ª consulta por conexión apunta a estado de sesión perdido.
- **[MariaDB/charset]**: `SystemError: <method 'fetchrows' …> returned a result with an exception set` con `UnicodeDecodeError` en la cadena = el servidor envía bytes en el charset de la sesión (p. ej. latin1) y el driver 1.1.x los decodifica como utf8mb4. Mirar `@@character_set_results` de la conexión que falla, no de una nueva.
- **[diagnóstico]**: `CharsetStateDetector` diagnostica una vez con la primera conexión: no ve estados de sesión posteriores.
- **[técnica]**: para aislar fallos dependientes de la conexión, parchear `mariadb.cursors.Cursor.execute`/`fetch*` y `mariadb.connections.Connection.__init__` en un `runpy` del script real (traza por `id(connection)`).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- El pool nativo de MySQL (`mysql.connector` pooling, `reset_session`) puede tener el mismo patrón; no verificado (fuera de alcance).
- Push y tag `v0.40.3` hechos (2026-10-09).
