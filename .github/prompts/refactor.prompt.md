# Prompt: refactor (Python library)

Refactor sin cambios funcionales. API pública estable salvo justificación explícita.
Agentes: Plan Architect (PLAN + AUDIT_PLAN) → Feature Implementer (IMPLEMENT) → Code Auditor
(AUDIT_CODE) → Version Closer (VERSION).

## Inputs requeridos
- **Objetivo**: qué se mejora (SRP, duplicación, nombres…)
- **Módulo(s) afectados**: rutas concretas
- **Restricción de API pública**: ¿cambia? (NO, salvo justificación)
- **Tests existentes**: cobertura disponible para validar la regresión

Si hay cambio de API sin justificación, detente y aclara.

## Devuelve en este orden

### PLAN
- objetivo
- rutas afectadas
- componentes implicados
- riesgos de regresión

### AUDIT_PLAN
- riesgos funcionales
- riesgos técnicos
- riesgos de seguridad (p.ej. cambios en la parametrización SQL o en el manejo de recursos)
- simplificaciones posibles

### IMPLEMENT (por rutas o módulos)
- cambios por archivo
- código
- explicación breve

### AUDIT_CODE
- regresiones potenciales
- contratos públicos sync/async
- cobertura preservada
- tipado

### VERSION
- commit message (`refactor: <descripción>`)
- changelog (qué módulos mejoraron y cómo)
- impacto en API pública (debe ser cero sin justificación)
- rollback
- validación ejecutada: comandos de `SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo»

## Revisar
- módulos, clases y dependencias
- contratos públicos y tipado
- queries y metadatos
- separación de responsabilidades
- estrategia de pruebas o cobertura preservada

## Reglas
- No introducir cambios funcionales.
- Priorizar separación de responsabilidades, eliminación de duplicación y legibilidad.
- Antes de aplicar compatibilidad hacia atrás, confirmar explícitamente si se mantiene el enfoque
  «solo OO» o se habilitan funciones wrapper, y si se autoriza romper contratos públicos o snapshots.
