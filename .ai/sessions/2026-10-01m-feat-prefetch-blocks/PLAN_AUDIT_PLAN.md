# PLAN + AUDIT_PLAN — `BulkCrud(prefetch_blocks=...)` (S-4)

- Base: `develop` (`d53834f`; P-1 sin publicar). Origen: `../2026-10-01l-plan-bulk-pending/S-4_prefetch.md`.
- Flujo: `/new-feature`. Política: sin refactor salvo el movimiento mínimo del helper (ver R-1).

## Inputs (supuestos explícitos)
- **Objetivo**: preparar el bloque N+1 (conversión a registros o columnas) en un hilo, con una cola de 2 bloques,
  mientras se envía el bloque N. Opt-in.
- **Módulos**: `src/util_bbdd/bulk/crud.py`; `src/util_bbdd/bulk/_support/prefetch.py` **(nuevo)**;
  `src/util_bbdd/dump/_source_reader.py` (importa el helper movido); tests `tests/unit/bulk/test_prefetch_blocks.py`
  **(nuevo)**; docs `docs/api/bulk_crud.md`, `docs/guides/benchmarks.md`.
- **API pública**: `BulkCrud(..., prefetch_blocks: bool = False)`. Sin cambios en `ParallelBulkLoader` ni en `dump`.
- **Contrato de entrada**: igual que hoy. **Salida**: idéntica (mismas filas, mismo orden de lotes, mismas notas de
  error, misma auditoría); solo cambia el solape entre preparación y envío.
- **Reglas**: sin cambio de resultados; el hilo lector nunca toca la BD; se cierra siempre (también si falla el envío).
- **Restricciones**: sin dependencias nuevas; solo sync.
- **Motores**: todos; medido: SQL Server INSERT −10,6 %, UPDATE −6,2 %; MySQL −5,7 % / −2,2 %; MariaDB −5,6 % / −5,2 %;
  Oracle −18 % (empeora, una medición de la auditoría); PostgreSQL/SQLite sin repetir.
- **Migraciones**: no.

## PLAN
1. Mover `_prefetch` y `_enqueue_prefetch` de `dump/_source_reader.py` a `bulk/_support/prefetch.py` (como
   `prefetch(items, depth=2)`); `dump/_source_reader.py` los importa con los nombres actuales (los tests de `dump`
   parchean `util_bbdd.dump.orchestrator._prefetch`: el nombre sigue existiendo).
2. `crud.py`: `self._prefetch_blocks`; un método `__blocks(generator)` que devuelve el generador tal cual o envuelto en
   `prefetch`. Se aplica a las tres vías de ejecución que consumen bloques: INSERT (`execute_blocks`, registros y
   columnas), UPDATE (`blocks()` de `__prepare_update_operation`) y los bloques de cada chunk de
   `bulk_insert_from_chunks`. No a `generar_sql` ni al DELETE (su ejecutor trocea el DataFrame sin preparación cara).
3. Cada consumidor recorre los bloques dentro de `closing_iterable(...)`: si el envío falla, se cierra el generador y
   `prefetch` hace `join` del hilo (lección A1/A2 de `dump`).
4. Docstring, docs y CHANGELOG (*Added*): opt-in; mejora medida y advertencia de Oracle.

## AUDIT_PLAN
- **R-1 Dependencia `bulk → dump`**: `bulk` no puede importar de `dump` (capas, `docs/architecture.md`). Mover el helper a
  `bulk/_support/` es el cambio mínimo correcto (`dump → bulk` ya existe). Verificar con `gen_arquitectura_capas.py`.
- **R-2 Hilo vivo tras un fallo**: un `for` no cierra el generador si el cuerpo lanza; sin `closing_iterable` el hilo
  seguiría preparando bloques hasta el GC. Test: envío que falla en el lote 1 → el hilo de prefetch terminó al salir.
- **R-3 Excepción del productor**: un fallo al preparar (p. ej. tipo no convertible) debe llegar al consumidor en el
  mismo lote y con su tipo; `prefetch` ya la relanza tras entregar los bloques anteriores. Test.
- **R-4 Concurrencia sobre el DataFrame**: el hilo solo lee (`iloc` + conversión); el consumidor no muta el DataFrame
  de trabajo durante el envío. pandas permite lecturas concurrentes. Sin riesgo de datos.
- **R-5 Oracle**: no se fuerza ni se bloquea; se documenta que empeoró en la única medición. Repetir la medición en
  Oracle en esta sesión (3 repeticiones) y, si empeora, documentarlo como «no recomendado».
- **R-6 `ParallelBulkLoader`**: no se expone (duplicaría hilos: workers × 2); queda fuera.
- **Seguridad**: sin superficie nueva.
- **Simplificación**: no se añade `depth` configurable (2 fijo, el mismo que `dump`).
- **Tests**: equivalencia de resultados con y sin prefetch (INSERT por registros y por columnas, UPDATE con y sin
  staging, `bulk_insert_from_chunks`), nota de error con la misma posición, R-2 y R-3; integración en los 5 servidores
  (parametrizar un test de ida y vuelta con `prefetch_blocks=True`).

**Veredicto: GO**
