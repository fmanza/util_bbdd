# REQUEST

## Session metadata
- id: 2026-10-03-metadata-centralization
- fecha: 2026-10-03
- rama: develop
- skill: metadata_centralization_audit_and_refactor (`/metadata-centralization`)
- fase solicitada: PLAN + AUDIT_PLAN

## Solicitud original saneada

```text
/metadata-centralization

Módulo destino: metadata/ ampliado
Ejes: ambos
Motores: todos
Baseline: no (capturar en PLAN)
Volumen de catálogo: 50 / 500 / 5000 tablas
Banco: sí (docker-compose.bench.yml)
Fases autorizadas: PLAN + AUDIT_PLAN
```

Contexto de la petición que originó el prompt (sesión anterior): centralizar toda la extracción de metadatos de los
diccionarios de datos de los motores en un módulo (nuevo o existente); se pueden romper contratos y API pública; aplica
a todo el proyecto; profundidad de auditoría sin límite; se puede consultar internet.

## Objetivo operativo de esta sesión
- Inventariar todos los caminos de extracción de metadatos de `src/util_bbdd/` (SQL de catálogo, `Inspector`,
  `data/sql_queries.json`) con `ruta:línea` verificada.
- Capturar el baseline de rendimiento de cada flujo que lee metadatos contra el banco (6 motores × 50/500/5000 tablas).
- Diseñar la arquitectura objetivo de `metadata/` ampliado y el borrador de ADR-003.
- Emitir el plan incremental por grupos y el veredicto de AUDIT_PLAN.

## Restricciones explícitas
- Solo PLAN + AUDIT_PLAN: no se modifica `src/`, `tests/` ni `docs/` (el ADR-003 queda como borrador en la sesión).
- Medición solo contra los contenedores del banco (`127.0.0.1`, puertos no estándar); nunca contra bases reales.
- Revalidar el «Punto de partida» del prompt (medido sobre v0.29.0) contra el árbol actual.
- No hacer `git add -A`: el usuario trabaja en paralelo.

## Resultado esperado
- `.ai/sessions/2026-10-03-metadata-centralization/` con `00_REQUEST.md`, `00_CONTEXT_SNAPSHOT.md`, `01_INVENTARIO.md`,
  `02_BASELINE_RENDIMIENTO.md`, `03_DISENO.md`, `ADR-003-borrador.md`, `04_PLAN.md`, `05_AUDIT_PLAN.md`,
  `TRACEABILITY.md` y el arnés de medición en `bench/`.
