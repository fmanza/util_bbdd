# TRACEABILITY

## Session metadata
- id: 2026-09-25-version-closure-v0.14.0
- fecha: 2026-09-25
- rama: develop
- skill: version_closure
- fase: VERSION

## Prompt issued
```
cierre de la 0.14.0
```
(Tras "¿Queda algo pendiente?", donde se propuso una 0.14.0 por los cambios de comportamiento acumulados en `[Unreleased]`.)

## Context supplied
- `git log v0.13.0..HEAD` (22 commits, incluido `19ef481` de otra sesión)
- `CHANGELOG.md` (`[Unreleased]`), `pyproject.toml`, `.ai/CURRENT_STATE.md`

## AI output summary
- **Versión**: `0.14.0` (MINOR) por los cambios de comportamiento observables: `chunk_size` inválido lanza `ValueError`, el DELETE respeta `commit_every_n_chunks`, `maintenance_scope` y `sync_pk_sequences` en Oracle, `docker-compose.yml`. Sin API pública nueva: `validate_chunk_size` es interno (`_execution`).
- **CHANGELOG**: `[Unreleased]` → `## [0.14.0] - 2026-09-25`, con introducción y "Cambios de comportamiento a revisar al actualizar".
  - Secciones: Added (1), Changed (8), Fixed (12), Removed (1).
  - Se añaden 2 commits que faltaban: `19ef481` (performance-audit de `dump`, de otra sesión; se indica que su banco es simulado y que la guía no está en la navegación) y `0deb039` (`.gitattributes`).
  - Se quita una cifra de tests desfasada y dos líneas en blanco sobrantes.
- **pyproject.toml**: `version = "0.14.0"`.
- **`.ai/CURRENT_STATE.md`**: cabecera, fila `v0.14.0` y cifras de tests.

## Release notes (resumen)
- **Fixed**:
  - auditoría de `bulk`, hallazgos 1–9: `chunk_size` sin validar; `maintenance_scope` ocultaba errores, no restauraba con `commit_every_n_chunks` y hacía commit implícito con `DISABLE KEYS` en InnoDB; `ParallelBulkLoader` retenía una conexión y no normalizaba el nombre; `sync_pk_sequences` con nombres citados y **Oracle identity (siempre fallaba)**; nombre de tabla sin sanear en `generar_sql`; DELETE sin cadencia de commit;
  - `PoolConnection.__del__` de Oracle;
  - 13 avisos de `mkdocs --strict`;
  - test de `matplotlib` siempre saltado.
- **Changed**:
  - contenedores del banco en `127.0.0.1`, con puertos configurables y base `bench` en SQL Server;
  - plantillas de URLs;
  - `docker-compose.yml` sobre el banco;
  - permisos de MariaDB;
  - `.gitattributes`;
  - tests por motor aplicable;
  - `pytest.ini` con avisos visibles.
- **Added**: entorno de performance-audit de `dump` (otra sesión).
- **Removed**: fixtures de `localhost:5432` con `DROP SCHEMA public CASCADE`.

## Impacto en API pública
- Sin cambios de firma. `DeleteStrategyResolver` y `DeleteBatchExecutor` (internos) aceptan `postgresql_strategy` y `commit_every_n_chunks`.
- Comportamiento: ver "Cambios de comportamiento a revisar al actualizar" en el CHANGELOG.

## Migraciones
- Ninguna obligatoria.
- Recomendado:
  - si se usó `sync_pk_sequences` con Oracle, volver a ejecutarlo: antes siempre terminaba en `error` y los contadores quedaban atrasados;
  - revisar código que pase `chunk_size` calculado, que ahora debe ser un entero ≥ 1;
  - quien levantara `postgres_db` con el `docker-compose.yml` del repo debe usar el suyo propio o `docker compose up -d --wait postgres` (puerto 55432).

## Compatibilidad
- Motores verificados con los 6 del banco: SQLite 3.50, PostgreSQL 17 (psycopg 3 y psycopg2), MySQL 8.4, MariaDB 11.4 (PyMySQL y `mariadb`), SQL Server 2022 (pymssql; pyodbc en pruebas previas), Oracle 23 Free.
- Python 3.12–3.14 (verificado en 3.14.2). Oracle: `sync_pk_sequences` exige 12c+, igual que antes.

## Rollback
- **Versión completa**: `git revert --no-commit v0.13.0..HEAD`, o `util_bbdd==0.13.0`. **Riesgo**: reaparecen `chunk_size` negativo sin error, errores ocultos en `maintenance_scope` y Oracle sin sincronización de PK.
- **Cambio concreto**: cada hallazgo tiene su commit (`git log --oneline v0.13.0..HEAD`).
- **Contenedores**: `git revert 2cb4256` restaura el `docker-compose.yml` anterior. Contenedores y volúmenes no se ven afectados.

## Checklist final
- [x] `ruff check src tests scripts`: sin errores
- [x] `mypy src tests/unit/test_protocol_conformance.py`: sin errores (341 ficheros)
- [x] `pytest`: 4783 passed / 160 skipped (sin URLs); 4943 passed / 0 skipped (URLs del banco); 0 avisos
- [x] `python -m build`: `util_bbdd-0.14.0` wheel y sdist
- [x] `pyproject.toml` 0.14.0
- [x] `CHANGELOG.md` actualizado
- [x] `mkdocs build --strict`: 0 avisos; `zensical build --strict`: sin problemas

## Pendientes fuera del código
- Push de `develop` y tag `v0.14.0` (a petición del usuario).
- GitHub Pages devuelve 404 (revisar `docs.yml` y Pages en Actions/Settings).
- `docs/PERFORMANCE_AUDIT_GUIDE.md` fuera de la navegación de `mkdocs.yml`, y `scripts/bench_dump.py` con la carga simulada (`TODO`). Ambos de la otra sesión.
- Contenedores del banco levantados; `postgres_db` sin uso por el proyecto.

## Directrices para Futuras IAs
- **[release]**: revisar siempre `git log vX..HEAD` frente a `[Unreleased]`. Pueden entrar commits de otras sesiones (aquí `19ef481`) o de configuración (`.gitattributes`) sin entrada en el CHANGELOG.
- **[repositorio compartido]**: en este repositorio puede trabajar otra sesión a la vez (commits y ficheros sin seguimiento ajenos). Mirar `git status` y `git log` antes de preparar commits y no incluir ficheros ajenos.

## Veredicto final
Veredicto: CLOSED (pendiente del commit `release: v0.14.0 …`, a petición del usuario)
