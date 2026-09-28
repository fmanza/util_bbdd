# Prompt: hotfix (Python library)

Corrección acotada de un bug P1/P2. Política: **solo fix mínimo; prohibido refactorizar y optimizar**.
Agentes: Hotfix Responder (PLAN → IMPLEMENT) → Code Auditor (AUDIT_CODE) → Version Closer (VERSION).

## Inputs requeridos
- **Bug**: qué no funciona
- **Rutas afectadas**: dónde está el bug (archivos concretos)
- **Síntomas**: cómo se manifiesta (logs, comportamiento incorrecto)
- **Dato faltante o supuesto**: qué NO se sabe con seguridad

Si no puedes emitir un PLAN con diagnóstico de causa raíz claro, detente.

## Devuelve en este orden

### PLAN
- objetivo
- rutas afectadas
- componentes implicados
- dato faltante o supuesto
- riesgos

### AUDIT_PLAN
- riesgos funcionales
- riesgos técnicos
- riesgos de seguridad
- simplificaciones posibles

### IMPLEMENT
- diagnóstico de causa raíz (RCA)
- implementación acotada
- test que reproduzca el fallo (si es viable) y estrategia de pruebas

### AUDIT_CODE
- regresiones potenciales
- edge cases
- compatibilidad

### VERSION
- commit message (`hotfix: <descripción>`; scope opcional, p.ej. `hotfix(dump): …`)
- changelog (1-2 líneas)
- rollback (pasos simples)

## Reglas
- Limítate a corregir la causa raíz con el menor alcance posible.
- Incluye un test que reproduzca el fallo cuando sea viable (test-first).
- Antes de cerrar, los comandos de `SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo» deben pasar.
