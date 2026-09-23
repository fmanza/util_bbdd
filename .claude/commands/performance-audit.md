# performance-audit

Auditoría de rendimiento del módulo bulk: optimización de carga masiva de datos.

## Cuándo usar
- Necesitas optimizar velocidad de INSERT/UPDATE/DELETE masivos
- Quieres identificar cuellos de botella en carga de datos
- Necesitas impacto cuantificable (% mejora estimado)
- Ciclo completo: PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION

## Inputs requeridos (OBLIGATORIO completar TODOS)

- [ ] **Módulo objetivo**: `src/util_bbdd/bulk/` (fijo, pero puedes especificar sub-áreas)
- [ ] **Operaciones a auditar**: INSERT | UPDATE | DELETE | Todas (marcar)
- [ ] **Escala de datos**: Tamaño típico de registros (1K, 10K, 100K, 1M+)
- [ ] **Motores de BD**: Oracle | MySQL/MariaDB | PostgreSQL | SQL Server | SQLite (marcar todos los relevantes)
- [ ] **Restricciones conocidas**: ¿auditoría integrada obligatoria? ¿validación? ¿compatibilidad?
- [ ] **Métricas base (si disponibles)**: Tiempo actual de carga, bottleneck conocido
- [ ] **Alcance de la auditoría**: Análisis solo | Incluir propuestas de remediación | Quick wins únicamente

**⚠️ VALIDACIÓN**: Si falta alguno, DETENTE y aclara antes de continuar. No emitas PLAN hasta tener contexto completo.

## Devuelve en este orden

### PLAN
- Flujo actual de carga (INSERT → batching → auditoría → persistence)
- Cuellos de botella teóricos identificados por área
- Estrategia de benchmark (qué medir, cómo reproducir)
- 10 áreas de auditoría a investigar

### AUDIT_PLAN
- Validación de viabilidad de cada mejora propuesta
- Breaking changes y compatibilidad multi-BBDD
- Pruebas requeridas por área
- Orden de ejecución (dependencias entre mejoras)
- **Veredicto:** GO / NO_GO / GO_CONDICIONAL

### AUDIT_CODE
- Hallazgos por severidad (CRÍTICA, ALTA, MEDIA, BAJA, INFO)
- Por cada hallazgo: Área, Archivo/Función, Descripción, Impacto% estimado, Evidencia, Remediación propuesta
- Diferenciar CONFIRMADO (código + benchmarks) de HIPÓTESIS (requiere validación)
- Consultar internet para best practices y versiones actuales

### VERSION
- **Veredicto final**: CRÍTICO | SIGNIFICATIVO | MODERADO | LIMPIO
- Top 5 mejoras de mayor impacto
- Quick wins (< 1h, 5%+ mejora, sin breaking changes)
- Fases de implementación recomendadas
- Métricas de éxito (antes/después en benchmark)

## Referencia
- Base: `.github/prompts/performance_audit_bulk.prompt.md`
- Agente: `Performance Auditor` (`.github/agents/performance-auditor.agent.md`)
- 10 áreas: Batching, Paralelización, Normalización SQL, Conexiones, Auditoría, Memoria, SQL generation, DB-specific, PK sync, Validation
