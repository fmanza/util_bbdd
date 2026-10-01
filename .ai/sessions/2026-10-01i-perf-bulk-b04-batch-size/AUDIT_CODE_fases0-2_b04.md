# AUDIT_CODE — Fases 0–2 (v0.24.0) y B-04 (sin commit)

Solo lectura sobre el código. Verificaciones contra los servidores del banco y los drivers instalados (2026-10-01).

## PLAN

- **Alcance**: `git diff e80059e` en `src/` (commits `7b64aac` y `874dd82`, publicados en v0.24.0) + B-04 en el árbol de
  trabajo (`bulk/_support/batch_sizes.py`, `crud.py`, `parallel_loader.py`, `delete_strategies.py`) y
  `scripts/bench_bulk.py`. Foco no indicado: todo (bugs, casos límite, contratos, tipado, tests, seguridad).
- **Archivos**: `bulk/crud.py`, `bulk/_execution/{batch,delete_strategies,executors,insert_strategies,parallel_loader,
  session,staging_update}.py`, `bulk/_support/{retry,sql_helpers,batch_sizes}.py`, `metadata/postgresql/tables.py`,
  `metadata/sqlserver/common.py`, `scripts/bench_bulk.py`.

## AUDIT_PLAN

- **Funcionales**: estrategias nuevas que cambian la sentencia enviada (OPENJSON, staging PG, columnas → tuplas) frente
  a la semántica de la vía anterior con entradas fuera del dominio de la columna; reintentos por código con drivers no
  probados contra servidor; vías `*_from_chunks` dentro de una sesión ya abierta.
- **Técnicos**: libro de filas por operación, cadencia del DELETE entre chunks, lotes por operación (B-04).
- **Seguridad**: SQL construido con f-strings (identificadores y tipos) en OPENJSON, staging y DELETE.

## AUDIT_CODE

### A1 — CRÍTICA · CONFIRMADO · DELETE de SQL Server con OPENJSON borra filas que no se pidieron
`bulk/_execution/delete_strategies.py:254` (PK simple, `CAST([value] AS <tipo de la columna>)`) y `:265` (PK compuesta,
`OPENJSON … WITH (<col> <tipo> '$[i]')`). El valor JSON se convierte **al tipo de la columna** antes de comparar, y esa
conversión trunca, redondea o sustituye caracteres en silencio. La vía anterior (`IN` con parámetros) compara el valor
tal cual y no borra nada. Medido en SQL Server 2022 (pyodbc):

| Columna | Filas | Clave a borrar | `IN` (v0.23) | OPENJSON (v0.24.0) |
|---|---|---|---|---|
| `VARCHAR(5)` | `abcde`, `zz` | `abcdeXYZ` | no borra nada | **borra `abcde`** (truncado) |
| `NUMERIC(8,2)` | `1.11`, `2.00` | `1.105` | no borra nada | **borra `1.11`** (redondeo) |
| `VARCHAR(5)` | `?`, `a` | `α` | no borra nada | **borra `a`** (best-fit del code page) |
| `INT` | `1`, `2` | `2**40` | no borra nada | `DataError 22003` (antes, sin error) |
| PK `(INT, VARCHAR(5))` | `(1,'abcde')`, `(1,'zz')` | `(1,'abcdeXYZ')` | — | **borra `(1,'abcde')`** |

Afecta a la versión publicada v0.24.0 (pérdida de datos silenciosa con claves que no caben en el tipo de la PK).
**Remediación** (`/hotfix`, antes de cerrar 0.25.0): usar OPENJSON solo si todos los valores caben exactamente en el
tipo — `str`: longitud ≤ `length` y, en columnas no Unicode (`VARCHAR`), solo ASCII o codificables sin pérdida;
`Decimal`: exponente ≥ −`scale` y dígitos ≤ `precision`; `int`: dentro del rango del tipo (`TINYINT`…`BIGINT`) — y si no,
`SqlBasedDeleteStrategy`. Alternativa: tipo ancho en el `CAST` (`NVARCHAR(MAX)`, `DECIMAL(38, s)`), a costa de
conversiones implícitas en la columna (posible pérdida del index seek); medir.
**Tests**: los cinco casos de la tabla en integración (filas que deben quedar) y unitarios del filtro de valores.

### A2 — MEDIA · CONFIRMADO · Con el conector `mariadb`, el lock wait timeout ya no se reintenta (regresión de B-13)
`bulk/_support/retry.py:52-57`: si el error tiene `sqlstate` se decide como PostgreSQL y nunca se mira `errno`. Los
errores reales de `mariadb` (Connector/Python) llevan ambos: lock wait timeout → `sqlstate=HY000`, `errno=1205` →
`is_retriable` = **False** (verificado contra MariaDB 11.4; con PyMySQL, `args[0]=1205` → True). En v0.23.x era
`OperationalError` y se reintentaba. El deadlock 1213 se salva por su `sqlstate=40001`. El test
`test_mariadb_connector_errno_attribute` usa una `Exception` con solo `errno`, no la forma real.
**Remediación**: mirar `errno` (entero) antes que `sqlstate`, o decidir por `errno` si existe; test con un error real o
con ambos atributos.

### A3 — BAJA · CONFIRMADO (SQLite) / HIPÓTESIS (servidores) · `*_from_chunks` dentro de una sesión abierta
`bulk/crud.py:587` (`__stream_operation`) y `:500` (`bulk_insert_from_chunks`) abren su propia `bulk_session()` sin
comprobar `self._session.active`. Los docstrings lo prohíben, pero no hay guarda. En SQLite: `database is locked`
(verificado). En servidores, previsiblemente: segunda conexión con su propia transacción (lo del stream se confirma
aparte) y, al salir, `SessionScope.bind` deja `connection=None`, así que las operaciones siguientes de la sesión externa
dejan de ser atómicas. Previo a la Fase 2 en `bulk_insert_from_chunks`; las vías nuevas lo heredan.
**Remediación**: `RuntimeError` si `self._session.active` (o reutilizar la sesión abierta).

### A4 — BAJA · CONFIRMADO (código) · La nota de error atribuye al lote los fallos del commit periódico
`bulk/_execution/executors.py:160` (y el commit del DELETE): el commit periódico se ejecuta dentro del `with
batch_failure_note(...)` del lote que lo dispara; si falla el `COMMIT`, la nota dice «falló el lote N» y el lote se
había ejecutado bien. Puede llevar a buscar un dato erróneo en esas filas.
**Remediación**: sacar el commit periódico del ámbito de la nota o distinguirlo («falló el commit tras el lote N»).

### A5 — INFO · Tipado
`bulk/crud.py:611`: `# type: ignore[index]` porque `operation` es `str`; tiparlo como `Literal["INSERT", "UPDATE",
"DELETE"]` (o recibir `BulkOperation`) quita el ignore.

### Revisado sin hallazgo
- **Contratos públicos**: firmas existentes sin cambios; parámetros nuevos con default; alias `MySQLStagingUpdateStrategy`
  conservado; `BulkCrud.chunk_size` sigue siendo `int`. `chunk_size=None` (B-04) cambia un default (documentado; minor).
- **Libro por operación (R-3)**, cadencia del DELETE entre chunks, reanudación del loader (solo con cadencia y en
  reintentos), `_skip_rows` (cierra el lector), 2 reintentos mínimos solo en `update`/`delete` (idempotentes).
- **Staging PG**: privilegio comprobado antes (un CREATE fallido abortaría la transacción); CTAS evita `CREATE TYPE`;
  sin esquema en la temporal; `DROP` en el error.
- **B-04**: el ejecutor de INSERT/UPDATE recibe `max(insert, update)` y los bloques llegan ya del tamaño de su
  operación; cadencia y `chunk_size` explícito conservan el comportamiento anterior; `dump` pasa `chunk_size` explícito.
- **Seguridad**: los f-strings solo interpolan identificadores citados por `identifier_preparer` y tipos compilados por
  el dialecto; los valores van como parámetros (también el JSON de OPENJSON). Sin credenciales en logs ni notas.
- **Rendimiento**: sin regresiones medidas (banco final de v0.24.0 y validación de B-04).

### Tests faltantes
- A1: claves fuera del dominio de la PK (longitud, escala, code page, rango) en SQL Server, simple y compuesta.
- A2: clasificación con la forma real de los errores de `mariadb` (`sqlstate` + `errno`).
- A3: guarda de sesión abierta para las tres vías `*_from_chunks`.

**Veredicto: RECHAZADO** — A1 es una pérdida de datos silenciosa confirmada en una versión ya publicada (v0.24.0).
Condición para aprobar: `/hotfix` de A1 (y de A2, regresión) con sus tests antes de cerrar 0.25.0; A3–A5 pueden ir
en el mismo hotfix o como deuda.

## VERSION

- Commit propuesto para la corrección: `hotfix(bulk): DELETE de SQL Server con OPENJSON solo si las claves caben en el
  tipo de la PK; reintento del lock wait de mariadb` (y release `v0.24.1`, o dentro de `v0.25.0` con B-04).
- Pruebas sugeridas: las de «Tests faltantes»; repetir `tests/integration` con pyodbc y pymssql.
