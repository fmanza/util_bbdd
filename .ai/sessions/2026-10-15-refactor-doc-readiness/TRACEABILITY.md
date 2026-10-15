# TRACEABILITY

## Session metadata
- id: 2026-10-15-refactor-doc-readiness
- fecha: 2026-10-15
- rama: develop
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Hacer el /refactor para que doc reutilice audit/readiness.py y la lógica no esté repetida. PLAN y AUDIT_PLAN; después
«IMPLEMENT con la recomendación» (incluir los alias de los Protocols duplicados).

## Context supplied
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md`, `.github/prompts/refactor.prompt.md`, `.github/agents/plan-architect.agent.md`
- Sesiones previas `2026-10-15-engine-conditions-doc` y `2026-10-15-engine-readiness-audit-sheets`

## AI output summary
- PLAN + AUDIT_PLAN: GO. Comparación línea a línea: lógica idéntica salvo el aviso de informe `None`, que `doc` conserva
- IMPLEMENT: `EngineConditionsSectionBuilder.build()` delega en `ReadinessRows.from_report()`; alias de Protocols en
  `doc/application/ports.py`; arista `doc → audit` en `DRAWN` (sin geometría: la etiqueta de la flecha a `audit/` se
  genera de `DRAWN`)
- Fallo detectado por pytest, no por mypy: import relativo `...audit` un nivel corto en `use_cases/` (`ignore_missing_imports`)
- AUDIT_CODE: equivalencia comprobada contra el builder de `HEAD` con 3000 informes aleatorios, `None` y `of()`
- Puerta: ruff, mypy, pytest 5816 pasan / 531 saltos (ningún test modificado), `gen_arquitectura_capas`, `zensical build --strict`

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/doc/application/{ports.py,use_cases/engine_conditions.py}`, `src/util_bbdd/audit/readiness.py` | completado |
| Diagrama | `scripts/gen_arquitectura_capas.py`, `docs/assets/diagrams/arquitectura-capas.svg` | completado |
| Logs | `build/logs/refactor_readiness_{pytest,mypy}.txt` | no versionado |

## Directrices para Futuras IAs
- **[mypy]**: `pyproject.toml` tiene `ignore_missing_imports = true` global: un import relativo interno mal escrito
  (p.ej. `...audit` en vez de `....audit`) pasa `mypy src` como `Any`. Validar imports nuevos con pytest o importando
  el módulo, no solo con mypy.
- **[readiness]**: `audit.readiness.ReadinessRows` es la única fuente de filas, resumen, verificación y avisos de las
  condiciones del motor (Excel de bulk y dump, sección de doc). `doc` solo añade sus cabeceras (`CONDICIONES_MOTOR`) y
  su aviso de origen no compatible.
- **[refactor/equivalencia]**: para probar «sin cambios funcionales» en una transformación pura, ejecutar la versión de
  `HEAD` (`git show HEAD:<ruta>` + `exec` con `__package__` del paquete original) contra la nueva sobre entradas
  aleatorias; es barato y más fuerte que los tests de ejemplo.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Commit (rutas de la sesión) y `/version-closure` (2.2.0)
