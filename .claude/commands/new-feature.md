# new_feature

Nueva funcionalidad para la librería. Política: **prohibido refactorizar**.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/new_feature.prompt.md` — inputs requeridos, contrato de salida y reglas
2. `.github/agents/plan-architect.agent.md` (PLAN + AUDIT_PLAN), `feature-implementer.agent.md` (IMPLEMENT),
   `code-auditor.agent.md` (AUDIT_CODE) y `version-closer.agent.md` (VERSION)

## Reglas de ejecución

- **⚠️ VALIDACIÓN**: si falta algún input del prompt, DETENTE y aclara antes de emitir PLAN.
- Detente tras AUDIT_PLAN y espera aprobación explícita antes de IMPLEMENT.

## Ejemplo de entrada

```text
/new-feature

Objetivo: exportar el informe de comparación de esquemas a Parquet
Módulo(s): src/util_bbdd/comparar/reporters/parquet_reporter.py (nuevo), tests/comparar/test_parquet_reporter.py (nuevo)
API esperada: SchemaDiff.to_parquet(path: Path) -> Path
Contrato entrada: SchemaDiff ya calculado
Contrato salida: fichero Parquet determinista (orden estable)
Reglas de negocio: no inventar metadatos
Restricciones: sin dependencias nuevas (pandas.DataFrame.to_parquet)
Motores/formatos: Parquet (agnóstico de BD)
Migraciones: no
Archivos relevantes: sí — comparar/reporters/
```
