# Prompt: new_feature (Python library)

Nueva funcionalidad para la librería. Política: **prohibido refactorizar** código no relacionado.
Agentes: Plan Architect (PLAN + AUDIT_PLAN) → Feature Implementer (IMPLEMENT) → Code Auditor
(AUDIT_CODE) → Version Closer (VERSION).

## Inputs requeridos
- **Objetivo**: qué se implementa (1-2 líneas)
- **Módulo(s) o clase(s)**: rutas completas; marca `(nuevo)` las que no existen
- **API pública esperada**: qué cambia en la firma (parámetros, tipos, métodos)
- **Contrato de entrada**: qué espera recibir (prerrequisitos, tipos)
- **Contrato de salida**: qué garantiza producir (output, invariantes)
- **Reglas de negocio**: restricciones funcionales (no inventar metadatos, determinismo…)
- **Restricciones técnicas**: sin dependencias nuevas, sync/async, etc.
- **Motores o formatos afectados**
- **Migraciones necesarias**
- **Archivos relevantes existentes**: sí/no + referencias

Si falta alguno, detente y aclara antes de emitir PLAN.

## Devuelve en este orden

### PLAN
- objetivo
- rutas afectadas
- componentes implicados
- tipos necesarios
- riesgos

### AUDIT_PLAN
- riesgos funcionales
- riesgos técnicos (incluye impacto en LSP/ISP: contratos sync/async y tamaño de interfaces)
- riesgos de seguridad
- simplificaciones posibles
- **Veredicto:** `GO | NO_GO | GO_CONDICIONAL` (con condiciones si aplica)

### IMPLEMENT (por capas: Level 1 → 2 → 3)
- cambios por archivo
- código
- explicación breve

### AUDIT_CODE
- bugs potenciales (`archivo:línea`)
- edge cases
- performance
- seguridad
- tipado
- deuda técnica

### VERSION
- commit message (`feat: <descripción>`)
- changelog por módulo afectado
- impacto en API pública
- rollback
- pruebas sugeridas

## Reglas
- Antes de cerrar IMPLEMENT, los comandos de `SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo» deben pasar.
- Documentación obligatoria según `SHARED_INSTRUCTIONS.md` § «Documentación obligatoria».
