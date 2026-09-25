# TRACEABILITY

## Session metadata
- id: 2026-09-26i-refactor-dump-stream-results
- fecha: 2026-09-26
- rama: develop (base `a4ee464`)
- skill: refactor (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION); mejora de memoria sin cambio funcional
- origen: Q2 / paso 1.2 del roadmap `2026-09-25b-performance-audit-dump-delta` (PF-02 de la auditoría `2026-09-25-performance-audit-dump`)

## Prompt issued
```
/refactor Q2: cursor de servidor (stream_results) en las lecturas de dump en PostgreSQL, MySQL y MariaDB. psycopg y
PyMySQL descargan el resultado entero antes del primer fetchmany (memoria pico proporcional a la tabla mayor). Sin
cambios de API ni de resultado; no en el engine del usuario; A/B intercalado en PG, MySQL y MariaDB; comprobar ranges4.
```

## PLAN / AUDIT_PLAN
- `stream_results=True` y `max_row_buffer=chunk_size` como opciones de ejecución **de la sentencia de lectura** (`text(sql).execution_options(...)`), no del engine.
- Solo PostgreSQL, MySQL y MariaDB (`_CLIENT_CURSOR_DIALECTS`); SQL Server y Oracle ya leen en streaming.
- Restricciones técnicas comprobadas: el cursor de servidor ocupa su conexión hasta terminar (cada lectura de `dump` tiene la suya; la consulta MIN/MAX de los rangos usa otra); el cursor con nombre de PostgreSQL necesita transacción (SQLAlchemy la abre sola).
- Riesgo residual: si la escritura falla a mitad en MySQL/MariaDB, cerrar la conexión drena las filas pendientes (PyMySQL); solo afecta al camino de error.

## IMPLEMENT
- `dump/orchestrator.py::_execute_read`: rama nueva para `_CLIENT_CURSOR_DIALECTS`. Punto único: cubre la carga de tabla entera y los lectores de rangos.

## Validación
- **Tests** (`tests/unit/dump/test_dump_fidelity.py::TestServerSideCursor`, 4): la sentencia lleva `stream_results` y `max_row_buffer=chunk_size` en PostgreSQL, MySQL y MariaDB (y conserva los parámetros); SQL Server no.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src` limpio; `pytest tests/unit`: **4544 passed**.
- **A/B intercalado** (`large`, 3,5M filas, 2 repeticiones por lado; `ab_antes/`, `ab_despues/`):

| Motor | RSS pico | Total | `read` | Verificación / identidad / PK sync |
|---|---|---|---|---|
| PostgreSQL | 414 → **167 MB** (−60 %) | 16,0 · 15,9 → 16,7 · 17,3 s (**+6,6 %**) | 3,3 → 4,2 s | 4/4 |
| MySQL | 858 → **159 MB** (−81 %) | 54,4 · 52,4 → 53,7 · 52,9 s (−0,2 %) | 18,2 → 18,7 s | 4/4 |
| MariaDB | 858 → **159 MB** (−81 %) | 50,3 · 48,4 → 49,9 · 48,5 s (−0,3 %) | 18,1 → 18,8 s | 4/4 |
| PostgreSQL `ranges4` | 188 MB | 12,0 s (12,3 s sin Q2) | — | verificado, identidad OK, 3 × `synced` |

- **Coste aceptado en PostgreSQL**: +1 s (+6,6 %), por encima de la tolerancia del roadmap (5 %). Causa: el cursor de servidor hace un `FETCH` por chunk (5000 filas) en lugar de descargar la tabla de una vez. Se acepta porque el objetivo de Q2 es acotar la memoria (el camino anterior es O(tabla mayor) y puede agotar la memoria con decenas de millones de filas) y porque Q3 (solape lectura/escritura) necesita este cursor y oculta el tiempo de lectura (la auditoría midió −36 % en PostgreSQL con ambos).
- **`ranges4` + cursor de servidor en PostgreSQL**: la auditoría previa medía que no se sumaban (+2 %); ahora 12,0 s frente a 12,3 s, sin penalización.

## AUDIT_CODE
- **API pública**: sin cambios. **Engine del usuario**: sin cambios (opciones en la sentencia).
- **Resultados**: mismas filas y tipos (verificación y sonda de identidad en las 13 mediciones).
- **Concurrencia**: cada lector de rangos abre su conexión; el cursor de servidor no se comparte.
- **Otros motores**: sin cambios (test).

## VERSION
- Commit: `refactor(dump): leer con cursor de servidor en PostgreSQL, MySQL y MariaDB (Q2)`
- Changelog: `[Unreleased]` → *Changed* (rendimiento).
- Impacto en API pública: ninguno.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump]**: las lecturas de `dump` usan cursor de servidor en PostgreSQL/MySQL/MariaDB (`_CLIENT_CURSOR_DIALECTS`). No lances otra consulta por la misma conexión mientras se lee (MySQL no lo permite con un cursor sin consumir).
- **[bench]**: la variante `stream` del banco fija `stream_results` en el engine de origen; tras Q2 debería dar lo mismo que `baseline`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Fase 1: Q3 (solape lectura/escritura) y Q4 (guía de `parallel_pk_ranges`).
