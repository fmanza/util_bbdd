# TRACEABILITY

## Session metadata
- id: 2026-10-09-feature-catalog-charset-mode
- fecha: 2026-10-09
- rama: develop
- skill: new_feature
- fase: FASE 4 de `drivers-connections-audit`, bloque CS: PLAN + AUDIT_PLAN (GO) + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```text
/new-feature

Objeto: drivers-connections-audit FASE 4 — bloque CS (catalog_charset_mode)
Funcionalidad: parámetro de conn_params `catalog_charset_mode: auto | native | convert` solo para mariadb y mysql, camino manager (sync AdaptiveCatalogExecutor y async AsyncManagerCatalogExecutor); default `auto` (comportamiento actual: diagnóstico → native/convert/failfast); `native` y `convert` omiten el diagnóstico (8 consultas)
Contexto: decision_matrix_phase_2.md § 6 (Q4, CS-1); D9 de audit_phase_2a.md; observación de B6: con schema vacío el diagnóstico da utf8mb4_mixed → convert
Fuera de alcance: SqlAlchemyCatalogExecutor (camino Engine), resto de motores
Versión: 0.38.0. Validar contra el banco. Commit + versión al cerrar.
```
Antes: push de `develop` y tags `v0.36.0`, `v0.36.1`, `v0.37.0` («si»). Aprobación de IMPLEMENT: «si».

## Context supplied
- `.github/prompts/new_feature.prompt.md`
- `.ai/sessions/2026-10-09-drivers-connections-audit-fase2/` (D9, Q4)

## AI output summary
- PLAN: `AdaptiveCatalogExecutor(mode=...)` ya existía, pero con `native`/`convert` seguía lanzando el diagnóstico (el modo solo se aplicaba en `select_strategy`, después).
- Test-first: `tests/unit/metadata/test_catalog_charset_mode.py` (17; 12 fallaban antes de implementar).
- `catalog_charset_mode` (campo de `MariaDBConnectionConfig`/`MySQLConnectionConfig`, `CATALOG_CHARSET_MODES`, validado y en minúsculas, fuera de `to_driver_kwargs`); entrada en `database_types.json` (mariadb, mysql).
- `AdaptiveCatalogExecutor`: con modo fijo no crea el detector (`diagnosis` queda en `None`); el guard de detección pasa a `strategy == "unknown"`.
- `ManagerCatalogExecutor`/`AsyncManagerCatalogExecutor`: kwarg `charset_mode`; los managers lo pasan desde `conn_params` validados.
- `ruff`/`mypy` OK; `pytest` 5383 passed, 497 skipped (`build/logs/feature_catalog_charset_mode_suite.txt`); `tests/integration` 552 passed, 10 skipped; `zensical build --strict` OK.
- Banco (`build/logs/feature_catalog_charset_mode_bench.txt`): tabla temporal con comentarios `ñandú €` / `código ñ €` en MariaDB 11.4 y MySQL 8.4; sync y async × `auto`/`native`/`convert`: 12 lecturas idénticas; `native`/`convert` sin diagnóstico; `auto` → `native` (schema con tablas: estado CLEAN). Tabla borrada al terminar.
- Docs: `docs/guides/connection_guide.md` § 6. Versión 0.38.0.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/connection/config.py`, `data/database_types.json` | modificados |
| IMPLEMENT | `src/util_bbdd/metadata/_adaptive_executor.py`, `managers/_catalog_executor.py`, `sync_mgr.py`, `async_mgr.py` | modificados |
| Tests | `tests/unit/metadata/test_catalog_charset_mode.py` | nuevo |
| Docs | `docs/guides/connection_guide.md` § 6 | |
| VERSION | ficheros de versión | 0.38.0 |

## Directrices para Futuras IAs
- **[charset/catálogo]**: la estrategia de lectura del catálogo MariaDB/MySQL se fija con `catalog_charset_mode`; `diagnosis is None` en `AdaptiveCatalogExecutor` significa «no diagnosticado» (modo fijo), no «pendiente»: el pendiente es `strategy == "unknown"`.
- **[charset/schema vacío]**: el `utf8mb4_mixed` de un schema sin tablas (`_test_read_comments` → `None`) no aparece con tablas; con datos reales el banco da CLEAN → `native`.
- **[banco/metadatos]**: `SchemaSnapshot.tables()` y `SchemaSnapshot.columns(tabla)` son métodos; para probar comentarios con caracteres no ASCII, crear una tabla temporal con `COMMENT` y borrarla en `finally`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Último bloque: B2 (TLS MariaDB), `/new-feature`, tras verificar que Connector/Python 1.1.14 y aiomysql aceptan `ssl_*`.
- Push y tag `v0.38.0` pendientes.
