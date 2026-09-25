# TRACEABILITY — 2026-09-25 audit-code AuditManager (bulk, Área A5)

- Skill: `/audit-code` (solo lectura) con la metodología de 5 fases de `.github/prompts/audit_audit_manager_bulk.prompt.md`
- Rama: `develop` @ `5499828` · Código de `src/` sin cambios

## Solicitud
Auditar la auditoría integrada del módulo `bulk` (rendimiento, sync/async, persistencia, multi-dialecto) y generar el informe y el roadmap.

## Ejecutado
- FASE 1: mapa real (`bulk/audit.py`, `bulk/_audit/*`, `_support/persistence.py`, puntos de integración en `crud.py`, `parallel_loader.py`, `dump/orchestrator.py`). El prompt cita ficheros inexistentes (`audit_manager.py`, `bulk_crud.py`) → H14.
- FASE 2: micro (290 µs/llamada), cProfile, contención con 8 hilos, memoria, E2E SQLite 1K/100K/1M con/sin auditoría y tiempo dentro de la auditoría (0,02 % → 16,5 %). Proyección a 5 motores con la línea base 2026-09-24. **No se ha medido en motores servidor**: las URLs del banco no estaban en el entorno.
- FASE 3: 14 hallazgos (2 ALTA, 5 MEDIA, 4 BAJA, 3 INFO). R1–R7 reproducidos con `bench/repro_audit.py`; H12 verificado con openpyxl.
- FASE 4: roadmap en 3 fases + ideas descartadas.
- FASE 5: matriz multi-dialecto; la auditoría es agnóstica al motor.
- Tests existentes: 53/53 en verde.

## Artefactos
- `audit_report_audit_manager_20260925.md`
- `optimization_roadmap_audit_manager.md`
- `bench/bench_audit.py`, `bench/prof_audit.py`, `bench/repro_audit.py`

## Veredicto
**APROBADO CON CONDICIONES**: corregir H2 (fila de auditoría antes del commit), H1 (fallo de auditoría tras commit), H4, H3 y H12.

## Directrices para futuras IAs
- El componente es `bulk/audit.py` + `bulk/_audit/`, **no** `audit_manager.py`. Es síncrono, sin buffer, y escribe 1 fila CSV por operación o chunk.
- El coste por fila CSV en Windows (~0,3–0,8 ms) lo ponen `resolve()`/`mkdir()`/`open` por llamada, no la escritura.
- Para medir overhead de auditoría, instrumentar el tiempo **dentro** de `registrar_operacion`: la resta E2E con/sin queda en el ruido (±4 %).
- No cambiar el formato del CSV (lo consume `dump/orchestrator.py:_build_audit_summary`).
- Pendiente de decisión del mantenedor: política fail-open/fail-closed (M-2).
