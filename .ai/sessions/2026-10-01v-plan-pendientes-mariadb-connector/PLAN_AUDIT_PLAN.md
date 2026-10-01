# PLAN + AUDIT_PLAN — pendientes tras v0.27.0 y driver original de MariaDB en las pruebas

- Base: `develop` (`36eb9c4`, v0.27.0 publicada).
- Petición: «PLAN y AUDIT-PLAN de lo pendiente. Necesito que se incluya en las pruebas el driver original de MariaDB».
- Driver original = **MariaDB Connector/Python** (paquete `mariadb` 1.1.14 instalado; SQLAlchemy `mariadb+mariadbconnector`).

## Diagnóstico (sondas sin cambios en el repo; scripts en el scratchpad de la sesión)

| # | Hecho | Evidencia |
|---|---|---|
| E-1 | **La librería usa el conector original como driver de MariaDB**: el engine factory construye `mariadb+mariadbconnector://` y `connection/mariadb/` (directa, pool, async, `UpdateAutoIncrement`) usa el módulo `mariadb`. | `factory/sqlalchemy_engine_factory.py:169`; `connection/mariadb/*.py` |
| E-2 | **El banco y la integración usan PyMySQL para MariaDB** (`UTIL_BBDD_TEST_MARIADB_URL=mariadb+pymysql://…`). El conector solo aparece en 2 tests puntuales de bulk (`test_bulk_engines.py:692`, `test_bulk_audit_20261001.py:446`) y como destino de `dump` (`mariadb_connector` en `test_dump_engines.py`). Es decir: **el driver por defecto de la librería para MariaDB es el menos probado**. | `scripts/bench_env.example.sh:20`; grep de `mariadbconnector` en `tests/` |
| E-3 | **No hay test end-to-end de managers con MariaDB** (sí con MySQL: `test_mysql_engine_e2e.py`). | `tests/integration/` |
| E-4 | Toda la integración con «mariadb» ejecutada con el conector (URL cambiada): **89 de 91 pasan** (bulk, `isolate`, staging, dump). Fallan 2 de `test_update_auto_increment_mariadb.py`. | sonda 1 |
| E-5 | Causa de E-4: el test lee `result.lastrowid` de un `INSERT` con `text()`; con `mariadbconnector` SQLAlchemy solo lo rellena en INSERT compilados (Core): `text` → `None`, Core → 2, cursor del driver → 3. **Fallo del test, no de la librería** (`src/` no usa `lastrowid`). | sonda `probe_lastrowid.py` |
| E-6 | Copia de `test_mysql_engine_e2e.py` con `db_type="mariadb"`: **managers sync/async, con y sin pool, inventario y `%` literales funcionan**; única diferencia: `get_columns()` devuelve el DEFAULT `'x'` (con comillas) en lugar de `x`. Es del **servidor** (MariaDB ≥ 10.2.7 guarda literales entre comillas en `information_schema.COLUMNS.COLUMN_DEFAULT`), no del driver. `migrate` ya lo resuelve por su cuenta (`column_default_hex`, `metadata/mariadb/_adapter_helpers.py:30`); `get_columns` lo devuelve tal cual. | sonda 2 |

## Pendientes heredados
- **ORA-03106** (oracledb 4.0.1 thin: UPDATE + bind LOB grande + fila mala + `batcherrors`): reportarlo a python-oracledb.
  Publicar en GitHub es una acción externa: la hace el usuario o con su confirmación explícita.
- **S-1 procesos**: NO_GO hasta un caso real ≥ 10M filas por tabla. Sin acción.

## PLAN

### Fase A — conector original de MariaDB en las pruebas (`test:`, sin cambios en `src/`)
1. `tests/integration/test_bulk_engines.py::_engine_params`: motor nuevo **`mariadb_connector`** (misma URL que
   `mariadb` con `mariadb+mariadbconnector`), presente si el paquete `mariadb` está instalado y la URL definida (patrón
   de `test_dump_engines.py`). Así **todos** los tests de bulk que hoy corren con MariaDB/PyMySQL (bulk, `isolate`,
   `ParallelBulkLoader`, staging, OPENJSON no aplica) corren también con el conector.
2. Revisar cada `only=`/`exclude=` con «mariadb» para incluir `mariadb_connector` donde aplique (p. ej. el UPDATE
   demasiado largo de `isolate`), y dejar los dos tests ad hoc que hoy crean su propio engine con el conector
   (`:692`, `:446`) parametrizados por el motor nuevo en lugar de duplicarlo.
3. **Nuevo `tests/integration/test_mariadb_engine_e2e.py`**: equivalente al de MySQL para `db_type="mariadb"`
   (Connector/Python): `SyncDatabaseManager` con y sin pool (catálogo, columnas, PK, únicas, FK, DDL de vista y tabla),
   inventario, `%` literales, `AsyncDatabaseManager` con y sin pool. El DEFAULT se comprueba como lo devuelve MariaDB
   (`'x'`) y se documenta la diferencia con MySQL (D-2).
4. `tests/integration/test_update_auto_increment_mariadb.py`: leer el siguiente id con `SELECT LAST_INSERT_ID()` (vale
   para ambos drivers) y parametrizar el engine por driver (PyMySQL y conector).
5. Docs: `docs/guides/benchmarks.md` § banco de pruebas (y `.ai/runtime.md`): con el paquete `mariadb` instalado, la
   integración de MariaDB se ejecuta con PyMySQL **y** con el conector original; nada que configurar.

### Fase B — banco de rendimiento (opcional, D-3)
- `scripts/bench_bulk.py`: motor `mariadb_connector` (misma URL); una medición 1M (INSERT/UPDATE/DELETE) para conocer
  el driver por defecto de la librería, que hoy no tiene cifras en `benchmarks.md`.

### Fase C — ORA-03106 (D-4)
- Reproducción mínima solo con `oracledb` (sin util_bbdd, ya existe la matriz en
  `2026-10-01r/s5_ora03106.py`), comprobada con la **última** versión publicada de python-oracledb antes de reportar;
  borrador del issue (versión, modo thin, servidor, pasos, esperado/obtenido) en la sesión. La publicación la decide el
  usuario.

## AUDIT_PLAN

### Riesgos y condiciones
- **R-1 Tiempo de la integración**: el motor nuevo duplica los tests de MariaDB (sonda: 91 tests en ~26 s); asumible.
- **R-2 Diferencias reales del conector**: E-4 indica que no hay; si al parametrizarlo de forma sistemática aparece un
  fallo de la librería (no del test), se para y se trata con `/hotfix` aparte, sin mezclarlo con esta sesión `test:`.
- **R-3 DEFAULT entre comillas** (E-6): normalizarlo en `get_columns` cambiaría la salida pública de los managers para
  MariaDB → decisión aparte (D-2), no se mezcla con tests.
- **R-4 Sin el paquete `mariadb`** (otra máquina/CI): los parámetros `mariadb_connector` se saltan con motivo explícito
  (`skipif`), como en `dump`.
- **R-5 Fase C**: no publicar nada externo sin confirmación; el borrador no contiene credenciales ni datos del banco.

### Tests
- F-A: `tests/integration` completo con el banco (5 servidores + conector) y sin URLs (los nuevos se saltan);
  `ruff`/`mypy`; mutación ligera: con el motor nuevo apuntando a PyMySQL por error, el test que comprueba
  `engine.dialect.driver == "mariadbconnector"` falla.
- F-B: la propia medición (3 repeticiones, como el resto del banco).

### Decisiones para el usuario
- **D-1 Cómo entra el conector en la integración de bulk**: (a) **motor `mariadb_connector` automático si el paquete
  está instalado** — recomendado (como `dump`); (b) solo con una variable de entorno opt-in.
- **D-2 DEFAULT entre comillas de MariaDB en `get_columns`**: (a) **el test fija el comportamiento actual y se
  documenta**; normalizarlo, si se quiere, en una sesión `/new-feature` aparte — recomendado; (b) normalizarlo ya.
- **D-3 Banco de rendimiento con el conector** (Fase B): (a) **sí** — recomendado (≈ 15 min de banco; hoy no hay cifras
  del driver por defecto); (b) no.
- **D-4 ORA-03106** (Fase C): (a) **preparar reproducción y borrador; publicas tú** — recomendado; (b) dejarlo.
- **D-5 Orden**: A → B → C, cada una en su sesión y commit.

**Veredicto: GO_CONDICIONAL** (condiciones: D-1 a D-5)
