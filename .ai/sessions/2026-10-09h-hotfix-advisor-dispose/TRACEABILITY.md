# TRACEABILITY

## Session metadata
- id: 2026-10-09h-hotfix-advisor-dispose
- fecha: 2026-10-09
- rama: develop
- skill: audit-code → hotfix
- fase: AUDIT_CODE (log de `pruebas_util`) + PLAN + IMPLEMENT (RCA + fix) + AUDIT_CODE + VERSION

## Prompt issued
```text
/audit-code
Log C:\Desarrollo\Proyectos\pruebas_util\ficheros\salida\log\util_bbdd.log: líneas 51–63 superan el minuto
(¿problema de rendimiento en util_bbdd.connection.performance_advisor?) y, al terminar la aplicación,
«Exception closing connection <mariadb.connection …> … mariadb.InterfaceError: Invalid connection or not connected».

/hotfix
H1 (Media): EngineReadinessAdvisor muestra autocommit/write_timeout/read_timeout como OK con valores por defecto
que no ha leído. H2 (Media-baja): SyncDatabaseManager.close() llama engine.dispose() también en la finalización
del intérprete. Fix mínimo, tests de regresión.
```
Usuario: «pudes continuar» tras el veredicto APROBADO CON CONDICIONES de `/audit-code`.

## Context supplied
- Log de la app `C:\Desarrollo\python\pruebas_util` (`src/main.py`, `src/bulk_crud_audit/pruebas.py`).
- Banco Docker (MariaDB 11.4, `127.0.0.1:53307`); mismas versiones que la app: Connector/Python 1.1.14,
  SQLAlchemy 2.1.3, Python 3.14.2.

## AI output summary
- **Audit (sin cambio de código)**: el advisor no tiene problema de rendimiento (`report_once` mide 9–12 ms en el
  banco: una conexión y dos `SHOW VARIABLES`). Líneas 51→52 (11 s): la app genera tres DataFrames de 1M filas antes de
  `BulkCrud(...)`; líneas 52→63 (83 s): el primer `bulk_insert_from_df(generar_sql=False)` (`83.029s` en la línea 64).
  Parece del advisor porque `bulk` solo registra el final de cada operación (H3, no corregido).
- **RCA H1**: `_conn_params_from_engine` solo obtiene host/port/database y pool; `_check_mysql` rellenaba
  `autocommit`/`write_timeout`/`read_timeout` (y `pool_size`) con valores por defecto y los informaba como OK.
  Reproducido en el banco con `write_timeout=5`, `read_timeout=5`, `autocommit=True` → informe «OK False/60s/30s».
- **RCA H2**: la app no llama a `close()`; los managers se cierran desde `__del__` en la finalización y `close()`
  hace `engine.dispose()`, que cierra las conexiones del driver en un momento no fiable. El cierre en finalización se
  reprodujo en el banco (misma secuencia de logs) pero sin el `InterfaceError` (4 ejecuciones): depende del entorno
  (servidor remoto, orden de finalización). Fix defensivo coherente con `connection/close.py`, que ya trata
  `sys.is_finalizing()` en los pools nativos.
- **Fix**: `_check_mysql` emite los checks estáticos solo con la clave presente en `conn_params`;
  `SyncDatabaseManager.close()` hace `engine.dispose(close=not sys.is_finalizing())`.
- **Test-first**: 5 tests nuevos fallaban antes del fix (`tests/unit/connection/test_performance_advisor.py::
  TestMySQLStaticChecksOnlyKnownValues`, `tests/unit/test_manager_sqlalchemy_engine_cache.py::
  test_sync_manager_close_does_not_close_engine_connections_during_finalization`).
- **Validación**: `ruff check`/`ruff format` OK; `mypy` sin errores en 332 ficheros
  (`build/logs/hotfix_v0.40.1_mypy.txt`); `pytest` 5427 passed, 507 skipped (`build/logs/hotfix_v0.40.1_pytest.txt`);
  `zensical build --strict` OK; banco: el informe ya no muestra los tres valores no leídos.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/connection/performance_advisor.py`, `src/util_bbdd/managers/sync_mgr.py` | modificados |
| Tests | `tests/unit/connection/test_performance_advisor.py`, `tests/unit/test_manager_sqlalchemy_engine_cache.py` | ampliados |
| VERSION | `CHANGELOG.md`, `pyproject.toml`, `README.md`, `docs/index.md`, `docs/roadmap.md`, `docs/architecture.md`, `.ai/CURRENT_STATE.md`, `.ai/sessions/SESSIONS_DIGEST.md` | 0.40.1 |

## Directrices para Futuras IAs
- **[advisor]**: `EngineReadinessAdvisor.report_once(engine)` solo conoce lo que hay en `engine.url` y `engine.pool`; los parámetros del driver van en el `creator` (ADR-005) y no son visibles. Un check que no tenga el valor no debe informarlo con un valor por defecto.
- **[logs de bulk]**: el tiempo entre el informe del advisor y «bulk X finalizado» es la operación entera: `bulk` no registra el inicio (H3, pendiente). No atribuirlo al advisor.
- **[cierre en finalización]**: `sys.is_finalizing()` ya decide el cierre de los pools nativos (`connection/close.py`) y, desde v0.40.1, del Engine sync (`dispose(close=False)`). Para reproducir un cierre en finalización, mantener los managers vivos con una referencia global; como locales de una corrutina se liberan antes.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- H3: log DEBUG al iniciar cada operación de `bulk` (observabilidad; no es hotfix).
- `_check_mysql` supera la complejidad cognitiva de Sonar (18/15) tras el fix; extraer un helper es refactor, fuera de hotfix.
- `AsyncDatabaseManager.close()` hace `await engine.dispose()`: en finalización no hay loop, caso distinto, sin evidencia de fallo.
- En `pruebas_util` (no es la librería): cerrar los managers en el `finally` de `main.py` y devolver las conexiones de `get_connection()`.
- Push y tag `v0.40.1` pendientes.
