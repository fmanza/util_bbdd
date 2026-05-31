# REQUEST

## Session metadata
- id: 2026-06-01b-dump-skip-schema-comparison
- fecha: 2026-06-01
- rama: develop
- skill: new_feature (perf) — PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION
- fase solicitada: análisis de rendimiento e implementación de optimizaciones

## Solicitud original saneada

> Cuando se hacen inserciones solo con el módulo `src/util_bbdd/dump` los tiempos de
> inserción son mucho más cortos que cuando se usan a través de `src/util_bbdd/comparar`.
> Revisar; se necesita que los tiempos sean muy pequeños, buscar optimizaciones.

Decisiones tomadas con el usuario (vía AskUserQuestion):
- **Enfoque**: *Eliminar* la comparación de esquemas del volcado (no flag opcional, no reducir flags).
- **Alcance**: Implementar y verificar (ruff + mypy + pytest), no solo análisis.

## Objetivo operativo de esta sesión
- Identificar por qué un volcado (`DumpOrchestrator.run()`) es más lento que una inserción directa con `bulk`.
- Eliminar el coste fijo previo al primer INSERT sin alterar la salida del informe Excel.
- Mantener API pública de `DumpOrchestrator.run()` y la suite de tests en verde.

## Restricciones explícitas
- No mezclar con deuda técnica ajena (p. ej. errores mypy preexistentes en otros módulos).
- El informe Excel de 3 hojas debe permanecer equivalente.
- Respetar el flujo del proyecto: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

## Resultado esperado
- `dump/orchestrator.py` sin la fase de comparación de esquemas.
- `dump/reporters.py` alimentando la hoja «Columnas Inexistentes» desde `TableDumpResult.skipped_columns`.
- Tests actualizados + tests de regresión; docs y CHANGELOG sincronizados.
- Carpeta `.ai/sessions/2026-06-01b-dump-skip-schema-comparison/` con trazabilidad.
