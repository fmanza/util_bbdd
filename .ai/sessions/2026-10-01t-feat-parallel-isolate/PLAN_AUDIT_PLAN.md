# PLAN + AUDIT_PLAN — `ParallelBulkLoader(on_error="isolate", rejects_csv_path, max_rejects)` (Fase 3, P-A)

- Base: `develop` tras la sesión `2026-10-01s` (batcherrors de Oracle), que va antes porque cambia el `Isolator`.
- Origen: `../2026-10-01p-plan-bulk-pending-2/PLAN_AUDIT_PLAN.md` (P-A), decisiones aprobadas: D-1 columna `particion`,
  D-2 sin reintento si el intento escribió rechazos, D-3 `max_rejects` por partición.
- Flujo: `/new-feature`. Sin refactor.

## Inputs (supuestos explícitos)
- **Objetivo**: que las cargas paralelas (`load`, `update`, `delete`) aparten las filas con errores de datos a un CSV
  de rechazos común, como `BulkCrud(on_error="isolate")`, sin duplicados por reintentos.
- **Módulos**: `bulk/_execution/parallel_loader.py`, `bulk/_support/rejects.py` (columna `particion` y desplazamiento
  de reanudación), `bulk/crud.py` (enganche interno para etiquetar la partición); tests
  `tests/unit/bulk/test_parallel_loader_isolate.py` **(nuevo)** e integración; docs `docs/api/bulk_parallel.md`,
  `docs/api/bulk_crud.md` (columna nueva); CHANGELOG.
- **API pública**: `ParallelBulkLoader(..., on_error: Literal["raise", "isolate"] = "raise", rejects_csv_path:
  Path | None = None, max_rejects: int | None = None)`; `PartitionResult.rows_rejected: int = 0`;
  `ParallelLoadResult.rows_rejected` (propiedad, suma). **Cambio de formato** del CSV de rechazos: columna
  `particion` entre `operacion` y `fila` (vacía fuera de `ParallelBulkLoader`).
- **Motores**: todos (SQLite con `max_workers=1` en la práctica).

## PLAN
1. `rejects.py`: `REJECT_COLUMNS = (timestamp, tabla, operacion, particion, fila, error, valores)`. `RejectsWriter`
   recibe en `write` la partición (o `None`). Un CSV de la 0.26.0 (sin `particion`) se aparta solo por cabecera
   distinta (B-4).
2. `crud.py`: método interno `_tag_rejects(partition: int | None, offset: int = 0)` que el loader llama tras crear la
   `BulkCrud` de cada partición y antes de cada intento; el `on_reject` de `__isolating` escribe la partición y suma
   `offset` a la posición (las filas saltadas al reanudar, B-11). Sin cambios para `BulkCrud` usada directamente.
3. `parallel_loader.py`:
   - Constructor: mismos parámetros y validación que `BulkCrud` (ValueError en las mismas combinaciones, antes de lanzar
     hilos); se pasan a cada `BulkCrud` de partición; `rejects_csv_path` común (lock por ruta de B-4).
   - D-2: si un intento falla y `crud.rows_rejected` creció en ese intento, **no se reintenta**: la partición queda con
     error explícito («el CSV de rechazos contiene N filas de este intento; reintentar duplicaría»), como PL-2.
   - `_partition_result`: `rows_rejected=crud.rows_rejected`.
   - `max_rejects` por partición (D-3): cada `BulkCrud` lo aplica a su operación (un `*_from_chunks` es una operación).
4. Docs: parámetros, columna `particion`, sin reintento con rechazos, `max_rejects` por partición; CHANGELOG *Added*
   (loader) y *Changed* (columna).

## AUDIT_PLAN

### Riesgos y condiciones
- **R-1 Posición tras reanudar**: con `commit_every_n_chunks`, un reintento salta `crud.rows_committed` filas; sin el
  `offset` del paso 2, la posición de un rechazo posterior sería relativa a lo que queda. Test: fallo transitorio
  simulado sin rechazos en el primer intento y rechazo en el segundo → posición absoluta en la partición.
- **R-2 Duplicados**: cubierto por D-2. Coste: un fallo transitorio (deadlock, lock timeout) en una partición que ya
  rechazó filas deja esa partición sin reintentar; el usuario la relanza (las filas confirmadas, si hay cadencia, están
  en `rows`).
- **R-3 Cambio de formato** del CSV de rechazos publicado en 0.26.0 (horas antes). Mitigado por B-4 (se aparta, no se
  mezcla). *Changed* en CHANGELOG.
- **R-4 `max_rejects` por partición**: con N particiones el total puede llegar a N × `max_rejects`. Documentar.
- **R-5 Concurrencia del CSV**: varias particiones escriben a la vez; el lock por ruta de B-4 lo serializa (test de 4
  hilos ya existe para `RejectsWriter`); falta el de extremo a extremo con el loader.
- **R-6 batcherrors en hilos**: el colector de la sesión `2026-10-01s` es por hilo (`ContextVar`); test de integración
  Oracle con 2 particiones.
- **R-7 Auditoría**: cada `BulkCrud` ya audita filas aplicadas; `ParallelLoadResult.audited_rows + rows_rejected` debe
  cuadrar con las filas enviadas (sin fallos). Test.
- **R-8 Hoist de constraints** (`disable_constraints=True` en PG/SQL Server): las FK no fallan; se aíslan PK y tipos.
  Documentar.

### Tests
- Unit (SQLite, `max_workers` 1–2 por el escritor único): rechazos de varias particiones con su `particion` y posición;
  `update`/`delete`; sin reintento si hubo rechazos (y sí si no los hubo); posición con reanudación (R-1); `max_rejects`
  por partición; validación de parámetros; sumas de `rows_rejected` y auditoría; `on_error="raise"` sin cambios.
- Integración (5 servidores): `load` con PK duplicadas repartidas en 4 particiones; `update` con valor demasiado largo
  (PG/MySQL/MariaDB y Oracle tras 2026-10-01s); `delete` con FK.

### Decisiones
Ninguna abierta (D-1, D-2, D-3 aprobadas en `2026-10-01p`).

**Veredicto: GO**
