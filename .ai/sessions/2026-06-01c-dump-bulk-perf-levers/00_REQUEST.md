# REQUEST

## Solicitud original (saneada)

Optimizar la carga de datos masivos en `src/util_bbdd/bulk` y `src/util_bbdd/dump`,
usando entre otras palancas: deshabilitar índices y constraints durante la carga y
reconstruirlos al final, commits por lotes (no por fila), y paralelizar por tabla o por
rangos de PK si el destino lo tolera.

Tras la evaluación inicial (solo PLAN + AUDIT_PLAN), el trabajo se descompuso en
incrementos y se ejecutó en orden, con commits separados y validación por incremento.
Después se actualizó documentación, se hizo thread-safe la auditoría, se rebalanceó la
frontera bulk↔dump (bulk como dueño del mecanismo de carga de gran volumen) y se cerró
la versión 0.9.0.

## Restricciones
- Todas las palancas **opt-in**, desactivadas por defecto (comportamiento previo intacto).
- Constraints ya gestionadas por `ConstraintManager`; faltaban índices, commits por lote y
  paralelización.
- `BulkCrud` no es thread-safe → una instancia por hilo.
- MariaDB: el `engine.dispose()` del `ConstraintManager` bloqueaba la paralelización →
  refactor previo (prerequisito).
- Mantener `ruff` + `mypy` + `pytest` verdes en cada incremento.

## Decisiones del usuario durante la sesión
- Planificar las 3 palancas, implementar por incrementos en orden #0→#3.
- MariaDB: refactorizar `dispose()` (no excluir MariaDB del paralelo).
- Incluir paralelización por rangos de PK además de por tabla.
- Tras docs: hacer thread-safe la auditoría y reactivarla en paralelo.
- Rebalanceo bulk↔dump: opción 2 (API de gran volumen en bulk), implementar (a) y luego (b).
- Cierre de versión: cortar release **0.9.0**.
