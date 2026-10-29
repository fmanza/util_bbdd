# TRACEABILITY

## Session metadata
- id: 2026-10-29-web-gaps-ola8
- fecha: 2026-10-29
- rama: develop
- skill: new_feature + version-closure
- fase: IMPLEMENT + AUDIT_CODE + VERSION de la ola 8 (v5.0.0)

## Prompt issued
Ola 8 del plan de huecos de util_bbdd_web (Grupo 8, util_bbdd 5.0.0: valores por defecto seguros): fases U-8.1 …
U-8.6, un commit por fase en `develop`; MAJOR 5.0.0; decisiones D8-1 … D8-8 aprobadas (§4 del plan); guía
`docs/guides/api_5_0_migration.md` nueva en U-8.1 y ampliada en cada fase que rompe. Plan canónico:
`docs/plan/UTIL_BBDD_GAPS_PLAN.md` de util_bbdd_web (PLAN y AUDIT_PLAN emitidos allí; aquí solo IMPLEMENT).

## Context sources
- `src/util_bbdd/dump/_models.py`, `bulk/crud.py`, `doc/database_documentation.py`,
  `doc/infrastructure/runtime/output_runtime.py`, `executors/` (`_read_only.py`, ejecutores sync y async),
  `managers/`, `results/types.py`, `metadata/` (`contracts.py`, `source.py`, `oracle/catalog.py`), `bulk/audit.py`,
  `connection/config.py`, `data/database_types.json`.
- util_bbdd_web: tabla de firmas 4.6.0 del Grupo 8 y fases W-8.x del plan.

## AI output summary
- Un commit por fase (ruff, ruff format, mypy, pytest completo y `zensical build --strict` en cada una; AUDIT_CODE tras
  cada fase):
  - U-8.1 `d7a8f519` G30: `DumpConfig.truncate_target: bool = False`; fuera `_TruncateTargetField`, `_ImplicitTrue`,
    el `FutureWarning` y su filtro de `pytest.ini`. Guía `api_5_0_migration.md` creada (en la navegación).
  - U-8.2 `152d6a40` G35: `_resolve_generar_sql` da `False` sin argumentos y sin aviso; `generar_sql` alias de
    `dry_run` (D8-2); `ValueError` si se contradicen.
  - U-8.3 `9e25d843` G2: ventana por defecto 0. Con ventana 0 no se reutiliza la caché y el nombre automático lleva
    `-2`, `-3`… si coincide el segundo o la carpeta existe (`DocumentationOutputRuntime._unique_auto_name`).
  - U-8.4 `11648d4e` G42: `execute_custom_result` → `CustomQueryResult(columns, rows)` (`util_bbdd.results`) en los
    dos managers y ejecutores. Con `read_only` y `timeout`, PostgreSQL añade `SET LOCAL statement_timeout` al prólogo
    y la cancelación (SQLSTATE 57014) se lanza como `QueryTimeoutError` (D8-4). asyncpg: columnas de `conn.prepare()`.
  - U-8.5 `7f28ed92` G43: Protocol opcional `FullServerVersionCatalogDialect.full_server_version_sql(version)`;
    `CatalogSource.server_version()` lee `VERSION` y, en Oracle 18c+, `VERSION_FULL`. `server_version_info()` y
    `get_server_version_info()` en fuentes y managers.
  - U-8.6 `251e51a3` D8-8: fuera el setter de `AuditManager.columnas_auditoria` y `encoding_errors` de MariaDB
    (config, validación, aviso, `optional` y `kinds` del JSON).
- Evidencias: pytest 6835 passed, 616 skipped (`build/logs/u8_6_pytest.txt`); mypy limpio (355 ficheros);
  `zensical build --strict` limpio. Banco: integración PostgreSQL de U-8.4 (psycopg y asyncpg, corte en el servidor
  en < 5 s); columnas con 0 filas y repetidas en MySQL, MariaDB, SQL Server y Oracle; `get_server_version_info()`
  igual a `server_version_info` de SQLAlchemy en PostgreSQL 17.11, MySQL 8.4.11, MariaDB 11.4.13, SQL Server 16.0 y
  Oracle 23.26.3 (T8-2 verificado). Integración completa (`-m integration`, 6 motores con `JAVA_HOME`): 661 passed, 7 skipped y 12 fallos en `test_dump_engines.py` causados por U-8.1 (el helper `Setup.run` contaba con `truncate_target=True` implícito); corregidos en `39c0083c` y repetidos: 76 passed (`build/logs/ola8_integration.txt`, `build/logs/ola8_integration_dump.txt`). Wheel 5.0.0 + `.sha256` (`f25a81c3…2d0`) probado en un venv limpio.
- `scripts/gen_arquitectura_capas.py`: sin aristas nuevas (solo finales de línea, revertidos); 355 ficheros.
- VERSION: `release: v5.0.0`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Ola 8 | `dump/_models.py`, `bulk/crud.py`, `doc/database_documentation.py`, `doc/infrastructure/runtime/output_runtime.py`, `results/types.py`, `results/__init__.py`, `executors/_read_only.py`, `executors/sync_query_executor.py`, `executors/async_query_executor.py`, `managers/sync_mgr.py`, `managers/async_mgr.py`, `metadata/contracts.py`, `metadata/source.py`, `metadata/oracle/catalog.py`, `bulk/audit.py`, `audit/legacy_csv.py`, `connection/config.py`, `data/database_types.json` | completado (v5.0.0) |
| Tests | `tests/integration/test_dump_engines.py` (`39c0083c`, tras la integración); nuevos: `tests/unit/dump/test_truncate_target_default.py` (renombrado de `test_truncate_target_warning.py`), `tests/unit/test_custom_sql_result.py`, `tests/unit/test_server_version_full.py`, `tests/integration/test_custom_sql_result_postgresql.py`; ajustados `test_dry_run.py`, `test_documentation_runtime.py`, `test_doc_generate_sqlite_e2e.py`, `test_database_documentation.py`, `test_manager_server_info.py`, `test_audit_subsystem.py`, `test_mariadb_charset_init_command.py`, `test_orchestrator.py`, `test_parallel_loader_audit.py`, `test_reflect_fk_chain.py`, `test_secondary_indexes_all.py` | completado |
| Docs | `docs/guides/api_5_0_migration.md` (nuevo, en `mkdocs.yml`), `docs/api/{dump,bulk_crud,database_documentation,managers_sync,managers_async,query_execution,intro,bulk_audit,connection_factory}.md`, guías de dump y conexión, ejemplos | completado |

## Desviaciones del plan
- U-8.1: también se toca `pytest.ini` (filtro del `FutureWarning` de G30, ya sin objeto).
- U-8.3: el sufijo es `-N` (no `_N`: la fecha ya lleva `_`). La caché se sigue escribiendo con ventana 0, solo para
  numerar dentro del segundo; la comprobación en disco cubre otros procesos que ya crearon su carpeta, no dos procesos
  en el mismo segundo antes de crearla (la web pasa `fichero_salida`).
- U-8.4: `CustomQueryResult` se exporta desde `util_bbdd.results`, no desde la raíz (la API 1.0 limita la raíz a los
  13 puntos de entrada). El corte en el servidor da `QueryTimeoutError` (no `DatabaseOperationError`), con el error del
  driver en `__cause__`. Una sentencia sin conjunto de resultados da `CustomQueryResult()` sin leer filas. Plazo no
  finito (`inf`/`nan`): sin límite en el servidor.
- U-8.5: el plan decía «`VERSION_FULL` y, si falla, `VERSION`». Se hace al revés: `VERSION` primero y `VERSION_FULL`
  solo si es 18 o más, porque el ejecutor de catálogo de los managers hace `rollback()` al fallar una consulta y
  desharía la transacción del usuario (`use_pool=False`). Mismo resultado, sin consultas que fallen.
- U-8.6: `encoding_errors` se descarta sin aviso en `from_params`, `build_conn_params` y `sanitize_for_connection`
  (como cualquier parámetro no declarado). Tabla del skill `drivers-connections-audit` actualizada.

## Notas para las fases W-8 de util_bbdd_web
- W-8.0: con `-W error::FutureWarning -W error::DeprecationWarning` no debería saltar nada de util_bbdd (los avisos de
  G30, G35, el setter y `encoding_errors` ya no existen).
- W-8.1: `ConnectionParamsManager.param_kinds("mariadb")` y `database_types.json` ya no traen `encoding_errors`.
- W-8.2: `from util_bbdd.results import CustomQueryResult`; `manager.execute_custom_result(sql, params,
  timeout=..., read_only=True, max_rows=limit + 1)`. En PostgreSQL, el plazo corta en el servidor y llega como
  `QueryTimeoutError` (mensaje del motor en `__cause__`). Oracle da los nombres de columna en mayúsculas.
- W-8.3: `get_server_version_info()` en los dos managers; Oracle 23ai `(23, 26, 3, 0, 0)` y `get_server_version()`
  `23.26.3.0.0`.

## Directrices para Futuras IAs
- **[metadata]**: el ejecutor de catálogo de los managers (`managers/_catalog_executor.py`) hace `rollback()` de la
  conexión cuando falla una consulta: no lanzar SQL de catálogo «a ver si funciona»; decidir antes (p. ej. por
  versión, como `full_server_version_sql(version)`).
- **[metadata]**: `server_version_sql()` la usan a la vez `ServerInfoCatalogDialect` y `VersionedCatalogDialect`
  (`_resolve_dialect`); debe funcionar en todas las versiones del servidor. Lo más detallado va en
  `FullServerVersionCatalogDialect`.
- **[executors]**: `execute_custom_result` reutiliza `_execute_custom` con `columns` (lista que rellena) y
  `server_timeout`; `execute_custom_many/one` no los pasan y no cambian. El plazo en el servidor solo existe con
  `read_only` (va dentro de su transacción, `SET LOCAL`).
- **[api]**: la raíz `util_bbdd` sigue con 13 símbolos; los tipos de resultado de los managers viven en
  `util_bbdd.results`.
- **[doc]**: `_LAST_AUTO_OUTPUT_BY_KEY` es de clase: en tests de nombres automáticos, `monkeypatch.setattr` con `{}`.
- **[herramientas]**: los scripts de edición con regex o con `` ` `` dentro de un heredoc de bash fallan o pierden
  barras: escribirlos en el scratchpad con Write y ejecutarlos con `python <ruta>`. `ruff format` puede reformatear un
  `return (...)` largo antes de la siguiente sustitución: releer antes de reemplazar.
- **[tests]**: tras cambiar un valor por defecto, buscar también los helpers de test que construyen el objeto con `**kwargs` (`Setup.run` de `test_dump_engines.py`): un `grep` de la llamada no los ve, y solo fallan con el banco.
- **[banco]**: contraseña común en `docker inspect util_bbdd_bench_postgres` (`POSTGRES_PASSWORD`); conexión directa
  con `user=bench`, SQL Server `sa` en 51833, Oracle `service_name=FREEPDB1`.

## Veredicto final
Veredicto: CLOSED (ola 8, v5.0.0)
Pendientes al cierre:
- Push de `develop`, tag `v5.0.0`, fast-forward de `main` y wheel + `.sha256` en GitHub Releases (propietario).
- Hacer W-8.0 … W-8.4 en util_bbdd_web y su `release: v1.7.0`.
- Condición 2 del veredicto de la ola 8: Oracle 11g real o simulado en el banco (aquí solo con un doble en unitarios).
- HSQLDB sin probar contra el servidor para `execute_custom_result` y `get_server_version_info` (las comprobaciones
  manuales no lo incluyeron; la integración de HSQLDB sí pasó).
