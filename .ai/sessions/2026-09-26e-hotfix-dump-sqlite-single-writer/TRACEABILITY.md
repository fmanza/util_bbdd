# TRACEABILITY

## Session metadata
- id: 2026-09-26e-hotfix-dump-sqlite-single-writer
- fecha: 2026-09-26
- rama: develop (base `4cf93d9`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-06 (MEDIA, resto) de `2026-09-25-performance-audit-dump`; roadmap `2026-09-25b-performance-audit-dump-delta`, paso 0.4 (la limpieza con `DELETE FROM` se corrigió en `cf0eafc`)

## Prompt issued
```
/hotfix PD-06 (resto): con destino SQLite, DumpOrchestrator no limita parallel_pk_ranges ni max_parallel_tables; SQLite
admite un solo escritor y la carga en paralelo pierde filas. Criterios: ranges4 en SQLite 3/3 success y verificación OK;
aviso en el log; test.
```

## RCA
- SQLite admite un solo escritor por base de datos. `_resolve_range_count` y `_resolve_max_workers` solo acotaban el paralelismo por la capacidad del pool, sin mirar el dialecto destino.
- **Reproducido** (`results_antes/`, `large`, PostgreSQL → SQLite, `parallel_pk_ranges=4`): `partición 3: (sqlite3.OperationalError) database is locked`; `order_items` en `error` con **1.500.000 de 2.000.000 filas** (las particiones que sí terminaron quedan confirmadas).

## FIX (mínimo)
- `dump/orchestrator.py`: `_single_writer_target(option, requested)` (nuevo) devuelve `True` y registra un WARNING si el destino es SQLite. `_resolve_range_count` y `_resolve_max_workers` devuelven 1 en ese caso. Con `max_parallel_tables > 1`, la rama paralela corre con un solo worker (secuencial); con 1 rango, la tabla se carga entera.
- `CHANGELOG.md` (`[Unreleased]` → *Fixed*).

## Validación
- **Tests** (`TestSqliteTargetSingleWriter`, 3):
  - resolución con destino SQLite → 1 y WARNING para las dos opciones (falla sin el arreglo);
  - otros destinos conservan lo pedido;
  - E2E SQLite → SQLite con `parallel_pk_ranges=4` y `max_parallel_tables=2`: todas las filas y `success`. **Pasa también sin el arreglo**: con 8.000 filas los escritores no llegan a chocar; es una guarda de resultado, no una reproducción (la reproducción es el banco `large`).
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy` limpio; `pytest tests/unit`: **4532 passed**.
- **Banco** (`results/`, `large`, `ranges4`, 3 repeticiones): **3/3 verificadas** (COUNT y SUM(PK) iguales, 3 tablas `success`, sonda de identidad OK). Tiempos 20,8 · 20,5 · 34,7 s (la tercera, ruido del entorno); la línea base secuencial es 21,3 s.

## AUDIT_CODE
- **Otros destinos**: sin cambio (el test lo cubre).
- **SQLite**: se pierde un paralelismo que no funcionaba; el WARNING dice qué opción se ignora.
- **Origen SQLite**: no aplica (el límite es del escritor); el origen SQLite no está soportado (PD-07).
- **Compatibilidad**: sin cambios de API; `DumpConfig` acepta los mismos valores.

## VERSION
- Commit: `fix(dump): cargar sin paralelismo con destino SQLite (PD-06)`
- Changelog: una entrada en `[Unreleased]` → *Fixed*.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump/sqlite]**: cualquier nueva fuente de paralelismo de escritura debe pasar por `_single_writer_target`.
- **[tests]**: un test pequeño de concurrencia en SQLite no reproduce `database is locked`; para eso hace falta volumen (banco `large`).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- PD-07 (origen SQLite).
