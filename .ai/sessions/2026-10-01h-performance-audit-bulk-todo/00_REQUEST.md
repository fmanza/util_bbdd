# REQUEST

## Session metadata
- id: 2026-10-01h-performance-audit-bulk-todo
- fecha: 2026-10-01
- rama: develop (HEAD `e80059e`, v0.23.1)
- skill: performance-audit-bulk (solo lectura sobre `src/`)
- fases: PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION (+ validación con banco)

## Solicitud original

```text
/performance-audit-bulk
Objetivo: TODO + paralelización + batching + Backpressure + Checkpoints + Manejo de Errores y Tolerancia a Fallos + Audit + Rendiento
Baseline: ejecutar benchmark primero
Dialects: Todos
Volumen: 1000K registros
Timeline: ASAP
Validación: sí
Presentar resultados por objetivos
```

## Interpretación y supuestos explícitos
- **Objetivo**: las 10 áreas del prompt, agrupadas en 7 objetivos: Rendimiento, Batching, Paralelización,
  Backpressure, Checkpoints, Errores y tolerancia a fallos, Auditoría. "Rendiento" se lee como "Rendimiento".
- **Dialects «Todos»**: los 6 del banco — SQLite 3.50, PostgreSQL 17 (psycopg 3), MySQL 8.4 y MariaDB 11.4 (PyMySQL),
  SQL Server 2022 (pyodbc + ODBC 18, driver recomendado por la librería) y Oracle 23 Free (oracledb thin). HSQLDB queda
  fuera: no hay servidor en el banco (supuesto).
- **Volumen**: 1M filas como tamaño principal; 1K/10K/100K (mediana de 3) para ver tendencias.
- **Baseline**: `scripts/bench_bulk.py` antes de cualquier prototipo (`baseline/`).
- **Validación**: prototipos A/B fuera de `src/` (`bench/`), verificados con SQL. No se modifica la librería.
- **Restricciones**: conservar atomicidad por defecto, auditoría integrada y compatibilidad multi-BBDD.
- **Límite del entorno**: servidores en Docker local (latencia de red ~0). Contra un servidor remoto, las vías con más
  idas y vueltas por fila empeoran proporcionalmente.
