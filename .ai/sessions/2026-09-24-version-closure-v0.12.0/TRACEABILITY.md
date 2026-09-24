# TRACEABILITY

## Session metadata
- id: 2026-09-24-version-closure-v0.12.0
- fecha: 2026-09-24
- rama: develop
- skill: version_closure
- fase: VERSION

## Prompt issued
```
/version-closure
```
(Tras recomendar el cierre de versión al terminar P-24. A mitad de sesión el usuario rechazó una edición del CHANGELOG hecha con un script de Python y pidió continuar: la misma corrección se rehízo con el editor.)

## Context supplied
- `CHANGELOG.md` (`[Unreleased]`), `pyproject.toml`, `.github/instructions/sync.instructions.md`, `.ai/CURRENT_STATE.md`
- `git log 166448a..HEAD` (commits desde la release `v0.11.0`)

## AI output summary
- **Versión objetivo**: `0.12.0` (MINOR). Hay API pública nueva (`BulkCrud(update_via_staging=...)`) y cambios de comportamiento sin rotura de firmas. No se pidió otra versión.
- **CHANGELOG**:
  - `[Unreleased]` pasa a `## [0.12.0] - 2026-09-24`, con introducción y lista de cambios de comportamiento a revisar al actualizar.
  - Secciones en orden Keep a Changelog: Added (5), Changed (4, fusionando un `### Changed` duplicado), Fixed (11), Known issues (1).
  - Añadidas 6 entradas de commits posteriores a `v0.11.0` que faltaban: `3abf4e0`, `b419745`, `3358060`+`f0f221f` (fixes de `bulk` previos a la auditoría) y `5811d43`+`7869c49` (comando y agente de performance-audit).
  - Corregida una entrada de `docs` desfasada ("ganancias en revisión").
  - Se dejan intactos los bloques `## [Unreleased]` antiguos que hay más abajo en el fichero (de versiones 0.3–0.7), ajenos a esta versión.
- **pyproject.toml**: `version = "0.12.0"` (`requires-python` sin cambios).
- **`.ai/CURRENT_STATE.md`**: cabecera, tabla de versiones (0.11.0 y 0.12.0 cerradas sin tag; Zenical pendiente sin versión) y cifra de tests.
- **Sincronización** (`sync.instructions.md`): no existen `docs/CHANGELOG.md`, `COMPATIBILITY.md` ni `.ai/COMPATIBILITY.md`, así que no aplican. `mkdocs.yml` sin páginas nuevas en esta versión.

## Release notes (resumen)
- **Fixed**: P-01/P-18 (SQL Server + pyodbc: fast_executemany real; UPDATE con DATETIME), P-05 (DELETE SQL Server), P-19 (JSON doble serializado), P-20 (`generar_sql` con JSON), P-21 (binarios UTF-8), P-22 (filas en tabla equivocada en MySQL/MariaDB), P-23 (`%` duplicados en el SQL generado), P-24 (nombre del fichero de `generar_sql`), y 3 fixes previos (case en MySQL/MariaDB, Update tratado como Insert, timestamp del CSV de auditoría).
- **Changed**:
  - P-02: INSERT MySQL/MariaDB + PyMySQL ~2×.
  - P-03: preparación de registros por columnas, 2,9×.
  - P-17: descartado; se recomienda pyodbc con un INFO en el log.
  - Documentación.
- **Added**:
  - P-04: `update_via_staging` (UPDATE MySQL/MariaDB ~12,5×, activo por defecto, con fallback y WARNING sin privilegio).
  - `scripts/bench_bulk.py`, `docker-compose.bench.yml` y tests de integración de `bulk` por motor.
  - Agente y comando de performance-audit.

## Impacto en API pública
- Nuevo parámetro `BulkCrud(update_via_staging: bool = True)`.
- Nuevo método `BatchStatementExecutor.execute(..., strategy=None)` y propiedad `insert_strategy`, ambos en el módulo interno `_execution`.
- Cambios de comportamiento observables:
  - UPDATE por tabla temporal en MySQL/MariaDB.
  - fast_executemany a nivel de dialecto en SQL Server + pyodbc.
  - INFO al detectar pymssql.
  - En SQLite, el fichero de `generar_sql` queda en `path_sql`.
- Sin eliminaciones ni deprecaciones.

## Migraciones
- Ninguna obligatoria.
- MySQL/MariaDB sin `CREATE TEMPORARY TABLES`: funciona (fallback con WARNING). Para silenciarlo, `update_via_staging=False` o conceder el privilegio.
- Recomendado revisar datos cargados con versiones anteriores en los casos de P-19, P-21, P-22 y P-23 (ver introducción de `[0.12.0]`).

## Compatibilidad
- Motores verificados: SQLite 3.50, PostgreSQL 17 (psycopg 3), MySQL 8.4 y MariaDB 11.4 (PyMySQL y `mariadbconnector`), SQL Server 2022 (pymssql 2.3 y pyodbc 5.3 + ODBC Driver 18), Oracle 23 Free (oracledb).
- Python 3.12–3.14 (verificado en 3.14.2 en este equipo; CI cubre 3.12–3.14).
- Dependencia nueva de facto: `pandas.core.dtypes.cast.maybe_box_native`, interno de pandas (P-03), cubierto por un test de equivalencia.

## Rollback
- **Volver a 0.11.0 completo**: `git revert --no-commit 3abf4e0^..HEAD` (o instalar `util_bbdd==0.11.0`). **Riesgo**: reaparecen fallos que corrompen datos (P-19, P-21, P-22, P-23).
- **Revertir solo el UPDATE por staging**: no hace falta revertir código; `BulkCrud(..., update_via_staging=False)` restaura el UPDATE fila a fila.
- **Revertir un cambio concreto**: cada hallazgo tiene su commit (`git log --oneline 166448a..HEAD`); los `docs(ai)` se pueden dejar.

## Checklist final
- [x] `ruff check src tests`: sin errores
- [x] `mypy src tests/unit/test_protocol_conformance.py`: sin errores
- [x] `pytest`: 4558 passed / 68 skipped (sin URLs de servidor)
- [x] `python -m build`: `util_bbdd-0.12.0` wheel y sdist
- [x] `pyproject.toml` a 0.12.0
- [x] `CHANGELOG.md` actualizado
- [~] `mkdocs build --strict`: 13 avisos, todos previos (`INSTALLATION.md`/`ROADMAP.md` en mayúsculas en git frente a `installation.md`/`roadmap.md` en nav y enlaces); ninguno nuevo

## Pruebas sugeridas antes de publicar
- `python -m pytest tests/integration/test_bulk_engines.py` con `UTIL_BBDD_TEST_<MOTOR>_URL` de los 6 motores (y SQL Server con pyodbc y pymssql).
- `python scripts/bench_bulk.py --sizes 100000 --repeat 3` para comparar con `02_BASELINE_MOTORES_REALES.md`.

## Directrices para Futuras IAs
- **[release]**: `0.11.0` y `0.12.0` se cerraron sin tag de git (el último tag es `v0.10.0`). Si se etiqueta, crear ambos tags o documentar el hueco.
- **[CHANGELOG]**: hay bloques `## [Unreleased]` antiguos más abajo del fichero (versiones 0.3–0.7). Al insertar entradas nuevas, ancla siempre en el primer `## [Unreleased]` o en la versión en curso, nunca buscando el encabezado sin más.
- **[bulk]**: las directrices técnicas de esta versión están en las `TRACEABILITY.md` de cada sesión 2026-09-23/24; las más importantes:
  - validar la generación de SQL ejecutando el fichero;
  - en comparaciones A/B, contar filas y comprobar que no fallaron las dos ramas;
  - no usar `bulk_copy` de pymssql;
  - añadir cada ruta tipada nueva a la corrección de JSON/binarios en `crud.py`.
- **[preferencia del usuario]**: rechazó una edición del CHANGELOG hecha con un script de Python y aceptó la misma hecha con el editor. Para ficheros de documentación prefiere ediciones visibles (Edit/Write).

## Veredicto final
Veredicto: CLOSED (pendiente del commit `release: v0.12.0 …`, a petición del usuario)
Pendientes al cierre:
- Commit de release; push (hay commits de `develop` sin publicar); decidir etiquetas de git.
- Retirar los contenedores del banco cuando ya no se necesiten (`docker compose -f docker-compose.bench.yml down -v`).
- Mejoras menores abiertas del informe: P-06, P-07, P-08, P-09, P-10, P-13; observación de SQLAlchemy (Known issues).
