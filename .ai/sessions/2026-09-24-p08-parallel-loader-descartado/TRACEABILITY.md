# TRACEABILITY

## Session metadata
- id: 2026-09-24-p08-parallel-loader-descartado
- fecha: 2026-09-24
- rama: develop
- skill: performance (medición de una hipótesis; sin cambios de código)
- fase: PLAN + medición + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Hago el commit y paso a P-08 …? … lo mediré antes de tocar nada". Antes, commits `2d99a84` y `03be4ac` de P-07.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-08, HIPÓTESIS):
  - cada partición crea un `BulkCrud`, refleja la tabla y, en MySQL, abre una conexión para validar variables;
  - "en Oracle puede costar segundos";
  - los hilos escalan poco por el GIL hasta resolver P-03.
- `src/util_bbdd/bulk/_execution/parallel_loader.py` (`_load_partition`), `src/util_bbdd/bulk/crud.py` (`__validate_mysql_config`, `reflect_table`)

## AI output summary
- **Medición** (`scratchpad/p08_bench.py`, 6 motores del banco, tabla de 10 columnas). Coste por partición, mediana de 5; `ParallelBulkLoader` con 200K filas en 4 particiones, mejor de 2:

  | Motor | `BulkCrud()` | Reflexión | 1 hilo | 4 hilos | Escalado |
  |---|---|---|---|---|---|
  | SQLite | 0,0 ms | 0,9 ms | 1,24 s | 1,34 s | 0,92× |
  | PostgreSQL | 0,0 ms | 11,5 ms | 2,65 s | 1,00 s | 2,64× |
  | MySQL | 4,9 ms | 2,0 ms | 3,60 s | 1,91 s | 1,88× |
  | MariaDB | 3,4 ms | 1,7 ms | 2,89 s | 1,80 s | 1,61× |
  | SQL Server (pymssql) | 0,0 ms | 61,5 ms | 49,08 s | 12,68 s | 3,87× |
  | Oracle | 0,1 ms | 8,8 ms | 3,06 s | 1,68 s | 1,82× |

- **Conclusión**:
  - el coste por partición no pasa del 2% de la carga (SQL Server: 4 × 66 ms frente a 12,7 s);
  - los hilos sí escalan tras P-03 (1,6–3,9×);
  - la única excepción es SQLite (un solo escritor), que es una limitación del motor.

  **P-08 se descarta**; reflejar una vez y compartir el `Table` ahorraría menos del 2%.
- **Documentación**: `docs/guides/benchmarks.md` (sección de carga paralela) con la tabla de escalado, la recomendación `max_workers=1` en SQLite y el coste por partición. Una entrada en CHANGELOG (docs).
- **Validación**: `mkdocs build --strict` sin avisos nuevos.

## Observación (sin cambio)
- `docs/api/bulk-parallel.md` dice que en `partition_errors` se captura "cualquier excepción dentro de un worker". En realidad `_load_partition` captura `SQLAlchemyError`, `ValueError` y `pandas.errors.DatabaseError`; el resto se propaga y aborta `load()`. Tras P-28 los errores de PostgreSQL ya entran en ese grupo. Pendiente de decidir: ajustar la documentación o ampliar la captura.

## Directrices para Futuras IAs
- **[medición]**: una hipótesis de rendimiento no se implementa sin medirla contra el motor real (P-08 y P-17 se descartaron así).
- **[SQLite]**: no recomendar carga paralela en SQLite.

## Veredicto final
Veredicto: CLOSED (descartado)
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
- Bloque de mejoras menores de la auditoría completado: P-06, P-07, P-09, P-10 y P-13 aplicados; P-08 descartado; Known issue resuelto. Hallazgos nuevos corregidos: P-25 a P-29.
