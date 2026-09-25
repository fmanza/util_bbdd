# TRACEABILITY

## Session metadata
- id: 2026-09-25e-hotfix-bulk-reflect-fk-chain
- fecha: 2026-09-25
- rama: develop (base `3711944`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-08 (ALTA) de `2026-09-25-performance-audit-dump`; roadmap `2026-09-25b-performance-audit-dump-delta`, paso 0.7

## Prompt issued
```
/hotfix PD-08: BulkCrud.reflect_table (Table(..., autoload_with=engine) sin resolve_fks=False) refleja recursivamente las
tablas referenciadas por FK con un MetaData nuevo por llamada: coste cuadrático y RecursionError con ~150 tablas
encadenadas. Criterios: volcado de 200 tablas encadenadas sin RecursionError; reflexión de la cadena de 100 en PG < 5 s.
```

## RCA
- `BulkCrud.reflect_table` crea un `MetaData()` nuevo por llamada y refleja con `Table(..., autoload_with=engine)`. Por defecto SQLAlchemy también refleja cada tabla referenciada por FK, y las referenciadas por esas (`resolve_fks=True`).
- En una cadena `c000 ← c001 ← … ← cN`, reflejar `cN` refleja `N + 1` tablas: el volcado (una reflexión por tabla) hace O(N²) reflexiones, y la recursión de SQLAlchemy supera el límite de Python a partir de ~150 tablas encadenadas.
- `bulk` no usa FKs ni tablas referenciadas (verificado: sin usos de `foreign_keys`, `ForeignKey.column` ni `metadata.tables` en `src/util_bbdd/bulk/`); solo necesita columnas, PK e identidad de la propia tabla.
- **Cómo falla, por motor** (medido en esta sesión; corrige el matiz del informe original, que decía «aborta el volcado entero» en todos):
  - PostgreSQL: el `RecursionError` salta dentro de una consulta y SQLAlchemy lo envuelve como error de sentencia (`SQLAlchemyError`): el volcado sigue, pero **79 de 200 tablas quedan en `error`**.
  - SQL Server: el `RecursionError` llega sin envolver y **aborta el volcado entero** (tras 372 s).

## FIX (mínimo)
- `bulk/crud.py::reflect_table`: `resolve_fks=False` en las dos llamadas a `Table(...)`.
- `CHANGELOG.md` (`[Unreleased]` → *Fixed*, con aviso de cambio a revisar).

## Validación
- **Tests** (`tests/unit/bulk/test_reflect_fk_chain.py`, nuevo), los 2 fallan sin el arreglo (`git stash`):
  - `test_reflect_table_does_not_load_referenced_tables`: reflejar `t4` de una cadena de 5 deja solo `t4` en el `MetaData` (antes, las 5).
  - `test_dump_of_long_fk_chain_does_not_raise_recursion_error`: volcado SQLite de 200 tablas encadenadas: 200/200 `success` en 1,8 s (antes, `RecursionError` a los 20 s).
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src tests/unit/test_protocol_conformance.py` limpio; `pytest tests/unit`: **4504 passed**.
- **Servidores reales** (esquemas propios `zz_pd08_src`/`zz_pd08_dst`, 200 tablas encadenadas con 1 fila, borrados al terminar; script en el scratchpad de la sesión):

| Motor | Código | Reflexión de las 100 primeras | Volcado de las 200 |
|---|---|---|---|
| PostgreSQL | antes | 40,2 s · 39,5 s | 142,7 s · 134,3 s — **121/200** `success` (79 `RecursionError` envueltos) |
| PostgreSQL | con el arreglo | **1,3 s** | **7,9 s — 200/200** |
| SQL Server (pyodbc) | antes | 233,8 s | **`RecursionError` sin envolver: volcado abortado** tras 372 s |
| SQL Server (pyodbc) | con el arreglo | **3,3 s** | **16,7 s — 200/200** |

  Criterios: reflexión de 100 en PG < 5 s ✅ (1,3 s); 200 encadenadas sin `RecursionError` ✅ (PG, SQL Server y SQLite). Oracle no se re-midió (mismo mecanismo de SQLAlchemy; el informe original lo reprodujo con 200 tablas).

## AUDIT_CODE
- **Cambio visible en la API pública**: `reflect_table` es público. En la `Table` devuelta, `table.foreign_keys` sigue existiendo, pero `ForeignKey.column` ya no resuelve la tabla referenciada (no está en el `MetaData`) y lanza `NoReferencedTableError` si se accede. Nada en `util_bbdd` lo usa; queda en el CHANGELOG como cambio a revisar.
- **Sin efecto en SQL generado ni en ejecución**: INSERT/UPDATE/DELETE, `generar_sql`, identidad (`_get_identity_pk_cols`), PK sync y `restore_binary_values` solo usan columnas y PK de la propia tabla.
- **`dump`** sigue analizando las FKs con su propio `Inspector` (`_topological_sort`, `ConstraintManager`), que no depende de `reflect_table`.
- **Edge cases**: tablas con FK a sí mismas y ciclos: antes también se resolvían; ahora no se sigue ninguna referencia. Tablas sin FK: sin cambio.

## VERSION
- Commit: `fix(bulk): reflejar solo la tabla pedida, sin seguir las FK (PD-08)`
- Changelog: una entrada en `[Unreleased]` → *Fixed*.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[bulk]**: `reflect_table` refleja con `resolve_fks=False`. Si algún código de `bulk` necesitara navegar FKs, debe reflejar la tabla referenciada explícitamente, no volver a `resolve_fks=True` (coste cuadrático y `RecursionError`).
- **[bench]**: para pruebas con muchas tablas usa esquemas propios (`zz_*`) y bórralos; en SQL Server, borra antes las FK (`sys.foreign_keys`) o el orden de borrado falla. No crees tablas en `dump_src`/`dump_dst`.
- **[dump]**: un `RecursionError` en PostgreSQL llega envuelto por SQLAlchemy (error de tabla); en SQL Server llega sin envolver y aborta el volcado.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Resto de la Fase 0: PD-04, PD-05, PD-06 (SQLite con rangos), PD-07, PD-09.
