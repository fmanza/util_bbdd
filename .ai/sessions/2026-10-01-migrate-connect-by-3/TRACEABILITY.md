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

- Error propio: el commit de F2 (`5809023`) se encadenó tras `mypy` sin mirar su resultado y quedó con 2 errores de
  tipos; corregido en `4adadbd` (commit aparte, sin amend). Desde entonces el commit va condicionado a `mypy`.
- **F3 `NOCYCLE` en MySQL/MariaDB/SQL Server**: `_KeyPath` con `start`/`extend`/`contains`, uno por destino
  (`_KEY_PATHS`): `_ArrayKeyPath` (PostgreSQL, el de 0.22.0) y `_TextKeyPath` (texto `<sep>k1<sep>k2<sep>` con
  `CHAR(31)`, búsqueda `COALESCE(posición, 0) > 0` —SQL Server no admite `COALESCE` sobre una condición— y binaria:
  `CAST(... AS BINARY)` en MySQL/MariaDB, `COLLATE Latin1_General_BIN2` en SQL Server). Camino `CHAR(10000)` /
  `NVARCHAR(MAX)`.
  - e2e en los 4 destinos × 3 claves (12 casos). Con claves de texto, la primera versión fallaba en MySQL, MariaDB y
    SQL Server: diagnóstico (`f3_diag.py`): solo `CONNECT_BY_ISCYCLE` de la fila 'a' (hija de 'A') daba 1; la fila no
    se perdía (la búsqueda binaria funciona). Causa: la columna destino no distingue mayúsculas y `hijo.jefe_id =
    fila.id` trata 'A' = 'a' también en la condición CONNECT BY (collation del destino, no del camino). La prueba de
    mayúsculas pasa a una vista propia sin ISCYCLE/ISLEAF (`zzvw_ciclo_mayus`); se comprobó que falla si se quita la
    búsqueda binaria (monkeypatch de `_binary_text`).

- **F1 `ORDER SIBLINGS BY`**: R1 verificado antes de implementar: sqlglot traduce el orden de NULL de Oracle en una
  ventana (`CASE WHEN x IS NULL THEN 1 ELSE 0 END` en MySQL/SQL Server) si los nodos `Ordered` vienen del análisis
  Oracle, así que se copian tal cual a la ventana. CTE previa `connect_by_ranked` con `ROW_NUMBER() OVER (PARTITION BY
  <columna hija> ORDER BY <claves>)`; ancla con `ROW_NUMBER() OVER (ORDER BY <claves>)` sobre las raíces; `cb_order` =
  `CAST(1000000000 + n AS TEXT)` encadenado por nivel (`_order_step`), `TEXT` en PostgreSQL (VARCHAR(n) recortaría sin
  error) y `CHAR(10000)` en MySQL/MariaDB; consulta exterior `ORDER BY cb_order`. SQL Server: sin CTE previa ni orden,
  con aviso. Claves que no son columnas de la tabla o generador `FROM dual` → sin reescribir.
  - Tests: `TestOrderSiblings` (SQLite **sin ordenar**: ASC, DESC, por id, con WHERE), e2e `test_oracle_order_siblings`
    en los 4 destinos (orden de llegada en PostgreSQL/MySQL/MariaDB, NULL entre hermanos); se comprobó que falla con un
    `cb_order` constante.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| F2 | `src/util_bbdd/migrate/views/_rewrites.py`, tests, docs, CHANGELOG | completado |
| F3 | `src/util_bbdd/migrate/views/{_rewrites,transpiler}.py`, tests, docs, CHANGELOG | completado |
| F1 | `src/util_bbdd/migrate/views/{_rewrites,transpiler}.py`, tests, docs, CHANGELOG | completado |

## Directrices para Futuras IAs
- **[migrate/views/CONNECT BY]**: `CONNECT_BY_ISLEAF` y `CONNECT_BY_ISCYCLE` son la misma pregunta («¿hay un hijo
  visitable?») con el filtro de camino opuesto: `_has_child(on_path=None|False|True)`; la cota `LEVEL <= n` limita a
  ambos (un hijo más allá del nivel máximo no cuenta).
- **[migrate/views/CONNECT BY]**: todo lo que depende del camino de `NOCYCLE` pasa por `_KEY_PATHS[destino]`
  (`start`/`extend`/`contains`); un destino nuevo solo añade una entrada.
- **[migrate/views/CONNECT BY]**: la collation de las columnas destino decide la igualdad de claves de texto en la
  propia condición CONNECT BY: con claves que solo difieren en mayúsculas, solo una collation binaria reproduce Oracle.
  No es un defecto del camino; se documenta.
- **[migrate/views/CONNECT BY]**: las funciones de ventana van en una CTE previa no recursiva, nunca en la rama
  recursiva (MySQL 3575, MariaDB 4008). Para traducir el orden de NULL de Oracle, reutilizar los nodos `Ordered` del
  análisis Oracle (llevan `nulls_first`), no construir nodos nuevos.
- **[tests/e2e]**: para validar un orden, comparar las filas en el orden de llegada (`_rows_in_order`), no con `_rows`
  (que ordena), y comprobar que el test falla si se rompe el orden a propósito.

## Veredicto final
Veredicto: CLOSED — F2, F3 y F1 implementados y verificados contra Oracle; liberado en v0.23.0 (2026-10-01).
