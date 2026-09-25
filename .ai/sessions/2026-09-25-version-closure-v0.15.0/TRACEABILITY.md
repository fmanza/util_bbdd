# TRACEABILITY

## Session metadata
- id: 2026-09-25-version-closure-v0.15.0
- fecha: 2026-09-25
- rama: develop
- skill: version_closure
- fase: VERSION

## Prompt issued
```
/version-closure
```
Interrumpido para terminar P-34/P-35 del roadmap de serialización SQL; después: "si, v0.15.0".

## Context supplied
- `git log v0.14.0..HEAD` (31 commits, hasta `d8df978`)
- `CHANGELOG.md` (`[Unreleased]`), `pyproject.toml`, `.ai/CURRENT_STATE.md`, `.github/instructions/sync.instructions.md`
- Cierre anterior: `.ai/sessions/2026-09-25-version-closure-v0.14.0/`

## AI output summary
- **Versión**: `0.15.0` (MINOR). En `[Unreleased]` hay API pública nueva (`audit_strict`, contadores de auditoría, hojas del Excel de `dump`) y un cambio incompatible (se retira `AuditTransaction`); en 0.x eso sube la menor. Propuesta aceptada por el usuario.
- **CHANGELOG**: `[Unreleased]` → `## [0.15.0] - 2026-09-25`, con introducción y "Cambios de comportamiento a revisar al actualizar" (6 puntos), y un `[Unreleased]` vacío encima. Secciones: Added (8), Changed (13), Fixed (15), Removed (1), Deprecated (1).
- **pyproject.toml**: `version = "0.15.0"`.
- **Commits**: `2b4391a` (release) y tag anotado `v0.15.0`; después, este commit `docs(ai)` con la sesión, `CURRENT_STATE`, `INDEX` y `SESSIONS_DIGEST`.
- **`.ai/CURRENT_STATE.md`**: cabecera, fila `v0.15.0` y cifras de tests.
- **Índices**: filas añadidas para `2026-09-25-performance-audit-bulk-sql`, `2026-09-25-hotfix-binary-sql-literals` y esta sesión.

## Release notes (resumen)
- **Changed**:
  - auditoría de `bulk` escrita al confirmarse el commit y descartada en rollback;
  - fail-open ante fallos del CSV (`audit_strict=True` para el comportamiento anterior);
  - escritura del CSV más barata (~290 → ~135 µs) y menos ruido de log;
  - `generar_sql` ~2,5× más rápido con el mismo SQL (1M filas SQLite: INSERT 12,6 → 4,9 s; UPDATE 13,0 → 5,4 s).
- **Added**:
  - `audit_strict` y contadores de auditoría en `BulkCrud`, `ParallelBulkLoader` y `dump`;
  - hojas «Auditoría Bulk» y «Secuencias PK» en el Excel de `dump`.
- **Fixed**:
  - literales binarios por motor en `generar_sql` (Oracle corrompía `b"abc"` sin avisar; SQLite, PostgreSQL y SQL Server no cargaban);
  - limpieza del destino SQLite en `dump`;
  - caché de lectura de auditoría;
  - `tiempo_seg` con `generar_sql`;
  - fórmulas en los Excel;
  - fidelidad de la auditoría en `ParallelBulkLoader`.
- **Removed**: `AuditTransaction` (incompatible).
- **Deprecated**: setter de `AuditManager.columnas_auditoria`.

## Impacto en API pública
- **Eliminado**: `AuditTransaction`, `AuditManager.iniciar_transaccion()`, `AuditManager.obtener_historial_transacciones()`.
- **Nuevo**:
  - `BulkCrud(audit_strict=False, warn_if_audit_disabled=True)` y propiedades `audit_failures`, `audited_rows`, `audit_uncommitted_records`, `unaudited_committed_rows`;
  - `ParallelBulkLoader(audit_strict=False)` y contadores en `PartitionResult` y `ParallelLoadResult`;
  - `DumpConfig.bulk_audit_strict` y contadores en `DumpAuditSummary`;
  - `AuditManager(warn_if_disabled=True)`;
  - `DumpReporter.generate(..., audit_summary=None, pk_sync_results=None)`.
- **Comportamiento**: ver "Cambios de comportamiento a revisar al actualizar" en el CHANGELOG.
- **Internos** (sin contrato público): `SqlColumns`, `dataframe_to_sql_columns`, `_BINARY_LITERAL_FORMATS`.

## Migraciones
- Obligatoria para quien use `AuditTransaction`: sustituirlo por `BulkCrud.bulk_session()` y consultar el CSV con `AuditManager.filtrar_por_rango_tiempo()` u `obtener_estadisticas()`.
- Recomendado:
  - regenerar los `.sql` con columnas binarias generados antes de esta versión para SQLite, PostgreSQL, SQL Server u Oracle;
  - revisar si se dependía de que un fallo del CSV de auditoría abortara la carga (usar `audit_strict=True`).

## Compatibilidad
- **Motores**: SQLite 3, PostgreSQL 17 (psycopg 3 y psycopg2), MySQL 8.4, MariaDB 11.4, SQL Server 2022 (pymssql, pyodbc), Oracle 23ai Free.
  - Los literales binarios de `generar_sql` se verificaron ejecutando el SQL en los 6.
  - Los tests de integración de binarios pasan en los 6 (14 passed, 0 skipped).
- **Python**: 3.12–3.14 (verificado en 3.14.2). SQLAlchemy 2.0.50, pandas 3.0.3 (con y sin pyarrow).
- **Límite conocido**: en Oracle, un literal binario no admite más de 2000 bytes (ORA-01704), igual que antes.

## Rollback
- Revertir la versión: `git tag -d v0.15.0` (tag local, no publicado) y `git revert 2b4391a` para el número de versión y el CHANGELOG.
- Revertir un cambio concreto: revertir su commit (`d8df978` P-34, `dde13b2` hotfix binarios, `e1adcc2` P-31/32/33, `1b072cf` retirada de `AuditTransaction`…).
- Riesgo: revertir `dde13b2` vuelve a generar literales binarios inválidos o corruptos.

## Checklist final
- [x] `ruff check src tests scripts` y `ruff format --check` sin cambios
- [x] `mypy src tests/unit/test_protocol_conformance.py` sin errores (342 ficheros)
- [x] `pytest`: 4938 passed, 165 skipped (servidores sin URL); integración de binarios con URLs: 14 passed, 0 skipped
- [x] `python -m build`: `util_bbdd-0.15.0.tar.gz` y `util_bbdd-0.15.0-py3-none-any.whl`
- [x] `pyproject.toml` en 0.15.0
- [x] CHANGELOG `[0.15.0]` sin entradas pendientes en `[Unreleased]`
- [x] `mkdocs build --strict` y `zensical build --strict` sin avisos
- [x] No hay `docs/CHANGELOG.md` ni `COMPATIBILITY.md` que sincronizar (no existen en el repo)

## Pruebas sugeridas tras publicar
- Suite completa con las URLs del banco (`scripts/bench_env.example.*`) en los 6 motores. En esta sesión solo se ejecutaron con URLs los tests de binarios.
- `scripts/bench_sqlgen.py --rows 1000000 --e2e` para confirmar las cifras en otra máquina.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| CHANGELOG | `CHANGELOG.md` (`[0.15.0] - 2026-09-25`) | cerrado |
| Versión | `pyproject.toml` (0.15.0) | actualizado |
| Tag | `v0.15.0` (anotado, local) | creado |
| Estado | `.ai/CURRENT_STATE.md` | actualizado |
| Índices | `.ai/sessions/INDEX.md`, `.ai/sessions/SESSIONS_DIGEST.md` | actualizados |

## Directrices para Futuras IAs
- **[versionado]**: en 0.x, una retirada de API pública (`AuditTransaction`) o una API nueva sube la versión menor (0.14 → 0.15), no la de parche.
- **[CHANGELOG]**: cada versión lleva introducción y una lista "Cambios de comportamiento a revisar al actualizar". Los ficheros `.sql` generados que haya que regenerar se indican ahí.
- **[cierre]**: se hace en dos commits (`release:` solo con CHANGELOG y `pyproject.toml`, más el tag anotado sobre él) y un `docs(ai)` posterior con la sesión, `CURRENT_STATE`, `INDEX` y `SESSIONS_DIGEST`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. Push hecho a petición del usuario: `develop` `6768d3f..5942105` y tag `v0.15.0` publicados en `origin`.
