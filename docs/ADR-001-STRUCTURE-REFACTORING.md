# ADR-001: Refactorización Estructural de util_bbdd

**Status:** PROPOSED
**Date:** 2026-03-11
**Author:** Análisis de Estructura Automatizado
**Context:** util_bbdd v0.4.0 necesita refactorización estructural
**Decision:** Reestructurar el proyecto en 3 niveles jerárquicos con 17 PRs

---

## 1. Problema a Resolver

### Síntomas Actuales
- `database_manager.py` tiene 1400+ líneas (límite recomendado: 400-500)
- Métodos con Complejidad Ciclomática de 22 (límite permitido: 15)
- 16 módulos sin organización jerárquica en raíz
- Metadatos dispersos en 3 archivos separados
- Drivers específicos en 2 ubicaciones diferentes
- Difícil agregar nuevos motores de BD

### Impacto Actual
- ❌ Baja mantenibilidad
- ❌ Baja testabilidad
- ❌ Dificultad escalabilidad
- ❌ Curva de aprendizaje alta

---

## 2. Opciones Consideradas

### Opción A: Sin cambios (Status quo)
**Ventajas:**
- ✅ No requiere esfuerzo
- ✅ Backward compatible (trivial)

**Desventajas:**
- ❌ Deuda técnica crece
- ❌ Nuevas features más difíciles
- ❌ Calidad de código degrada

**Recomendación:** Descartar

---

### Opción B: Refactoring Incremental (Todo al mismo tiempo)
**Ventajas:**
- ✅ Rápido (teóricamente)

**Desventajas:**
- ❌ Alto riesgo de fallas
- ❌ Difícil mergear cambios
- ❌ Imposible validar incrementalmente
- ❌ Revert difícil

**Recomendación:** Descartar

---

### Opción C: ✅ REFACTORING POR FASES (Propuesta)
**Ventajas:**
- ✅ 17 PRs pequeñas (<500 líneas c/u)
- ✅ Validación incremental (443 tests después de cada PR)
- ✅ Bajo riesgo (cada fase independiente)
- ✅ Reversible (rollback plan per PR)
- ✅ Mejor code review
- ✅ Comunicable a team

**Desventajas:**
- ⚠️ Toma tiempo (~11 semanas)
- ⚠️ Requiere coordinación team
- ⚠️ Requiere CI/CD fiable

**Recomendación:** ✅ ADOPTAR

---

## 3. Decisión

### Refactorizar util_bbdd en 3 niveles jerárquicos mediante 17 PRs sobre 9-11 semanas

```
ESTRUCTURA PROPUESTA (3 Niveles):

├── _core/              → Abstracciones (tipos, excepciones, contracts)
├── _drivers/           → Drivers y validación
├── connection/         → Conexión y pool (nivel 2: acceso indirecto)
├── query/              → Queries y ejecución (nivel 2: acceso indirecto)
├── metadata/           → Metadatos (nivel 2: acceso indirecto)
├── results/            → Resultados (nivel 3: especializado)
├── bulk/               → CRUD masivo (nivel 3: especializado)
├── analysis/           → Análisis relaciones (nivel 3: especializado)
└── managers/           → APIs alto nivel (coordinador)
```

### Justificación

**Arquitectura Limpia:**
- Separación clara de responsabilidades
- Bajo acoplamiento, alta cohesión
- Fácil testabilidad

**Escalabilidad:**
- Agregar nuevo motor = nuevo archivo en `connection/motors/`
- Nuevas features = nuevo módulo especializado en nivel 3
- No afecta código existente

**Mantenibilidad:**
- Cada módulo < 500 líneas
- Responsabilidad única por archivo
- Imports reducidos y explícitos

---

## 4. Plan de Implementación

### Fases (9 fases, 17 PRs)

| Fase | PRs | Objetivo | Duración |
|------|-----|----------|----------|
| 1 | #1-2 | Core y drivers | 1 semana |
| 2 | #3-5 | Connection | 1.5 semanas |
| 3 | #6-8 | Queries | 1 semana |
| 4 | #9-11 | Metadatos | 1.5 semanas |
| 5 | #12-14 | Results, Bulk, Analysis | 1.5 semanas |
| 6 | #15-16 | Managers | 1 semana |
| 7 | #17-18 | Cleanup y docs | 1 semana |
| 8 | #19 | Validación | 0.5 semana |

**Total:** ~11 semanas, 105-140 horas

### Validación por Fase

Cada PR requiere:
- ✅ 443/443 tests passing (100%)
- ✅ Coverage >= 80%
- ✅ mypy: 0 errors
- ✅ ruff: 0 errors
- ✅ Backward compatible
- ✅ Code review approval

---

## 5. Métricas de Éxito

### Antes (v0.4.0)
```
Líneas máx/archivo:        1400+
CC máximo:                 22
Módulos raíz:              16
Cohesión:                  Media
Acoplamiento:              Alto
```

### Después (v0.5.0)
```
Líneas máx/archivo:        <500 (56% reducción ✅)
CC máximo:                 ~8 (64% reducción ✅)
Módulos raíz:              6 (62% reducción ✅)
Cohesión:                  Alta (+40% ✅)
Acoplamiento:              Bajo (-40% ✅)
```

### No Negociable
- ✅ 443/443 tests passing (cobertura del 85%)
- ✅ Zero breaking changes para API pública
- ✅ Backward compatible 2 releases
- ✅ Documentación completa

---

## 6. Consecuencias

### Positivas
- ✅ Código más mantenible
- ✅ Nueva developers pueden entender estructura rápidamente
- ✅ Agregar features es más seguro
- ✅ Calidad de código mejora
- ✅ Testing es más fácil

### Neutrales
- ⚪ Tiempo inicial importante (~11 semanas)
- ⚪ Requiere coordinación del equipo
- ⚪ CI/CD debe ser fiable

### Riesgos y Mitigación
| Riesgo | Impacto | Mitigación |
|--------|---------|-----------|
| Tests fallan | Alto | Cada PR valida 443 tests |
| Breaking changes | Alto | Exports mantenidos en `__init__.py` |
| Import circulares | Medio | Diseño cuidadoso (DAG) |
| Performance | Bajo | Benchmarking continuo |
| Team no capacitado | Medio | Migration guide + training |

---

## 7. Alternativas Consideradas (Largo Plazo)

### Considerar en futuro (v0.6.0+)
- Plugin architecture para nuevos motores
- Async-first design
- Query builder abstraction
- ORM layer

---

## 8. Referencias

### Principios Aplicados
- Clean Architecture (Robert C. Martin)
- SOLID principles
- DRY (Don't Repeat Yourself)
- SRP (Single Responsibility Principle)

### Documentos Relacionados
- `docs/REFACTORING_PLAN_v0.4.0.md` - Plan detallado
- `docs/PR_EXECUTION_PLAN.md` - Plan de PRs
- `docs/EXECUTIVE_SUMMARY.md` - Resumen ejecutivo

---

## 9. Aprobación

### Requerida de:
- [ ] **Tech Lead / Architect** - Aprobación arquitectónica
- [ ] **Team Lead** - Viabilidad de timeline
- [ ] **Product** - Alignment con roadmap
- [ ] **QA** - Estrategia de testing

### Approved by:
- Tech Lead: _________________ (Firma)
- Team Lead: _________________ (Firma)
- Product: _________________ (Firma)
- Date: _________________

---

## 10. Seguimiento

### Hito 1: Aprobación (Semana 1)
- [ ] ADR aprobado
- [ ] Documentos revisados
- [ ] Team capacitado
- [ ] Rama de feature creada

### Hito 2: Progreso (Semana 4)
- [ ] PRs #1-5 completas
- [ ] 100% cobertura de tests
- [ ] Zero breaking changes

### Hito 3: Finalización (Semana 11)
- [ ] PRs #1-19 completas
- [ ] Docs actualizadas
- [ ] Release v0.5.0 ready

### Hito 4: Post-Release (Release + 2)
- [ ] Monitor issues
- [ ] Support v0.4.x con deprecation warnings
- [ ] Migration path claro

---

## 11. Cambios Futuros a Este ADR

Si el contexto cambia:
1. Comunicar cambio al equipo
2. Actualizar sección 11 con fecha y razón
3. Mergear cambios en rama main
4. Mantener histórico

---

## 12. Glosario

**CC:** Complejidad Ciclomática (métrica de complejidad)
**ADR:** Architecture Decision Record (este documento)
**DAG:** Directed Acyclic Graph (sin ciclos)
**SRP:** Single Responsibility Principle
**SOLID:** Suite de principios de diseño

---

**Documento finalizado**

Propuesta de refactorización estructural completa y fundamentada.
Pendiente de aprobación ejecutiva del equipo.

---

### Anexo: Cronograma Detallado

```
SEMANA 1:
├─ Aprobación ADR
├─ PR #1: _core/ (tipos, excepciones, contracts)
└─ PR #2: _drivers/ (drivers y validación)

SEMANA 2-3:
├─ PR #3: connection/ - consolidar files
├─ PR #4: connection/motors/ - drivers específicos
└─ PR #5: data/loader.py

SEMANA 4:
├─ PR #6: query/ - registry y resolver
├─ PR #7: query/executors/
└─ PR #8: query/database_queries.py

SEMANA 5-6:
├─ PR #9: metadata/ - base (cache, contracts, normalizer)
├─ PR #10: metadata/ - builder y fetcher
└─ PR #11: metadata/manager.py

SEMANA 7:
├─ PR #12: results/
├─ PR #13: bulk/
└─ PR #14: analysis/

SEMANA 8-9:
├─ PR #15: managers/database.py
└─ PR #16: managers/async_database.py

SEMANA 10:
├─ PR #17: Cleanup directorios antiguos
└─ PR #18: Documentación y migration guide

SEMANA 11:
├─ PR #19: Full test suite validation
└─ RELEASE v0.5.0
```

---

**Fin del ADR-001**
