# Prompt: tech_debt (Python library)

Inventario de deuda técnica. No mezclar con nuevas features en el mismo PLAN.
Agentes: Plan Architect (análisis); si el scope autoriza IMPLEMENT, Feature Implementer → Code Auditor → Version Closer.

## Inputs requeridos
- **Módulo/paquete objetivo** (p.ej. `src/util_bbdd/metadata/mariadb/`)
- **Deuda conocida o síntomas** (p.ej. "hay `Any` sueltos", "duplicación sync/async")
- **Versión actual** y rama activa
- **Scope**: solo análisis (PLAN + AUDIT_CODE) o también IMPLEMENT
- **Política de compatibilidad**: ¿se autoriza romper contratos públicos?

Si falta alguno, decláralo como supuesto explícito antes de continuar.

## Devuelve en este orden
1. PLAN — módulo objetivo, síntomas, scope, riesgos de regresión al abordarla
2. AUDIT_PLAN — riesgos funcionales, técnicos y de seguridad; dependencias entre ítems de deuda
3. AUDIT_CODE — ver «Salida» abajo
4. VERSION (solo si IMPLEMENT fue autorizado) — commit `refactor: <descripción>` y pruebas sugeridas

## Salida — AUDIT_CODE de deuda técnica
- deuda detectada por módulo (archivo concreto + línea si aplica)
- impacto real (tipado, mantenibilidad, tests, rendimiento, seguridad)
- prioridad clasificada:
  - `quick_win` — < 1h, sin riesgo de regresión
  - `fase_media` — cambio acotado, test requerido, posible breaking change
  - `deuda_estructural` — refactor amplio, decisión de arquitectura
- quick wins listos para implementar (con estrategia de prueba mínima)
- plan por fases con orden de dependencias
- riesgos si no se aborda

## Criterios de prioridad
| Nivel            | Criterio de entrada                                         | Criterio de salida              |
|------------------|-------------------------------------------------------------|---------------------------------|
| `quick_win`      | Fix aislado, sin cambio de contrato público, test trivial    | PR de 1 commit, sin migration   |
| `fase_media`     | Cambio visible en API interna, test de integración requerido | Review explícito antes de merge |
| `deuda_estructural` | Afecta arquitectura, múltiples módulos o compatibilidad | PLAN+AUDIT_PLAN aprobados primero |

## Reglas
- Emitir veredicto final: `LIMPIO | DEUDA_MENOR | DEUDA_SIGNIFICATIVA | CRÍTICO`.
- Señalar evidencias concretas (archivo, función, línea).
- Diferenciar hallazgos confirmados de hipótesis.
- Si la deuda implica un patrón arquitectónico, referenciar el patrón correcto (SOLID, GoF).
