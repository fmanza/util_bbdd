# TRACEABILITY

## Session metadata
- id: 2026-09-26k-refactor-dump-ranges-guidance
- fecha: 2026-09-26
- rama: develop (base `ee1d64e`)
- skill: refactor (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION); aviso en log y documentación, sin cambio funcional
- origen: Q4 / paso 1.4 del roadmap `2026-09-25b-performance-audit-dump-delta` (PF-04 de la auditoría `2026-09-25-performance-audit-dump`)

## Prompt issued
```
/refactor Q4: guía por motor para parallel_pk_ranges y aviso donde empeora. Volver a medir ranges4 frente a baseline con
el código actual (tras Q1–Q3) antes de escribir la guía. Sin cambios de API ni de resultado.
```
Durante la medición, el usuario aportó un WARNING del log de MySQL (`[MY-014084] … log_checkpointer … Considere aumentar
innodb_redo_log_capacity`) y pidió **las dos cosas**: escribir la guía y medir con más redo log.

## Mediciones
- **`baseline` frente a `ranges4`, código actual, redo por defecto** (`large`, 2 rondas intercaladas; `results/`):

| Motor | `baseline` | `ranges4` | Δ media | Auditoría (antes de Q1–Q3) |
|---|---|---|---|---|
| SQL Server | 57,0 · 66,4 s | 43,9 · 33,9 s | **−37 %** | −55 % |
| PostgreSQL | 17,0 · 14,9 s | 17,5 · 11,6 s | −9 % (ruidoso) | −35 % |
| Oracle | 38,3 · 32,1 s | 36,6 · 32,5 s | −2 % | −23 % |
| MySQL | 38,5 · 38,9 s | 67,4 · 80,0 s | **+90 %** | +14 % |
| MariaDB | 37,5 · 40,1 s | 67,1 · 83,4 s | **+94 %** | +27 % |

  Todas las mediciones verificadas (datos, sonda de identidad, PK sync — PD-11 ya corregido).
- **El WARNING de MySQL** (00:33:50 UTC) coincide con la segunda medición `ranges4` de MySQL. Configuración del contenedor del banco: MySQL 8.4.11 con `innodb_redo_log_capacity` = 100 MB y MariaDB 11.4 con `innodb_log_file_size` = 96 MB (valores por defecto); `innodb_buffer_pool_size` = 512 MB; `innodb_flush_log_at_trx_commit` = 1. Cuatro escritores concurrentes generan redo más rápido de lo que el checkpoint libera y InnoDB detiene a los escritores.
- **Experimento con 2 GB de redo log** (`redo_2gb/`; `SET GLOBAL`, no persistente; valores originales restaurados y comprobados al terminar: MySQL 104857600, MariaDB 100663296):

| Motor | `baseline` | `ranges4` | Δ |
|---|---|---|---|
| MySQL | 37,6 · 38,2 s | 71,7 · 72,9 s | +90 % |
| MariaDB | 37,3 · 37,7 s | 70,6 · 67,2 s | +84 % |

  Con más redo, `ranges4` es más estable (MySQL 67–80 s → 72–73 s: desaparecen las esperas intermitentes), pero sigue casi al doble. El redo log no es la causa principal. Hipótesis, sin medir por separado: PyMySQL es Python puro (decodificar y codificar filas es CPU bajo el GIL) y 4 lectores + 4 escritores compiten por él, mientras la carga secuencial ya solapa lectura y escritura con un solo escritor (Q3).

- **Experimento con 4 GB de redo log** (a petición del usuario, para confirmar; `redo_4gb/`; mismo procedimiento, valores originales restaurados y comprobados):

| Motor | `baseline` | `ranges4` |
|---|---|---|
| MySQL | 57,5 · 51,9 s | 69,1 · 68,9 s |
| MariaDB | 71,9 · 46,8 s | 85,3 · 74,8 s |

  - `ranges4` queda donde con 2 GB (≈ 69–85 s frente a ≈ 70 s): **confirma que el redo log no resuelve la carga por rangos** en MySQL/MariaDB.
  - `baseline` empeoró durante el experimento (47–72 s frente a 37–38 s). Causa: E/S transitoria del redimensionado del redo log (InnoDB crea los ficheros nuevos en segundo plano) sobre el disco del contenedor (WSL2); no es un efecto del tamaño.
  - Comprobación tras restaurar: la primera medición siguió lenta (MySQL 51,6 s, MariaDB 65,7 s) con InnoDB ya en reposo (`Innodb_redo_log_resize_status = OK`, 0 páginas sucias, history list 0, contenedores sin carga). Minutos después, control: PostgreSQL 15,7 s, **MySQL 38,4 s y MariaDB 38,4 s**, con las mismas fases que antes del experimento (`control/`, `tras_restaurar/`). Los contenedores quedan como estaban.

## Cambio de conclusiones frente a la auditoría
- El solape de Q3 acelera la carga secuencial y no se aplica a la ruta por rangos; la ventaja de los rangos se reduce (SQL Server, PostgreSQL, Oracle) o se invierte (MySQL/MariaDB).

## IMPLEMENT
- `dump/orchestrator.py`: `_warn_slow_pk_ranges(requested)` (nuevo), llamado desde `_resolve_range_count`. Con destino MySQL/MariaDB y `parallel_pk_ranges > 1` registra un WARNING con la recomendación (`parallel_pk_ranges=1`). **No fuerza el valor**: es más lento, no incorrecto (a diferencia de SQLite, PD-06).
- `dump/_models.py`: docstring de `DumpConfig.parallel_pk_ranges` con el efecto medido por motor.
- `docs/api/dump.md`: fila `parallel_pk_ranges` con la guía por motor y la capacidad del pool; fila nueva en «Errores y casos especiales». HTML comprobado: 13 filas en la tabla de parámetros y 5 en la de errores.
- `CHANGELOG.md`: *Changed*.

## Validación
- **Tests** (`TestSlowPkRangesWarning`, 6): aviso con destino MySQL/MariaDB sin cambiar el valor pedido; sin aviso en PostgreSQL, SQL Server y Oracle; sin aviso con 1 rango.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy` limpio; `pytest tests/unit`: **4558 passed**; `mkdocs build --strict` sin errores.

## AUDIT_CODE
- **Sin cambio de comportamiento**: el número de rangos resultante es el mismo que antes (test).
- **API pública**: sin cambios.

## VERSION
- Commit: `refactor(dump): guía y aviso de parallel_pk_ranges por motor (Q4)`
- Changelog: `[Unreleased]` → *Changed*.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump]**: `parallel_pk_ranges` solo compensa claramente en SQL Server tras Q3; en MySQL/MariaDB casi duplica el tiempo, también con 2 y 4 GB de redo log.
- **[bench mysql/mariadb]**: el contenedor usa el redo log por defecto (100/96 MB); con escritores concurrentes aparece `[MY-014084]` y las mediciones oscilan. Para experimentar, `SET GLOBAL innodb_redo_log_capacity` (MySQL) / `innodb_log_file_size` (MariaDB), no persistente, y restaurar al terminar. Tras redimensionar, espera unos minutos antes de medir: la E/S del redimensionado distorsiona las mediciones siguientes.
- **[rendimiento]**: al cambiar la ruta secuencial (p. ej. Q3), vuelve a medir las rutas paralelas: la comparación relativa cambia.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Fase 1 del roadmap completa (Q1–Q4). Fase 2: Q5 (lote de escritura por motor), Q6 (`manage_indexes`), 2.3 (aviso `_warn_chunk_size`).
