# /metadata-centralization

Centralización de **toda** la extracción de metadatos (SQL de catálogo, `Inspector` de SQLAlchemy y
`data/sql_queries.json`) en un único módulo, junto con la mejora del rendimiento de la introspección (consultas por
schema en vez de por tabla, caché, vista de catálogo por motor). Permite romper la API pública si se justifica y se
documenta.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/metadata_centralization_audit_and_refactor.prompt.md` — inputs, fases, áreas, medición y veredicto (contrato de salida)
2. `.github/instructions/architecture.instructions.md` § «Reglas de acceso a metadatos» (Reglas #1–#6)
3. `.github/agents/plan-architect.agent.md` (PLAN + AUDIT_PLAN) y `.github/agents/performance-auditor.agent.md` (eje de rendimiento)
4. `.ai/architecture.md`, `.ai/standards.md`, `.ai/runtime.md` y `.ai/glossary.md`

## Reglas de ejecución

- Si falta algún input del prompt, decláralo como supuesto explícito antes de la fase PLAN.
- Revalida el «Punto de partida» (§2 del prompt) contra el árbol actual antes de usarlo.
- Para por defecto tras AUDIT_PLAN: IMPLEMENT necesita aprobación explícita y avanza por grupos (un PR por grupo).
- Medición: conteo de consultas con `before_cursor_execute` y `scripts/bench_metadata.py` (lo crea el grupo F si no
  existe; banco en `.ai/runtime.md`). Nunca contra bases reales.
- Puedes consultar internet; cita la fuente con fecha.
- Entregables en la carpeta de la sesión (`.ai/sessions/<fecha>-metadata-centralization/`): `01_INVENTARIO.md`,
  `02_BASELINE_RENDIMIENTO.md`, `03_DISENO.md` (+ borrador de `docs/adr/ADR-003-*.md`) y `04_PLAN.md`.

## Ejemplo de entrada

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
