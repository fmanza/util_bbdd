# TRACEABILITY

## Session metadata
- id: 2026-09-24-refactor-p07-block-pipeline
- fecha: 2026-09-24
- rama: develop
- skill: refactor (memoria; sin cambios funcionales salvo el fichero sin restos si falla la generación)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Hago el commit y sigo con lo que queda de P-07 …?". Antes, commits `c3141fb` y `4232972` de P-06/P-29.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-07: doble materialización, pico 4,2× el DataFrame)
- `src/util_bbdd/bulk/crud.py` (`__run_bulk_pipeline`, `__prepare_*_operation`), `_support/persistence.py` (`persist_sql`), `_support/sql_helpers.py` (`wrap_identity_insert_sql`)

## AI output summary
- **Medición inicial** (`scratchpad/p07_mem.py`, SQLite, 200K filas, DataFrame de 18,5 MB, tracemalloc), picos de memoria adicional:
  - INSERT 70,6 MB (3,8×);
  - UPDATE 86,0 MB (4,7×);
  - con `generar_sql`: 163,7 MB (INSERT) y 175,7 MB (UPDATE). Registros + todas las líneas + la cadena unida.
- **Cambios** (`crud.py`):
  - `__record_blocks`: registros de `chunk_size` en `chunk_size` filas, el mismo lote del ejecutor, así que los lotes enviados a la BD no cambian.
  - `__blocks_transaction`: todos los bloques en una transacción. Usa la de `bulk_session` si ya está abierta; si no, abre una con `bulk_session()` (atómica, o commit-as-you-go con `commit_every_n_chunks`), igual que antes cuando todo iba en una llamada al ejecutor.
  - INSERT (normal, `OVERRIDING SYSTEM VALUE` e `IDENTITY_INSERT`) y UPDATE (directo o por staging, en `__execute_update_blocks`) ejecutan y generan SQL por bloques.
  - DELETE genera SQL por bloques; su ejecución ya iba por lotes.
  - `_PreparedBulkOperation.generate_sql_lines` pasa a devolver un iterable.
- **Otros ficheros**:
  - `persistence.persist_sql` escribe en streaming (`writelines` con separador `\n` y sin salto final, como `"\n".join` en modo texto) a `<fichero>.tmp`, que renombra al terminar y elimina si falla.
  - `sql_helpers.iter_identity_insert_sql`: generador; `wrap_identity_insert_sql` lo usa y conserva su contrato de lista.
- **Tests**:
  - `tests/unit/bulk/test_block_pipeline.py` (9):
    - conversión en bloques de 3/3/2 para INSERT y UPDATE;
    - fallo en un bloque posterior → nada guardado;
    - `commit_every_n_chunks=1` conserva los bloques confirmados y `rows_committed`;
    - `bulk_session` deshace INSERT y UPDATE por bloques;
    - fichero idéntico byte a byte con `chunk_size` 2 y 5000 (INSERT/UPDATE/DELETE);
    - sin fichero ni `.tmp` si la generación falla.
  - Con el código anterior fallan los 3 del comportamiento nuevo y pasan los 6 de lo que se conserva.
  - Tests existentes: 5 llamadas internas a `op.generate_sql_lines()` envueltas en `list()` (generador).
- **Resultado** (misma medición):
  - memoria adicional: INSERT 3,9 MB, UPDATE 6,5 MB, INSERT con `generar_sql` 3,6 MB, UPDATE con `generar_sql` 4,2 MB;
  - tiempo sin tracemalloc, dos pasadas alternas: antes 1,07–1,42 s, ahora 1,05–1,44 s.
- **Validación**:
  - `ruff check src tests` y `mypy src tests/unit/test_protocol_conformance.py` limpios;
  - suite 4710 passed / 177 skipped;
  - integración 6 motores 162 passed / 24 skipped (incluye staging con `chunk_size=2`).

## AUDIT_CODE
- Regresiones potenciales:
  - la conversión de un bloque ocurre ya dentro de la transacción: un error de normalización en un bloque posterior se produce tras escribir los anteriores. Sin `commit_every_n_chunks` se deshacen; con él, quedan los confirmados, que es la semántica documentada de esa opción;
  - el fichero SQL se escribe con un `.tmp` junto al destino.
- Edge cases:
  - DataFrame vacío: sin bloques; se abre y cierra una transacción vacía (antes, una llamada al ejecutor sin lotes);
  - `generate_sql_lines` se consume una vez.
- Compatibilidad: sin cambios de API pública; `wrap_identity_insert_sql` conserva su contrato.

## Directrices para Futuras IAs
- **[bulk/memoria]**: no volver a materializar todos los registros o líneas. Cualquier paso nuevo debe trabajar por bloque dentro de `__blocks_transaction`.
- **[bulk/transacciones]**: si una operación ejecuta varios bloques, deben ir en `__blocks_transaction`; varias llamadas sueltas al ejecutor abrirían una transacción cada una.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- Último del bloque: P-08 (medir primero).
