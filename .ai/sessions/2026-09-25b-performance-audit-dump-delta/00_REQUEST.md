# REQUEST

## Session metadata
- id: 2026-09-25b-performance-audit-dump-delta
- fecha: 2026-09-25
- rama: develop (sobre `cfbbf05`, v0.15.0)
- skill: performance-audit-dump
- fase solicitada: FASE 1–5 en modo **delta** frente a la auditoría `2026-09-25-performance-audit-dump` (`5557688`). Sin IMPLEMENT en `src/`.

## Solicitud original saneada
```
/performance-audit-dump
Objective: Auditar rendimiento del módulo dump (volcado masivo de datos)
Scope: src/util_bbdd/dump/ — todas las clases y funciones
Validation: ejecutar bench_dump.py post-audit para validar mejoras
```

Respuestas a los inputs obligatorios (preguntados antes de la FASE 1):

| Input | Respuesta |
|---|---|
| Relación con la auditoría previa del mismo día | **Re-auditoría delta**: cambios de `dump` desde `5557688`, nueva línea base, estado de PD-01…09 y CB1–CB8; actualizar informe y roadmap |
| Banco de validación | **Llevar el banco real a `scripts/`** (roadmap 1.5 / Q7) y validar con él |
| Dialects | Los 6 de la auditoría previa: PostgreSQL, MySQL, MariaDB, SQL Server, Oracle, SQLite (destino) |
| Volumen | `large` (3,5M filas; datos ya cargados en los contenedores) |
| Timeline | ASAP (supuesto, no se preguntó; como en la auditoría previa) |
| Validación | Sí |

## Objetivo operativo de esta sesión
- Sustituir `scripts/bench_dump.py` (no medía `dump`) por el banco real y alinear las guías que describen su CLI.
- Medir la línea base actual (v0.15.0) en los 6 motores con 3 repeticiones y compararla con la de `5557688`.
- Medir el área nueva desde la auditoría previa: la auditoría de `bulk` dentro del volcado (`bulk_audit_path`, resumen del CSV).
- Re-verificar el estado de PD-01…PD-09 y actualizar el roadmap.

## Restricciones explícitas
- Solo análisis y banco: no se edita `src/`.
- `setup` del banco NO se ejecuta (borraría los datos `large` ya cargados).
- La contraseña del banco se lee del entorno del contenedor (`docker inspect`) con autorización del usuario; no se imprime ni se guarda.
- `.github/agents/config-reviewer.agent.md` tiene cambios ajenos a esta sesión en el árbol de trabajo: no se tocan ni se incluyen.

## Resultado esperado
- `scripts/bench_dump.py` nuevo + guías actualizadas.
- `audit_report_dump_delta_20260925.md`, `improvement_roadmap_dump.md` (actualizado), `validation_report_delta_20260925.md`.
- `results/results.jsonl` con los datos crudos.
- `TRACEABILITY.md` y entrada en `INDEX.md`.
