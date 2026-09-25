# TRACEABILITY

## Session metadata
- id: 2026-09-25b-performance-audit-dump-delta
- fecha: 2026-09-25
- rama: develop (sobre `cfbbf05`, v0.15.0)
- skill: performance-audit-dump
- fase: FASE 1 (delta de arquitectura) + FASE 2 (CB1–CB8 y PD-xx re-verificados) + FASE 3 (priorización) + FASE 4 (informe delta + roadmap actualizado) + FASE 5 (validación con banco). Sin IMPLEMENT en `src/`.

## Prompt issued
```
/performance-audit-dump
Objective: Auditar rendimiento del módulo dump (volcado masivo de datos)
Scope: src/util_bbdd/dump/ — todas las clases y funciones
Validation: ejecutar bench_dump.py post-audit para validar mejoras
```
Inputs completados con el usuario antes de la FASE 1: re-auditoría delta; llevar el banco real a `scripts/`; 6 motores; `large`. Timeline ASAP (supuesto).

## Context supplied
- `.claude/commands/performance-audit-dump.md`, `.claude/performance-audit-guide.md`, `.github/prompts/performance_audit_dump_agent.prompt.md`
- Sesión `2026-09-25-performance-audit-dump` (informe, roadmap, `bench/bench_dump_real.py`, `summarize.py`, resultados)
- `git log`/`git diff 5557688..HEAD` de `src/util_bbdd/dump/` y `src/util_bbdd/bulk/`

## AI output summary
- Detectado que el módulo ya se había auditado el mismo día (`5557688`) y que `scripts/bench_dump.py` seguía sin llamar a `DumpOrchestrator`; se preguntó al usuario el enfoque (delta) y el banco (llevar el real a `scripts/`).
- `scripts/bench_dump.py` reescrito desde `bench_dump_real.py`: subcomandos `summarize` y `list`, variantes `audit`/`audit_history`, fase `audit_summary`, copia de `_load_whole_table` de `prefetch` alineada con el código actual (`AuditError`, `OSError`), informes y CSV en directorio temporal, SQLite en `<tmp>`, stdout UTF-8. ruff + mypy OK. `summarize` reproduce las medianas de la sesión previa.
- Guías actualizadas a la nueva CLI: `docs/PERFORMANCE_AUDIT_GUIDE.md`, `.claude/performance-audit-guide.md`, `.github/prompts/performance_audit_dump_agent.prompt.md`, `.claude/commands/performance-audit-dump.md`.
- Docker Desktop arrancado y contenedores del banco iniciados (`docker start`); contraseña leída de `docker inspect` con autorización del usuario, sin imprimirla ni guardarla. Datos `large` verificados (COUNT) y esquemas sin tablas ajenas. `setup` no se ejecutó.
- Matriz: 6 motores × {baseline, audit} × 3 + `audit_history` × 3 (PG) + `redump` × 1 (PG, SQLite) → 42 mediciones, todas sin excepción. Microbanco aislado de `AuditManager.leer_auditoria` (100K/500K/2M registros).
- Hipótesis `format="mixed"` como causa del coste del resumen de auditoría: refutada (0,18 s de 0,71 s).
- Revisión de código de PD-01…PD-09: solo PD-06 cambia (mitad corregida por `cf0eafc`).
- Roadmap previo marcado como histórico; roadmap vigente en esta sesión.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Solicitud | `00_REQUEST.md` | emitido |
| Informe delta | `audit_report_dump_delta_20260925.md` | emitido |
| Validación | `validation_report_delta_20260925.md` | emitido |
| Roadmap vigente | `improvement_roadmap_dump.md` | emitido |
| Datos crudos | `results/results.jsonl` | completado |
| Banco | `scripts/bench_dump.py` | completado |
| Guías | `docs/PERFORMANCE_AUDIT_GUIDE.md`, `.claude/performance-audit-guide.md`, prompt y comando | completado |

## Directrices para Futuras IAs
- **[bench]**: `scripts/bench_dump.py` es el banco real de `dump`. `setup` BORRA `dump_src`/`dump_dst`; si los datos `large` ya están (compruébalo con COUNT), no lo ejecutes. Los contenedores no tienen volúmenes externos: `docker start` conserva los datos, `docker rm` no.
- **[bench]**: la copia de `_load_whole_table` de la variante `prefetch` debe seguir al original; si cambia `DumpOrchestrator._load_whole_table`, actualízala o `prefetch` medirá otro código.
- **[bench]**: el ruido entre repeticiones llega a ±20 % (PG `audit` 18,6/23,7/23,2 s) y el primer arranque en frío a +27 %. Mediana de 3 como mínimo; no atribuyas diferencias entre sesiones sin un commit que las explique.
- **[dump]**: línea base v0.15.0: PG 19,1 s · SQLite 21,3 · MariaDB 52,9 · MySQL 57,0 · Oracle 57,6 · SQL Server 65,8 (3,5M filas).
- **[dump/audit]**: activar `bulk_audit_path` cuesta ≤ ruido. El resumen relee todo el CSV (≈ 1,4 µs/registro): relevante solo con CSV de millones de registros.

## Veredicto final
Veredicto: GO_CONDICIONAL (APROBADO CON CONDICIONES: sin cambio; corregir PD-01, PD-02, PD-03, PD-05 y PD-08 antes de la Fase 1)
Pendientes al cierre:
- `/hotfix` de PD-02 y PD-03 (reproducidos otra vez) y del resto de la Fase 0.
- Fase 1 del roadmap (Q1–Q4) con medición antes/después en `scripts/bench_dump.py`.
- Contenedores del banco quedan en marcha con los datos `large` en `dump_src`/`dump_dst`.
