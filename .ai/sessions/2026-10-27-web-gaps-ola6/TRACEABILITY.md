# TRACEABILITY

## Session metadata
- id: 2026-10-27-web-gaps-ola6
- fecha: 2026-10-27
- rama: develop
- skill: new_feature + version-closure
- fase: IMPLEMENT + AUDIT_CODE + VERSION de la ola 6 (v4.6.0)

## Prompt issued
Ola 6 del plan de huecos de util_bbdd_web (catálogo, conexiones y explorador, util_bbdd 4.6.0): fases U-T1 … U-T8, un
commit por fase en `develop`; solo parámetros opcionales nuevos; sin romper `driver_info` (`default_driver` añadido,
lista de SQL Server conservada, G14); U-T3 antes que U-T5; G11 como `security` en MINOR (D2); anotar en el CHANGELOG lo
que la web necesita de cada fase. Plan canónico: `docs/plan/UTIL_BBDD_GAPS_PLAN.md` de util_bbdd_web (solo lectura).

## Context sources
- `src/util_bbdd/core/capabilities.py`, `_drivers/`, `data/database_types.json`, `connection/` (builder, params),
  `managers/`, `query/resolver.py`, `validators/`, `executors/`, `metadata/` (dialectos de catálogo, `CatalogSource`).
- util_bbdd_web: `backend/app/integrations/util_bbdd/catalog.py` (EngineCapabilities, `param_kind`, `KNOWN_PARAMS`,
  `OBSOLETE_DRIVERS`), `probe.py` (versión del servidor), `metadata.py` (schemas con `denormalize_name`) y `sql.py`
  (transacción de solo lectura y `fetchmany(limit + 1)`).

## AI output summary
- Un commit por fase (ruff, ruff format, mypy, pytest completo y `zensical build --strict` en cada una; AUDIT_CODE tras
  cada fase):
  - U-T1 `8c7c0b6e` G5, G10: `EngineCapabilities` + `get_engine_capabilities` (tabla en `core/capabilities.py`) y
    `DriverStatus` + `get_driver_status` (`_drivers/driver_status.py`, `find_spec`), reexportados en
    `util_bbdd.connection`.
  - U-T2 `500731dc` G8, G14: fuera `cx_Oracle`; `default_driver` en cada motor (`_config_loader.default_driver`; en SQL
    Server la opción `"default": true`); `get_db_type_driver_info`/`get_driver_requirements` ya no dan `{}` en SQL
    Server.
  - U-T3 `bdc97243` G12: `connection_params.kinds` en el JSON; `ConnectionParamsManager.param_kinds/param_kind`,
    `ParamKind`.
  - U-T4 `191e5ede` G15: `build_conn_params` conserva los opcionales declarados (salvo `None` y, con `dsn` en Oracle,
    el destino por partes).
  - U-T5 `328d1d97` G11 (`security`): `ConnectionParamsManager.redact_secrets` en `get_database_info()` de los dos
    managers.
  - U-T6 `5a6438d4` G13, G17: `ServerInfoCatalogDialect` (`server_version_sql`, `schema_names_sql`) en los 7
    dialectos; `CatalogSource`/`AsyncCatalogSource.ping/server_version/schema_names`; `ping()`,
    `get_server_version()`, `get_schema_names()` en los managers. La consulta de versión de Oracle reconoce 23.26.
  - U-T7 `76243151` G18 (`security`): `validators.base_validator.check_interpolated_params` en
    `QueryResolver.resolve`.
  - U-T8 `2deb0a21` G19, G20: `executors/_read_only.py`; `read_only` en `execute_custom_*` y `max_rows` en
    `execute_custom_many` (managers y ejecutores, sync y async).
- Evidencias: pytest 6791 passed, 614 skipped (`build/logs/U-T8_pytest.txt`); mypy limpio (355 ficheros);
  `zensical build --strict` limpio. Banco: U-T6 (`build/logs/U-T6_bench_check.txt`) y U-T8
  (`build/logs/U-T8_bench_check.txt`) en PostgreSQL, MySQL, MariaDB, SQL Server, Oracle y HSQLDB (`JAVA_HOME` jdk-25);
  integración completa (`-m integration`): 656 passed y los mismos 14 fallos/errores de entorno (`build/logs/ola6_integration.txt`).
- `scripts/gen_arquitectura_capas.py`: sin aristas nuevas (solo finales de línea, revertidos); 355 ficheros.
- VERSION: `release: v4.6.0`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Ola 6 | `core/capabilities.py`, `_drivers/driver_status.py` (nuevo), `_drivers/_config_loader.py`, `_drivers/validator.py`, `data/database_types.json`, `connection/params.py`, `connection/builder.py`, `managers/sync_mgr.py`, `managers/async_mgr.py`, `metadata/contracts.py`, `metadata/source.py`, `metadata/*/catalog.py`, `query/resolver.py`, `query/queries.py`, `validators/base_validator.py`, `executors/_read_only.py` (nuevo), `executors/sync_query_executor.py`, `executors/async_query_executor.py` | completado (v4.6.0) |
| Tests | `tests/unit/connection/test_engine_capability_matrix.py`, `test_param_kinds.py`, `test_build_conn_params_optionals.py`; `tests/unit/test_driver_info_default.py`, `test_database_info_secrets.py`, `test_manager_server_info.py`, `test_query_interpolation_security.py`, `test_custom_sql_read_only.py`; ajustados `test_architecture_metadata_rules.py` (excepción `PRAGMA query_only`), `test_snapshot_golden.py` y `test_oracle_11_catalog_detection.py` | completado |

## Desviaciones del plan
- U-T1: `core` es Foundation y no puede importar `migrate`, `connection`, `metadata` ni `dump`: la matriz es una tabla
  declarativa contrastada por test con cada fuente. Añade `documentation`, `compare` y `dump_constraints` a lo pedido.
  Las funciones se exponen en `util_bbdd.connection` (`core` y `_drivers` no son submódulos públicos).
- U-T2: el `default_driver` se calcula al cargar el JSON (`with_default_drivers`); en el JSON solo se marca la opción
  predeterminada de SQL Server.
- U-T3: `kind` va en un mapa `connection_params.kinds` (los `required` son cadenas y no admiten atributos).
- U-T6: el SQL va en los dialectos de catálogo (ADR-003), no en los managers; `ping()` devuelve segundos.
- U-T7: la «opción de bind» ya existía (`:nombre`/`%(nombre)s`); solo se documenta.
- U-T8: `max_rows` solo en `execute_custom_many`. SQL Server no tiene transacciones de solo lectura: se deshace.

## Notas para las fases W-T de util_bbdd_web
- W-T1: `from util_bbdd.connection import get_engine_capabilities, get_driver_status`; `drivers` ya no trae
  `cx_Oracle`; `default_driver` sustituye a `_driver_info()`. `get_engine_capabilities` es síncrona y barata (tabla).
- W-T2: `get_db_type_info_static(db)["connection_params"]["kinds"]` o `ConnectionParamsManager.param_kinds(db)`;
  las clases coinciden con `param_kind` de la web (`port` es nueva: hoy la web la trata como `plain`).
  `build_conn_params` ya conserva los opcionales: `build_params` sin la mezcla.
- W-T3: `manager.ping()` (segundos), `get_server_version()` (texto tal como lo da el servidor: PostgreSQL incluye la
  distribución, Oracle `23.0.0.0.0`) y `get_schema_names()`; el schema por defecto, `manager.metadata_source.current_schema()`.
- W-T4: `execute_custom_many(sql, params, read_only=True, max_rows=limit + 1)`; `read_only` empieza con un `rollback`
  de la conexión. En Oracle, una tabla recién creada da `ORA-01466` en solo lectura durante unos segundos.

## Directrices para Futuras IAs
- **[core]**: `ENGINE_CAPABILITIES` es declarativo; `test_engine_capability_matrix.py` lo compara con
  `MigrationPlanner`, `EngineReadinessAdvisor.SUPPORTED_DB_TYPES`, el registro de catálogo, `dump/_constraints` y la
  fábrica de SQLAlchemy. Un cambio de soporte en esas fuentes obliga a actualizar la tabla.
- **[data]**: `connection_params.kinds` cubre exactamente `allowed_keys` (test). Un parámetro nuevo en las configs de
  conexión necesita su entrada en `optional` y en `kinds`. `json.dump(indent=2, ensure_ascii=False)` reproduce el JSON
  tal cual: se puede editar por programa.
- **[metadata]**: `ServerInfoCatalogDialect` es opcional; `CatalogSource._resolve_dialect` solo trata como versionado
  al dialecto con `server_version_sql` **y** `for_server_version` (Oracle). No usar `%` literal en SQL de catálogo sin
  parámetros (pyformat).
- **[query]**: todo campo `{nombre}` de una plantilla se valida con `check_interpolated_params`; los valores van por
  bind. `QueryDefinition.required_params` sale de la plantilla: vacío/`None` lo rechaza antes el validador del motor.
- **[executors]**: `read_only` = `rollback` + prólogo (`READ_ONLY_PRELUDE`) + consulta + `rollback` + epílogo. El
  manager solo pasa `read_only`/`max_rows`/`db_type` al ejecutor si se piden (contratos de llamada en tests).
  `execute_custom_*` no confirma nada: una escritura con él no es una API soportada.
- **[tests]**: dos ficheros de test con el mismo nombre de módulo en carpetas distintas chocan en la recogida
  (`tests/unit/test_engine_capabilities.py` ya existía).
- **[banco]**: en un manager sin pool, `release_connection` cierra la única conexión. HSQLDB necesita
  `JAVA_HOME="C:/Program Files/Java/jdk-25"`. Los scripts de comprobación importables no deben ejecutar nada al
  importarse (`bench_params.py` aparte).
- **[herramientas]**: el clasificador de permisos falla a veces de forma transitoria; reintentar la misma acción.

## Veredicto final
Veredicto: CLOSED (ola 6, v4.6.0)
Pendientes al cierre:
- Push de `develop` y del tag `v4.6.0`, fast-forward de `main` y wheel + `.sha256` en GitHub Releases (propietario).
- Registrar la ola 6 en §6 del plan de util_bbdd_web y hacer W-6.0 y W-T1…W-T4.
- Vía async de `read_only`/`max_rows` probada solo con aiosqlite (faltan `asyncpg` y `aioodbc` en este venv).
- Ola 8 (5.0.0: `truncate_target=False`, `generar_sql=False` por defecto) fuera de este plan (D4).
