# TRACEABILITY

## Session metadata
- id: 2026-10-01-migrate-connect-by-3
- fecha: 2026-10-01
- rama: develop
- skill: new_feature (deuda de la 0.22.0: F2 `CONNECT_BY_ISCYCLE`, F3 `NOCYCLE` en MySQL/MariaDB/SQL Server, F1
  `ORDER SIBLINGS BY`)
- fase: PLAN + AUDIT_PLAN (GO_CONDICIONAL) → «F3: one membership helper per target instead, IMPLEMENT» → commits sin
  push

## Prompt issued
- «PLAN y AUDIT_PLAN» sobre `ORDER SIBLINGS BY`, `CONNECT_BY_ISCYCLE`, `NOCYCLE` en otros destinos y comentarios de
  rutinas → «F3: one membership helper per target instead, IMPLEMENT». Supuestos: se implementa el plan completo en el
  orden F2 → F3 → F1 → F4; SQL Server convierte `ORDER SIBLINGS BY` sin el orden y lo avisa (recomendación del plan,
  punto 3 sin respuesta). F4 (comentarios de rutinas) va en su propia sesión.

## Context supplied
- `src/util_bbdd/migrate/views/_rewrites.py`, `views/transpiler.py`, `tests/unit/migrate/test_view_connect_by.py`,
  `tests/integration/test_migrate_views_e2e.py`.
- Sondas de solo lectura en el banco (scratchpad `plan023_probes.py`): funciones de ventana prohibidas en la rama
  recursiva en MySQL (3575) y MariaDB (4008), permitidas en una CTE previa no recursiva en los 4 destinos; `CYCLE …
  RESTRICT` de MariaDB deduplica globalmente (diamante: 4 una vez; Oracle, dos); desbordar `CHAR(n)` en la ruta da
  error 1406 en MySQL/MariaDB.

## AI output summary
- **F2 `CONNECT_BY_ISCYCLE`**: semántica medida en Oracle (`f2_oracle_iscycle.py`): 1 si la fila tiene un hijo que la
  condición visitaría (con `AND LEVEL <= n`, dentro del nivel máximo) y que ya está en el camino, ella misma incluida
  (`Self` → 1; con `LEVEL <= 3`, Eva → 0 porque Ana estaría en el nivel 4). Implementado como espejo de ISLEAF:
  `_has_child(..., on_path)` + `_flag`; `_in_keys` (pertenencia positiva) y `_not_in_keys`. Sin `NOCYCLE` → sin
  reescribir («ORA-30930»). e2e: vista con ISCYCLE, fila `Self` y vista con `LEVEL <= 3`, parametrizado por destino
  (`NOCYCLE_TARGETS`) y clave.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| F2 | `src/util_bbdd/migrate/views/_rewrites.py`, tests, docs, CHANGELOG | completado |

## Directrices para Futuras IAs
- **[migrate/views/CONNECT BY]**: `CONNECT_BY_ISLEAF` y `CONNECT_BY_ISCYCLE` son la misma pregunta («¿hay un hijo
  visitable?») con el filtro de camino opuesto: `_has_child(on_path=None|False|True)`; la cota `LEVEL <= n` limita a
  ambos (un hijo más allá del nivel máximo no cuenta).

## Veredicto final
Veredicto: GO — en curso (F2 hecho; F3 y F1 pendientes).
