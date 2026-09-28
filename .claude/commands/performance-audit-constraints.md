# /performance-audit-constraints

Auditoría de rendimiento de la desactivación de constraints (FK, UK, CHECK, índices asociados, triggers)
durante la carga masiva de `bulk` y `dump`: coste por constraint y motor, estrategias seguras de
desactivación y reactivación, riesgos de integridad y alternativas sin desactivar. Solo lectura.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/performance_audit_constraints.prompt.md` — inputs, áreas de auditoría y reglas (contrato de salida)
2. `.github/prompts/performance_audit_constraints_agent.prompt.md` — flujo operativo en 5 fases y archivos clave
3. `.github/agents/performance-auditor.agent.md` — rol y criterios de prioridad
4. `docs/performance_audit_constraints_guide.md` — guía de uso y referencia rápida

## Reglas de ejecución

- Si falta algún input obligatorio del prompt, decláralo como supuesto explícito y continúa.
- Cita solo código real (`archivo:línea`); los ejemplos de los prompts son ilustrativos.
- Cualquier recomendación que desactive constraints debe incluir validación de integridad post-carga y rollback.
- Puedes consultar internet para el comportamiento por motor; cita la fuente.
- Las mejoras se implementan después con `/new-feature` o `/refactor` (commit `perf:`).

## Ejemplo de entrada

```text
/performance-audit-constraints

Tabla objetivo: orders (3 FK, 1 UK, 1 CHECK)
Operación: INSERT
Volumen: 1M
Base de datos: PostgreSQL + SQL Server
Baseline: 5,2 s por 100K filas con constraints activos
Restricciones de negocio: no desactivar la auditoría; ventana máxima de 30 min
```
