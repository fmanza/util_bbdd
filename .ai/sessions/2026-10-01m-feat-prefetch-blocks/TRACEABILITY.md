# TRACEABILITY

## Session metadata
- id: 2026-10-01m-feat-prefetch-blocks
- fecha: 2026-10-01
- rama: develop (base `d53834f`)
- skill: new-feature (PLAN + AUDIT_PLAN aprobados → IMPLEMENT → AUDIT_CODE → VERSION)

## Prompt issued
«Opciones nuevas» → PLAN/AUDIT_PLAN (`PLAN_AUDIT_PLAN.md`) → «Si».

## AI output summary
- `bulk/_support/prefetch.py` (nuevo): `prefetch(items, depth=2, *, thread_name)`, movido desde `dump/_source_reader.py`;
  `dump` conserva `_prefetch` (hilo `dump-prefetch`) llamándolo: sin cambios de comportamiento (280 tests de `dump`).
- `crud.py`: `BulkCrud(prefetch_blocks=False)`; `__prefetched` en las tres vías que consumen bloques (INSERT por registros
  y por columnas, UPDATE, chunks de `bulk_insert_from_chunks`), siempre dentro de `closing_iterable` (R-2).
- Tests: `tests/unit/bulk/test_prefetch_blocks.py` (6: equivalencia con/sin prefetch por registros y por columnas, los
  bloques se preparan en el hilo, nota de error y hilo cerrado tras fallo de envío, fallo de preparación con su tipo,
  default); integración `test_prefetch_blocks_gives_the_same_result` (6 motores). Mutación: sin `closing_iterable` el
  hilo queda vivo y el test falla.
- R-5: medición con la API final (`bench_prefetch.py`, 1M, 3 repeticiones): Oracle −2,2 % / +1,4 %, PostgreSQL −1,7 % /
  −1,1 %, SQLite +4,2 % / +1,2 % (todos con rangos solapados): sin efecto. El −18 % de Oracle de la auditoría era ruido.
  Con S-4: SQL Server −10,6 % / −6,2 %, MySQL −5,7 % / −2,2 %, MariaDB −5,6 % / −5,2 %.
- Docs: `docs/api/bulk_crud.md`, `docs/guides/benchmarks.md`, pie de `docs/architecture.md` (389 ficheros); CHANGELOG
  `[Unreleased]` → *Added*.

## AUDIT_CODE
- Sin hallazgos: el hilo solo prepara datos (no toca la BD ni el DataFrame del llamador); excepción del productor
  relanzada con su tipo; cierre determinista; default False (sin cambio para nadie).
- Capas: `dump → bulk/_support/prefetch` (dependencia existente); `gen_arquitectura_capas.py` sin cambios de dibujo.

## Validación
`ruff`/`mypy` limpios (389); `pytest` 5919 passed; `tests/integration` 461 passed (5 servidores); `zensical build
--strict` sin avisos.

## Directrices para Futuras IAs
- **[bulk/prefetch]**: el helper canónico es `bulk/_support/prefetch.py: prefetch`; `dump._source_reader._prefetch` es un
  envoltorio con el nombre de hilo `dump-prefetch` (los tests de `dump` lo buscan por nombre).
- **[bulk/prefetch]**: todo consumidor de un generador con prefetch debe usar `closing_iterable`; sin él, si el envío
  falla, el hilo sigue vivo hasta el GC (la traza de la excepción retiene el generador).

## Veredicto final
Veredicto: CLOSED
