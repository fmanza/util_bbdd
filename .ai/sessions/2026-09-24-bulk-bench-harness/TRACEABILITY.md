# TRACEABILITY

## Session metadata
- id: 2026-09-24-bulk-bench-harness
- fecha: 2026-09-24
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
Fase 0: montar el banco de pruebas contra los 5 motores reales
```

## Context supplied
- Informe `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md`
- Ver `00_CONTEXT_SNAPSHOT.md`

## AI output summary
- **PLAN**: script `scripts/bench_bulk.py` + tests de integración + compose de 5 motores + guía. Inputs de `/new-feature` derivados del repo (URLs por variable de entorno según la convención existente `UTIL_BBDD_TEST_<MOTOR>_URL`).
- **AUDIT_PLAN**: GO.
  - Riesgo de DROP accidental: mitigado con nombre fijo `zz_util_bbdd_bench` y guarda en `reset_table`.
  - Import de `bulk._execution.batch`, un módulo privado, aceptado en un script.
  - `tracemalloc` opcional (`--memory`) porque distorsiona los tiempos.
  - URLs sin contraseña en la salida.
- **IMPLEMENT**:
  - `scripts/bench_bulk.py`: CLI; motor × variante × tamaño × repetición; verificación SQL por operación (COUNT y SUM con CAST a BIGINT); errores registrados sin detener el banco; variantes `baseline`, `p02-mysql-executemany`, `p01-mssql-engine-fast-executemany`; salida `summary.md`, `results.csv`, `environment.json`, `audit.csv`.
  - `docker-compose.bench.yml`: postgres:17, mysql:8.4, mariadb:11.4, mssql 2022, gvenzl/oracle-free:23-slim-faststart en puertos 5xxxx, con healthchecks; la contraseña se exige desde `UTIL_BBDD_BENCH_PASSWORD`.
  - `tests/integration/test_bulk_engines.py`: INSERT+UPDATE de 3000 filas (NaN/None → NULL, strip, auditoría), DELETE de 3000 PKs y DELETE con PK compuesta. En SQL Server, `xfail(strict=True)` por P-05.
  - `tests/unit/test_bench_bulk_script.py`: 25 tests (URLs, nombres, variantes, errores, verificación, resumen, CLI, ciclo completo en SQLite).
  - `docs/guides/benchmarks.md`: nueva subsección, verificación, filas de solución de problemas y aviso sobre las cifras de MySQL/SQL Server.
  - `.gitignore`: `bench_results/`. `CHANGELOG.md`: `[Unreleased]`.
- **Validación**:
  - `ruff check` limpio; `mypy src tests/unit/test_protocol_conformance.py scripts/bench_bulk.py` limpio.
  - `pytest`: 4457 passed / 19 skipped.
  - Banco ejecutado contra SQLite y contra PostgreSQL 18.3 real (contenedor `postgres_db`) a 1K/10K/100K: todas las operaciones verificadas OK, sin contraseña en la salida y tabla eliminada al terminar.
  - Tests de integración en verde contra ese mismo PostgreSQL (6 passed).
  - Página de docs renderizada: ancla, aviso, lista con tabla y bloques de código.
- **AUDIT_CODE**: ver abajo.
- MySQL, MariaDB, SQL Server y Oracle no ejecutados en la primera entrega (descarga de varios GB pendiente de decisión del usuario).
- **Incidente al levantar los contenedores** (tras "Levántalos"):
  - La primera versión de `docker-compose.bench.yml` no declaraba `name:`, así que compose usó el proyecto `util_bbdd` (el nombre del directorio), el mismo que `docker-compose.yml`. El servicio `postgres` coincidía, de modo que compose **recreó `postgres_db`** como `util_bbdd_bench_postgres` y le montó el volumen `util_bbdd_postgres_data`.
  - Ese contenedor (`postgres:17`) falló en `initdb` ("directory exists but is not empty") sin escribir nada. Se verificó que el volumen conservaba `pgdata` con `PG_VERSION=18`.
  - Remedio:
    - `name: util_bbdd_bench` en el compose.
    - Borrado solo de los contenedores del banco; el volumen con nombre no se tocó.
    - `postgres_db` recreado con `docker compose -f docker-compose.yml up -d postgres`.
    - Verificado: PostgreSQL 18.3 en el puerto 5432, `testdb` con sus 4 tablas.
  - Después se levantaron los 5 motores del banco como proyecto `util_bbdd_bench`, todos healthy.
- Tests de integración contra los 6 motores (PostgreSQL 17, MySQL 8.4, MariaDB 11.4, SQL Server 2022 vía pymssql, Oracle 23 Free, SQLite): **17 passed, 1 xfailed**. El `xfail` es el DELETE con PK compuesta en SQL Server, que confirma la parte de sintaxis de P-05. El DELETE de 3000 filas pasa con pymssql (el límite de 2100 parámetros solo aplica a pyodbc).

- **Línea base** (`python scripts/bench_bulk.py`, 1K/10K/100K × 3 repeticiones + 1M × 1): 240/240 mediciones verificadas (96 combinaciones), 0 errores. Archivada en `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` + `baseline/`.
  - Confirma P-02 (INSERT MySQL/MariaDB 1,85–2,05×) y P-04 (UPDATE 339–556 s por millón en MySQL/MariaDB/SQL Server).
  - Nuevo P-17: SQL Server + pymssql a ~2.700 filas/s en INSERT; `bulk_copy` 6,7× en prueba de 20K filas.
- **P-01 medido** (tras "P-01 sin medir, hazlo"; el usuario confirmó ODBC Driver 18 instalado y se verificó con `pyodbc.drivers()`):
  - Se llegó a construir una imagen Docker auxiliar con ODBC 18 como alternativa a tocar el host. Se retiró sin usarla al confirmarse el driver en Windows.
  - Banco `mssql+pyodbc`, `baseline` frente a `p01-mssql-engine-fast-executemany`, 1K–100K × 3 + 1M × 1: 33 mediciones correctas y 17 errores esperados.
  - INSERT 11,6–12,1× más rápido (1M: 245,5 s → 20,4 s).
- **Nuevo P-18 (CRÍTICA)**: `bulk_update_from_df` en SQL Server + pyodbc falla con `HY104 Invalid precision value` si la tabla tiene una columna DATETIME.
  - Bisección de columnas: solo influye DATETIME. Funciona con `enable_fast_executemany=False` o con `create_engine(fast_executemany=True)`.
  - `test_insert_and_update_roundtrip[mssql]` marcado `xfail(strict=True)` solo para pyodbc.
  - Integración con pyodbc: 15 passed, 3 xfailed. Con pymssql: 17 passed, 1 xfailed.
  - Guía `benchmarks.md`: fila de solución de problemas con el remedio temporal.

## AUDIT_CODE (resumen)
- Bugs corregidos durante la sesión:
  - `create_engine` fuera del `try` (un driver ausente tumbaba el banco).
  - Salida no ASCII en consolas cp1252 de Windows.
  - Posible desbordamiento de `SUM(INT)` en SQL Server.
- Edge cases:
  - Con `--ops update|delete` sin `insert`, los datos se cargan sin cronometrar.
  - Un paso que falla corta el ciclo (el estado siguiente sería incierto).
  - Motor inaccesible: queda como `error` en `environment.json` y el resto continúa.
- Seguridad: `render_as_string(hide_password=True)`; compose sin contraseña; guarda contra DROP de tablas ajenas.
- Tipado: mypy limpio (incluido el script).
- Deuda técnica:
  - Cada ejecución SQLite sin URL deja un directorio temporal (`tempfile.mkdtemp`).
  - P-03, P-04 y P-06 no tienen variante hasta que se implementen (no se pueden expresar sin tocar `src/`).
- Observación a verificar al ejecutar SQL Server: `BulkCrud` pasa a mayúsculas columnas y tabla en `mssql`. Una tabla con columnas en minúsculas podría no casar en `get_insert_columns` (comparación sensible a mayúsculas contra lo reflejado). El banco y los tests usan la convención de la librería, así que no lo detectan. **HIPÓTESIS**.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Banco de pruebas | `scripts/bench_bulk.py` | completado |
| Motores locales | `docker-compose.bench.yml` | completado (validado con `docker compose config`) |
| Tests de integración | `tests/integration/test_bulk_engines.py` | completado |
| Tests unitarios | `tests/unit/test_bench_bulk_script.py` | completado |
| Guía | `docs/guides/benchmarks.md` | actualizada |
| Changelog | `CHANGELOG.md` `[Unreleased]` | actualizado |

## Directrices para Futuras IAs
- **[bulk/bench]**: añade una variante A/B en `VARIANTS` de `scripts/bench_bulk.py` para cada hallazgo que implementes (P-03, P-04, P-06…), y compárala contra `baseline` en el mismo proceso antes de cambiar el comportamiento por defecto.
- **[bulk/bench]**: la verificación SQL de cada operación es parte del contrato del banco. Una variante más rápida pero incorrecta debe aparecer como error, no como mejora.
- **[tests/integration]**: los DELETE de SQL Server en `test_bulk_engines.py` son `xfail(strict=True)` por P-05. El `/hotfix` de P-05 debe retirar esas marcas (strict hará fallar la suite si pasan).
- **[docker]**: todo compose adicional en la raíz del repo debe declarar `name:` propio. Sin él comparte proyecto con `docker-compose.yml` y los servicios con el mismo nombre (`postgres`) reemplazan contenedores del usuario y heredan sus volúmenes.
- **[entorno]**: para medir P-01 hace falta el ODBC Driver 17/18 de Microsoft; el driver antiguo `SQL Server` de Windows no soporta `fast_executemany`.
- **[docs]**: `mkdocs build --strict` falla ya antes de esta sesión por `INSTALLATION.md`/`ROADMAP.md` en mayúsculas en git; no es una regresión de la guía de benchmarks.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit de los cambios (no realizado; pendiente de petición del usuario).
- Los contenedores `util_bbdd_bench_*` siguen levantados (`docker compose -f docker-compose.bench.yml down -v` para retirarlos).
