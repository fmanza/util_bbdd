# PLAN + AUDIT_PLAN — desacoplar `ParallelBulkLoader` de `BulkCrud._tag_rejects`

- Base: `develop` (`97b595d`, v0.27.1 publicada). Origen: deuda técnica del `/audit-code` de la 0.27.0
  (`../2026-10-01z-fix-audit-v027/`): «`BulkCrud._tag_rejects` es un método privado que usa otra clase».

## Diagnóstico

| # | Hecho | Evidencia |
|---|---|---|
| E-1 | Acoplamiento: `ParallelBulkLoader._load_partition` llama a `crud._tag_rejects(index, resume_from)` antes de cada intento; `BulkCrud` guarda `_rejects_partition`/`_rejects_offset` y su `on_reject` los aplica. Único llamador. | `parallel_loader.py:605`; `crud.py:294-296, 735, 743, 771-778` |
| E-2 | **Bug (v0.27.0, Fase 3)**: con `disable_constraints=True` sin hoist (todos los motores salvo PostgreSQL/SQL Server), `_load_with_maintenance` carga la partición con un `bulk_insert_from_df` **por chunk** (no `bulk_insert_from_chunks`, que no admite una sesión abierta, A3). Cada chunk es una operación: la posición del rechazo es **relativa al chunk** y **`max_rejects` cuenta por chunk**. | Sonda (SQLite, 2 chunks de 3 filas, nulos en la 2.ª de cada uno): sin `disable_constraints` `filas=[1, 4]`; con él `filas=[1, 1]`; con `max_rejects=1` se rechazan 2 y la partición **no** falla |
| E-3 | El mismo problema lo tiene cualquier usuario que siga el consejo del `RuntimeError` de A3 («usa `bulk_*_from_df` por chunk dentro de la sesión»): posiciones por chunk y `max_rejects` por chunk. | mensaje de `__ensure_no_open_session` |
| E-4 | `dump` no está afectado: no pasa `disable_constraints` al loader (usa la vía por streams). | `dump/orchestrator.py::_bulk_options` |

Conclusión: el acoplamiento existe porque **falta en `BulkCrud` un concepto público**: «estas operaciones forman una
sola secuencia de entrada para los rechazos» (posición continua, un presupuesto de `max_rejects`, etiqueta de
partición). `_tag_rejects` lo resolvía a medias (solo el desplazamiento inicial y la partición, y solo para streams).

## Inputs (supuestos explícitos)
- **Objetivo**: eliminar el uso de miembros privados de `BulkCrud` desde `ParallelBulkLoader` y corregir E-2/E-3.
- **Módulos**: `bulk/crud.py`, `bulk/_execution/parallel_loader.py`, `bulk/_support/rejects.py` (si hace falta);
  tests `tests/unit/bulk/test_parallel_loader_isolate.py`, `tests/unit/bulk/test_on_error_isolate.py`; integración;
  docs `docs/api/bulk_crud.md`, `docs/api/bulk_parallel.md`; CHANGELOG.
- **API pública nueva**: context manager `BulkCrud.rejects_scope(*, partition: int | None = None, row_offset: int = 0)`.
- **Motores**: todos.

## PLAN
1. `BulkCrud.rejects_scope(*, partition=None, row_offset=0)` (context manager):
   - Dentro, todas las operaciones con aislamiento comparten **un** `Isolator` (un presupuesto de `max_rejects`) y la
     posición de los rechazos es continua: `row_offset` + filas de las operaciones anteriores del ámbito + posición
     dentro de la operación. `partition` va a la columna `particion` del CSV.
   - Un `*_from_chunks` dentro del ámbito es una operación más (su posición ya es la de la secuencia).
   - Sin `on_error="isolate"` no hace nada (el loader lo usa siempre sin preguntar).
   - Anidar ámbitos → `RuntimeError` (no tiene un significado claro).
2. `__isolating` reutiliza el aislador del ámbito si existe (como hoy dentro de un stream); al terminar cada operación
   (también si falla) el ámbito avanza el desplazamiento con las filas de la operación.
3. `ParallelBulkLoader`: cada intento va en `with crud.rejects_scope(partition=index, row_offset=resume_from):`; tanto la
   vía por streams como `_load_with_maintenance` quedan cubiertas (corrige E-2). Se eliminan `_tag_rejects`,
   `_rejects_partition`/`_rejects_offset` como estado suelto.
4. Docs: `rejects_scope` en `docs/api/bulk_crud.md` (con el ejemplo de chunks dentro de `bulk_session`, E-3);
   `docs/api/bulk_parallel.md` (posiciones y `max_rejects` por partición también con `disable_constraints`); CHANGELOG
   *Added* (`rejects_scope`) y *Fixed* (E-2).

## AUDIT_PLAN

### Riesgos y condiciones
- **R-1 Mezcla de tipos de cambio**: es una corrección (E-2) + una API nueva (`rejects_scope`) + el desacoplamiento. La
  regla del repo pide no mezclarlos salvo petición expresa (D-1). Hacerlo por separado obligaría a parchear E-2 con el
  mismo acoplamiento privado (o uno mayor: compartir el presupuesto entre operaciones) para quitarlo después.
- **R-2 Avance del desplazamiento**: debe contar las **posiciones de la entrada** de cada operación (`len(df)` o filas de
  la secuencia), incluidas las rechazadas, igual que `rows_committed`. Si una operación falla a mitad, el ámbito no
  continúa (el intento termina); no hace falta avanzarlo con precisión en el fallo.
- **R-3 `rows_rejected` y D-2 del loader**: siguen como hoy (`crud.rows_rejected` se acumula al cerrar cada operación;
  el loader compara antes y después del intento).
- **R-4 Notas de error (`batch_failure_note`)**: hoy, en `_load_with_maintenance` y al reanudar, dicen la posición dentro
  de la operación, no de la partición. Extender el ámbito a las notas sería coherente pero cambia su texto (D-2).
- **R-5 Compatibilidad**: método nuevo; nada cambia para quien no lo use. `_tag_rejects` era privado: quitarlo no rompe
  la API pública.
- **LSP/ISP/DIP**: el loader depende de un contrato público de `BulkCrud`, no de su estado interno.

### Tests
- Unit: `rejects_scope` con varios `bulk_insert_from_df` (posición continua con `row_offset`, `particion`, un
  presupuesto de `max_rejects` que corta en el segundo `from_df`), con un `*_from_chunks` dentro, anidado →
  `RuntimeError`, sin `isolate` → sin efecto; loader con `disable_constraints=True` en SQLite (la sonda de E-2 como test:
  `[1, 4]` y `max_rejects` por partición); los tests actuales de reanudación y D-2 sin cambios.
- Integración: el test paralelo de `isolate` con `disable_constraints=True` en los motores sin hoist (MySQL, MariaDB
  ×2 drivers, Oracle).
- Comprobación: `grep` sin `_tag_rejects` ni acceso a atributos privados de `BulkCrud` desde `parallel_loader.py`.

### Decisiones para el usuario
- **D-1 Alcance**: (a) **un solo cambio** (desacoplar + `rejects_scope` + corrección de E-2), commit `fix(bulk)` y
  versión **0.28.0** (API nueva) — recomendado; (b) primero `/hotfix` de E-2 con el diseño actual y luego el refactor.
- **D-2 Notas de error**: (a) **solo rechazos** en este cambio (las notas siguen por operación, como hoy) — recomendado
  para acotar; (b) las notas también con la posición del ámbito.
- **D-3 Nombre**: `rejects_scope` (recomendado, describe lo que agrupa) frente a `isolation_scope`.

**Veredicto: GO_CONDICIONAL** (condiciones: D-1, D-2, D-3)
