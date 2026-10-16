# REQUEST

## Session metadata
- id: 2026-10-16f
- fecha: 2026-10-16
- rama: develop
- skill: new_feature + refactor incompatible (alcance mixto pedido explícitamente)
- fase solicitada: análisis → PLAN + AUDIT_PLAN (opción B) → IMPLEMENT (con las recomendaciones D1–D3)

## Solicitud original saneada
Crear una estrategia para que la ejecución de `src/util_bbdd/bulk/_execution/parallel_loader.py` se decida
automáticamente mediante un algoritmo optimizado, con parámetros pedidos en la API de `BulkCrud` (en `dump` ya se hace
así). `BulkCrud` recibe más de 13 parámetros y debería recibir el resto en paquetes compactados. Analizar las
implicaciones en `bulk` y `dump`. Explicar por qué `parallel_loader.py` tiene funciones fuera de la clase.

Después: «PLAN y AUDIT_PLAN con B — Reempaquetar todo de una vez: cambio incompatible, exige versión MAJOR», y
«IMPLEMENT acepto recomendaciones». Durante IMPLEMENT: «Si lo necesitas puedes ejecutar nuevos benchmarks».

## Objetivo operativo de esta sesión
- Paquetes de opciones inmutables comunes a `BulkCrud` y `ParallelBulkLoader` (API 3.0.0, sin compatibilidad 2.x).
- `ParallelPlanner` puro con reglas medidas, usado por `ParallelBulkLoader`, `BulkCrud` y `dump`.
- Ruta paralela opcional en `BulkCrud.bulk_*_from_df` y `DumpConfig(parallel_pk_ranges="auto")`.
- Reubicar las funciones sueltas de `parallel_loader.py`.

## Restricciones explícitas
- Opción B: ruptura de API en una sola MAJOR (2.2.4 → 3.0.0), sin capa de compatibilidad.
- D1: `DumpConfig` no se reempaqueta. D2: la fachada paralela de `BulkCrud` entra en 3.0.0. D3: campos sin prefijo.
- No hacer commit ni push sin que lo pida el usuario; no usar `git add -A` (el usuario trabaja en paralelo).

## Resultado esperado
- Código, tests y documentación de 3.0.0 en `develop` (sin commit), puerta de calidad en verde.
- Artefactos en `.ai/sessions/2026-10-16f-bulk-options-parallel-planner/`.
