# PLAN + AUDIT_PLAN — pendientes de `bulk` tras v0.26.0

- Base: `develop` (`6eb9392`, v0.26.0 publicada). Origen: «Pendientes» de `../2026-10-01o-fix-isolate-low-findings/`
  (VERSION) e informes S-1 y S-3 de `../2026-10-01l-plan-bulk-pending/`.
- Cada ítem que se apruebe se implementa en su propia sesión con su flujo (`/new-feature`, spike o `docs:`); sin mezclar.

## Inventario y estado verificado

| # | Pendiente | Estado verificado hoy | Evidencia |
|---|---|---|---|
| P-A | `on_error="isolate"` en `ParallelBulkLoader` | El bloqueo citado en S-2 («lock por ruta del CSV de rechazos») **ya no existe**: B-4 (v0.26.0) da a `RejectsWriter` el lock por ruta de la auditoría, que basta entre hilos de un proceso. Quedan tres problemas de diseño (abajo) | `bulk/_support/rejects.py`; `parallel_loader.py:539` crea una `BulkCrud` por partición sin `on_error` |
| P-B | `on_error="isolate"` en `dump` | Depende de P-A (`dump` usa `BulkCrud` y `ParallelBulkLoader` con `_bulk_options()`, `orchestrator.py:779`). El informe por tabla tiene `target_rows_after`; sin columna de rechazos | `dump/orchestrator.py:770-789`, `dump/_models.py:185` |
| P-C | `batcherrors` de Oracle | `oracledb` 4.0.1 tiene `Cursor.executemany(..., batcherrors=True)` y `getbatcherrors()`. En Oracle el INSERT va por `DefaultInsertStrategy` (executemany de SQLAlchemy, sin acceso a `batcherrors`). Hoy en Oracle: 10 filas malas 1,20×, y el valor demasiado largo (ORA-12899, `DatabaseError`) **no se aísla** | `insert_strategies.py:453-469`; `bench_isolate.log` de `2026-10-01n` |
| P-D | S-1: procesos en `ParallelBulkLoader` | NO_GO del 2026-10-01: a 1M filas el arranque de cada proceso (1,3–1,8 s en Windows) se come la ganancia; la fase de inserción sí escala en PostgreSQL (1,25 s con 4 procesos frente a 3,36 s con 4 hilos) | `S-1_processes.md` |
| P-E | S-3: `ClientRead` | **Cerrado en código**: causa confirmada (el pipeline de psycopg 3 no escala con hilos); la mitigación existe (`_staging_update_available`: sin `TEMP`, el UPDATE paralelo de PostgreSQL usa 1 hilo, `parallel_loader.py:461`). **Hueco de documentación**: no consta en `docs/` que el INSERT paralelo de PostgreSQL con psycopg 3 no gana con hilos (S-1: 3,46 s con 1 hilo, 3,36 s con 4) | `S-3_clientread.md`; búsqueda en `docs/` sin resultados |

## PLAN

### Fase 1 — documentación (P-E), `docs:`, sin cambios de código
- `docs/api/` de `ParallelBulkLoader` y `docs/guides/benchmarks.md` (tabla de palancas): en PostgreSQL con psycopg 3 el
  INSERT y el UPDATE paralelos no escalan con hilos (cliente limitado por el GIL en el pipeline); medidas de S-1/S-3;
  recomendación: `max_workers=1` con psycopg 3, o varios procesos por cuenta del usuario para cargas muy grandes.

### Fase 2 — spike S-5: `batcherrors` en Oracle (P-C), solo medición
- Prototipo de estrategia Oracle que envía el lote con el cursor del driver y `batcherrors=True`, y devuelve las filas
  erróneas (offset, error) sin reenviar nada. SQL y parámetros compilados por SQLAlchemy (`stmt.compile(dialect=…)`,
  procesadores de bind) para no perder las conversiones de tipo actuales.
- Medir con 1M filas (INSERT, UPDATE, DELETE): sin filas malas, con 10 malas y con ORA-12899; comparar con la bisección.
- Comprobar tipos: NUMBER/Decimal, VARCHAR2/NVARCHAR2, DATE/TIMESTAMP, CLOB, BLOB, NULL, JSON.
- Criterio GO: mismos datos que la bisección en todos los tipos, coste con 10 malas ≤ 1,05× y aislamiento de
  ORA-12899. Si GO, una sesión `/new-feature` aparte.

### Fase 3 — `ParallelBulkLoader(on_error, rejects_csv_path, max_rejects)` (P-A), `/new-feature`
1. Se pasan a cada `BulkCrud` de partición; `rejects_csv_path` compartido (lock B-4).
2. Partición en el CSV: columna nueva `particion` (D-1).
3. Reintentos: si el intento fallido escribió rechazos, no se reintenta y la partición queda con error explícito, como
   el PL-2 de la auditoría estricta (D-2).
4. `max_rejects` por partición (D-3).
5. `PartitionResult.rows_rejected` y `ParallelLoadResult.rows_rejected`; `rows` sigue contando posiciones (reanudación).

### Fase 4 — `DumpConfig(on_error, rejects_csv_path, max_rejects)` (P-B), `/new-feature`, tras la Fase 3
- `_bulk_options()` los pasa a `BulkCrud` y `ParallelBulkLoader`; `rows_rejected` por tabla en el resultado y en la
  hoja de resumen del Excel; las filas rechazadas explican la diferencia entre el origen y `target_rows_after`.

### P-D — S-1 procesos
- Sin implementación. Opcional (D-4): medir a 10M filas en PostgreSQL con lectores que lean solo su partición.

## AUDIT_PLAN

### Riesgos y condiciones
- **R-1 (P-A) Duplicados en el CSV por reintentos**: en modo atómico un fallo transitorio deshace la partición entera y
  el reintento vuelve a rechazar las mismas filas (los rechazos se escriben al detectarse, R-6 de S-2). Con cadencia,
  igual para lo no confirmado. Sin D-2, el CSV tendría filas repetidas.
- **R-2 (P-A) Formato del CSV**: añadir `particion` cambia la cabecera publicada hace horas en 0.26.0. B-4 ya aparta
  un fichero con otra cabecera, así que un CSV antiguo no se mezcla; en `BulkCrud` la columna queda vacía. Cambio de
  formato, no de API: CHANGELOG *Changed*.
- **R-3 (P-A) `max_rejects` global**: haría falta un contador compartido entre hilos y decidir qué partición falla
  primero (no determinista). Por partición es determinista y coherente con «una partición falla sin abortar las demás».
- **R-4 (P-B) `dump` desactiva constraints** (`maintenance_scope`, hoist en PG/SQL Server): entonces las FK no fallan y
  solo se aíslan PK duplicadas y tipos. Documentar.
- **R-5 (P-C) Conversión de tipos fuera de SQLAlchemy**: el cursor del driver no aplica los procesadores de bind de
  SQLAlchemy; si el prototipo no los reproduce, cambiarían datos (como la A1 de OPENJSON). Por eso es spike con
  verificación de tipos, no implementación directa.
- **R-6 (P-C) Qué errores rechazar**: `batcherrors` solo informa errores de fila (un error de sentencia hace fallar el
  `executemany` entero), así que todos son rechazables; con `max_rejects` superado en un lote hay que volver al
  SAVEPOINT del lote (las filas buenas ya aplicadas).
- **R-7 (P-D) Coste de medir a 10M**: generar 10M filas por proceso en el prototipo actual falsearía el arranque;
  hay que medir con lectores por partición (cambio del prototipo).
- **Sin cambios** con los valores por defecto en ningún ítem: `on_error="raise"` en `ParallelBulkLoader` y `dump`.

### Tests (por fase)
- F1: `zensical build --strict`.
- F2: el propio spike (equivalencia de datos por tipo frente a la bisección, 6 tipos + NULL; tiempos).
- F3: unit con SQLite (2–4 particiones, rechazos por partición, `particion` en el CSV, sin reintento si hubo rechazos,
  `max_rejects` por partición, resultados agregados); integración en 5 servidores.
- F4: unit de `DumpConfig` y del informe; integración de `dump` con filas que violan una PK del destino.

### Decisiones para el usuario
- **D-1 (P-A) Partición en el CSV**: (a) **columna nueva `particion`** (vacía en `BulkCrud`) — recomendado; (b) sin
  columna: la posición es relativa a la partición y no se sabe de cuál.
- **D-2 (P-A) Reintento con rechazos escritos**: (a) **no reintentar esa partición** (error explícito, como PL-2) —
  recomendado: simple, sin duplicados; (b) escribir los rechazos al confirmarse el commit (coherente con la BD, pero si
  el CSV falla después del commit las filas ya confirmadas quedan sin su rechazo escrito); (c) reintentar y aceptar
  duplicados con una columna `intento`.
- **D-3 (P-A) `max_rejects`**: (a) **por partición** — recomendado; (b) global para toda la carga.
- **D-4 (P-D) S-1**: (a) **mantener NO_GO** hasta que haya un caso real ≥ 10M filas por tabla — recomendado; (b)
  medir ahora a 10M (prototipo con lectores por partición, ≈ 1 h de banco).
- **D-5 Alcance y orden**: recomendado F1 → F2 → F3 → F4, cada una en su sesión, parando tras cada spike o
  AUDIT_PLAN propio.

**Veredicto: GO_CONDICIONAL** (condiciones: D-1 a D-5)
