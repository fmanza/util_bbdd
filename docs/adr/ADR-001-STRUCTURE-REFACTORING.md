# ADR-001: Refactorización Estructural de util_bbdd

> Nota histórica (2026-03-31): esta ADR documenta la decisión de reestructuración para v0.4.0→v0.5.0.
> Sus referencias a fases y métricas deben leerse en contexto histórico; la decisión está ACEPTADA e implementada.

## 1. Contexto y Problema

En la versión v0.4.0, `util_bbdd` presentaba síntomas de deuda técnica acumulada:

- `database_manager.py` con más de 1400 líneas (límite recomendado: 400–500)
- Complejidad Ciclomática máxima de 22 (límite recomendado: 15)
- 16 módulos sin organización jerárquica en la raíz del paquete
- Metadatos dispersos en 3 archivos separados
- Drivers específicos en 2 ubicaciones diferentes

El impacto operativo era baja mantenibilidad, baja testabilidad y alta curva de aprendizaje para nuevos contributors.

## 2. Decisión

Reestructurar `util_bbdd` en 3 niveles jerárquicos mediante 17 PRs incrementales a lo largo de 9–11 semanas, siguiendo los principios de Clean Architecture y SOLID.

**Estructura adoptada:**

```
_core/       → Abstracciones (tipos, excepciones, contracts)
_drivers/    → Drivers y validación
connection/  → Conexión y pool
query/       → Queries y ejecución
metadata/    → Metadatos
results/     → Resultados
bulk/        → CRUD masivo
analysis/    → Análisis de relaciones
managers/    → APIs de alto nivel (coordinador)
```

Se eligió el enfoque incremental (por fases y PRs pequeños) sobre el refactoring monolítico porque permite validación incremental (100% tests por PR), bajo riesgo de regresión y rollback granular por PR.

## 3. Consecuencias

| Tipo | Descripción |
|---|---|
| Ventaja | Cada módulo < 500 líneas; complejidad ciclomática reducida al ~64% |
| Ventaja | Agregar un nuevo motor de BD = crear un único archivo en `connection/motors/` |
| Ventaja | Testing más sencillo por responsabilidad única por módulo |
| Compromiso | Tiempo de implementación elevado (~11 semanas, 105–140 horas) |
| Compromiso | Requiere mantener fachadas legacy durante 2 releases para backward compatibility |
| Deuda técnica aceptada | Algunas rutas legacy (`util_bbdd.database_manager`, `util_bbdd.bulk_crud`) se mantienen como aliases hasta v0.6.x |

**Métricas alcanzadas (v0.5.0 vs v0.4.0):**

| Métrica | Antes | Después |
|---|---|---|
| Líneas máx/archivo | 1400+ | <500 |
| CC máximo | 22 | ~8 |
| Módulos en raíz | 16 | 6 |

## 4. Alternativas Consideradas

| Alternativa | Pros | Contras | Motivo de rechazo |
|---|---|---|---|
| **Mantener status quo** | Sin esfuerzo inmediato | Deuda crece, nuevas features más difíciles | Insostenible a largo plazo |
| **Refactoring monolítico** | Teóricamente más rápido | Alto riesgo, difícil mergear, imposible validar incrementalmente | Riesgo de regresión inaceptable |
| **Refactoring por fases (adoptado)** | Validación incremental, bajo riesgo, reversible por PR | Toma tiempo, requiere coordinación | — |

## 5. Estado y Revisión

**Estado:** ACEPTADO — implementado en v0.5.0 (completado en 2026-03-31)

La estructura de 3 niveles jerárquicos está vigente en la versión actual del repositorio.
Las fachadas legacy siguen activas; su deprecación se documenta en `MIGRATION_GUIDE.md`.

Fecha de última revisión: 2026-06-03
